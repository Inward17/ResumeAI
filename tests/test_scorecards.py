"""Structured interview scorecards: template, AI suggestion, submissions, independent review, evidence summary."""
import json
from unittest.mock import AsyncMock, patch

from app.services import scorecards as sc
from app.services.fact_checker_service import AIServiceUnavailable
from tests.conftest import create_owned_job

GROQ = "app.routes.scorecard_routes._call_groq"
EVIDENCE = "Walked through sharding a 2 TB table and the rollback plan."


def comp(name, weight=1, cid=None):
    return {"id": cid or name.lower(), "name": name, "description": f"{name} skill",
            "anchors": ["gap", "some", "meets", "strong"], "weight": weight}


TEMPLATE = {"competencies": [comp("Design", 3), comp("Coding", 2), comp("Communication", 1)]}


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


async def _setup(client, mock_db, job_id, cid="c1"):
    await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": cid, "status": "Shortlisted"})
    assert (await client.put(f"/api/jobs/{job_id}/scorecard", json=TEMPLATE)).status_code == 200
    return f"/api/jobs/{job_id}/candidates/{cid}/scorecards"


async def _add_member(client, mock_db, uid, name):
    from app.auth import AuthUser
    await client.get("/api/org")  # creates the owner's workspace
    org_id = (await mock_db.users.find_one({"uid": "test-user"}))["org_id"]
    await mock_db.org_members.insert_one({"org_id": org_id, "uid": uid, "email": f"{uid}@example.com", "name": name, "role": "member"})
    await mock_db.users.insert_one({"uid": uid, "org_id": org_id})
    return AuthUser(uid=uid, email=f"{uid}@example.com", name=name)


def submission(design=4, coding=3, rec="yes", submit=True):
    return {"ratings": [{"competency_id": "design", "rating": design, "evidence": EVIDENCE},
                        {"competency_id": "coding", "rating": coding, "evidence": EVIDENCE},
                        {"competency_id": "communication", "rating": None}],
            "recommendation": rec, "summary": "Solid systems thinking.", "submit": submit}


class TestTemplate:
    async def test_save_and_read(self, client, owned_job_id):
        url = f"/api/jobs/{owned_job_id}/scorecard"
        assert (await client.get(url)).json() == {"scorecard": None}
        body = {"competencies": [{**c, "id": ""} for c in TEMPLATE["competencies"]]}
        saved = (await client.put(url, json=body)).json()["scorecard"]["competencies"]
        assert [c["name"] for c in saved] == ["Design", "Coding", "Communication"]
        assert all(c["id"] for c in saved) and len({c["id"] for c in saved}) == 3  # ids generated
        assert (await client.get(url)).json()["scorecard"]["competencies"] == saved

    async def test_validation(self, client, owned_job_id):
        url = f"/api/jobs/{owned_job_id}/scorecard"
        c = TEMPLATE["competencies"]
        bad = [
            {"competencies": c[:2]},                                     # fewer than 3
            {"competencies": [comp(f"C{i}") for i in range(9)]},         # more than 8
            {"competencies": [comp("Design", 0), c[1], c[2]]},           # weight below 1
            {"competencies": [comp("Design", 11), c[1], c[2]]},          # weight above 10
            {"competencies": [{**c[0], "anchors": ["a", "b"]}, c[1], c[2]]},  # not 4 anchors
            {"competencies": [c[0], {**c[0], "id": "x"}, c[2]]},         # duplicate name
            {"competencies": [c[0], {**c[1], "id": "design"}, c[2]]},    # duplicate id
            {"competencies": [{**c[0], "id": "$where"}, c[1], c[2]]},    # unsafe id
            {"competencies": [{**c[0], "name": "  "}, c[1], c[2]]},      # blank name
        ]
        for body in bad:
            assert (await client.put(url, json=body)).status_code == 422, body

    async def test_other_workspace_job_is_404(self, client, mock_db):
        other = await create_owned_job(mock_db, owner_uid="someone-else")
        assert (await client.get(f"/api/jobs/{other}/scorecard")).status_code == 404
        assert (await client.put(f"/api/jobs/{other}/scorecard", json=TEMPLATE)).status_code == 404
        assert (await client.get(f"/api/jobs/{other}/scorecard-counts")).status_code == 404
        assert "scorecard" not in await mock_db.jobs.find_one({})

    async def test_job_delete_removes_scorecards(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        await client.put(url + "/mine", json=submission())
        assert (await client.delete(f"/api/jobs/{owned_job_id}")).status_code == 200
        assert await mock_db.scorecards.count_documents({}) == 0


class TestSuggest:
    DRAFT = {"competencies": [{"name": n, "description": "d", "anchors": ["1", "2", "3", "4"], "weight": 3}
                              for n in ("System design", "Python", "Ownership", "Collaboration")]}

    async def test_suggestion_is_validated_and_not_saved(self, client, mock_db, owned_job_id):
        with patch(GROQ, AsyncMock(return_value="```json\n" + json.dumps(self.DRAFT) + "\n```")) as ai:
            resp = await client.post(f"/api/jobs/{owned_job_id}/scorecard/suggest")
        assert resp.status_code == 200
        assert [c["name"] for c in resp.json()["competencies"]] == ["System design", "Python", "Ownership", "Collaboration"]
        assert "<candidate_data>" in ai.call_args.args[1]  # job text is delimited
        assert "scorecard" not in await mock_db.jobs.find_one({})
        usage = await mock_db.usage_quotas.find_one({})
        assert usage["count"] == 1 and usage["features"]["scorecards"] == 1

    async def test_ai_down_is_503(self, client, owned_job_id):
        with patch(GROQ, AsyncMock(side_effect=AIServiceUnavailable("down"))):
            resp = await client.post(f"/api/jobs/{owned_job_id}/scorecard/suggest")
        assert resp.status_code == 503 and "AI service is down" in resp.json()["detail"]

    async def test_unusable_output_is_503(self, client, owned_job_id):
        for raw in ("not json", json.dumps({"competencies": self.DRAFT["competencies"][:1]})):
            with patch(GROQ, AsyncMock(return_value=raw)):
                assert (await client.post(f"/api/jobs/{owned_job_id}/scorecard/suggest")).status_code == 503

    async def test_quota(self, client, owned_job_id, monkeypatch):
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "1")
        with patch(GROQ, AsyncMock(return_value=json.dumps(self.DRAFT))) as ai:
            assert (await client.post(f"/api/jobs/{owned_job_id}/scorecard/suggest")).status_code == 200
            assert (await client.post(f"/api/jobs/{owned_job_id}/scorecard/suggest")).status_code == 429
        assert ai.call_count == 1


class TestSubmission:
    async def test_needs_template(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"job_id": owned_job_id, "candidate_id": "c1"})
        resp = await client.put(f"/api/jobs/{owned_job_id}/candidates/c1/scorecards/mine", json=submission())
        assert resp.status_code == 409

    async def test_submit_requires_evidence_recommendation_summary(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id) + "/mine"
        thin = submission()
        thin["ratings"][1]["evidence"] = "good"
        resp = await client.put(url, json=thin)
        assert resp.status_code == 400 and "Coding" in resp.json()["detail"] and "Design" not in resp.json()["detail"]
        assert (await client.put(url, json={**submission(), "recommendation": None})).status_code == 400
        assert (await client.put(url, json={**submission(), "summary": " "})).status_code == 400
        assert (await client.put(url, json={**submission(), "ratings": []})).status_code == 400
        unknown = submission()
        unknown["ratings"].append({"competency_id": "nope", "rating": 2, "evidence": EVIDENCE})
        assert (await client.put(url, json=unknown)).status_code == 400
        assert (await client.put(url, json={**submission(), "recommendation": "maybe"})).status_code == 422
        bad_rating = submission(design=5)
        assert (await client.put(url, json=bad_rating)).status_code == 422
        assert await mock_db.scorecards.count_documents({}) == 0

    async def test_draft_then_submit_then_update_keeps_history(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        draft = {"ratings": [{"competency_id": "design", "rating": 3, "evidence": "half"}], "submit": False}
        mine = (await client.put(url + "/mine", json=draft)).json()["mine"]
        assert mine["status"] == "draft" and mine["submitted_at"] is None
        app = await mock_db.applications.find_one({"candidate_id": "c1"})
        assert app["status"] == "Shortlisted"  # drafts don't move the candidate

        assert (await client.put(url + "/mine", json=submission())).json()["mine"]["status"] == "submitted"
        assert (await mock_db.applications.find_one({"candidate_id": "c1"}))["status"] == "Interview"
        # Once submitted, autosave can't turn it back into a draft
        assert (await client.put(url + "/mine", json=draft)).status_code == 409
        updated = (await client.put(url + "/mine", json=submission(design=2))).json()["mine"]
        assert updated["versions"] == 1 and updated["ratings"][0]["rating"] == 2
        stored = await mock_db.scorecards.find_one({})
        assert stored["history"][0]["ratings"][0]["rating"] == 4

    async def test_one_card_per_interviewer(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        await client.put(url + "/mine", json=submission())
        await client.put(url + "/mine", json=submission())
        assert await mock_db.scorecards.count_documents({}) == 1

    async def test_other_workspace_candidate_is_404(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        other = await create_owned_job(mock_db, owner_uid="someone-else", scorecard=TEMPLATE)
        await mock_db.applications.insert_one({"job_id": other, "candidate_id": "theirs"})
        their = f"/api/jobs/{other}/candidates/theirs/scorecards"
        mixed = f"/api/jobs/{owned_job_id}/candidates/theirs/scorecards"
        for u in (their, mixed):
            assert (await client.get(u)).status_code == 404
            assert (await client.put(u + "/mine", json=submission())).status_code == 404
            assert (await client.get(u + "/summary")).status_code == 404
            assert (await client.post(u + "/requests", json={"uid": "test-user"})).status_code == 404
        assert (await client.get(url)).status_code == 200
        assert await mock_db.scorecards.count_documents({}) == 0

    async def test_request_only_workspace_members(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        assert (await client.post(url + "/requests", json={"uid": "outsider"})).status_code == 404
        await _add_member(client, mock_db, "ana", "Ana")
        assert (await client.post(url + "/requests", json={"uid": "ana"})).status_code == 200
        assert (await client.get(url)).json()["interviewers"] == [{"uid": "ana", "name": "Ana", "status": "requested"}]
        assert (await client.delete(url + "/requests/ana")).status_code == 200
        assert (await client.get(url)).json()["interviewers"] == []


class TestIndependence:
    async def test_interviewer_sees_others_only_after_submitting(self, client, mock_db, owned_job_id, test_user):
        url = await _setup(client, mock_db, owned_job_id)
        ana = await _add_member(client, mock_db, "ana", "Ana")
        ben = await _add_member(client, mock_db, "ben", "Ben")
        await client.post(url + "/requests", json={"uid": "ana"})
        await client.post(url + "/requests", json={"uid": "ben"})

        _sign_in_as(ana)
        assert (await client.put(url + "/mine", json=submission(design=4))).status_code == 200

        _sign_in_as(ben)  # asked, not submitted: sees only his own
        view = (await client.get(url)).json()
        assert view["locked"] is True and view["others"] == [] and view["mine"]["status"] == "requested"
        assert {i["uid"]: i["status"] for i in view["interviewers"]} == {"ana": "submitted", "ben": "requested"}
        assert (await client.get(url + "/summary")).status_code == 403
        with patch(GROQ, AsyncMock(return_value="{}")) as ai:
            assert (await client.post(url + "/brief")).status_code == 403
        ai.assert_not_called()
        # A draft keeps him locked too
        await client.put(url + "/mine", json={**submission(design=1), "submit": False})
        assert (await client.get(url)).json()["locked"] is True

        await client.put(url + "/mine", json=submission(design=1))
        view = (await client.get(url)).json()
        assert view["locked"] is False and [o["author_name"] for o in view["others"]] == ["Ana"]

        _sign_in_as(test_user)  # never asked: sees every submitted card
        view = (await client.get(url)).json()
        assert view["locked"] is False and view["mine"] is None
        assert sorted(o["author_name"] for o in view["others"]) == ["Ana", "Ben"]

    async def test_drafts_are_private(self, client, mock_db, owned_job_id, test_user):
        url = await _setup(client, mock_db, owned_job_id)
        ana = await _add_member(client, mock_db, "ana", "Ana")
        _sign_in_as(ana)
        await client.put(url + "/mine", json={**submission(), "submit": False})
        _sign_in_as(test_user)
        assert (await client.get(url)).json()["others"] == []
        assert (await client.get(url + "/summary")).json()["summary"]["submitted"] == 0

    def test_rule(self):
        assert sc.must_submit_first(None) is False
        assert sc.must_submit_first({"status": "requested"}) is True
        assert sc.must_submit_first({"status": "draft"}) is True
        assert sc.must_submit_first({"status": "submitted"}) is False


class TestAggregate:
    TPL = [comp("Design", 3), comp("Coding", 1), comp("Communication", 2)]

    def card(self, ratings, rec="yes", status="submitted", name="A"):
        return {"status": status, "author_name": name, "recommendation": rec, "summary": "s",
                "ratings": [{"competency_id": k, "rating": v, "evidence": f"note {k}", "question_ids": [1]}
                            for k, v in ratings.items()]}

    def test_weighted_mean_spread_disagreement(self):
        cards = [self.card({"design": 4, "coding": 2}, "strong_yes", name="A"),
                 self.card({"design": 2, "coding": 2, "communication": None}, "no", name="B"),
                 self.card({"design": 1}, "strong_no", status="draft")]  # drafts never count
        s = sc.aggregate(self.TPL, cards, {"questions": [{"question_id": 1, "question": "Q1", "selected_tags": ["x"], "total_tags": 2}]})
        design, coding, comm = s["competencies"]
        assert (design["mean"], design["spread"], design["disagreement"], design["score"]) == (3, 2, True, 67)
        assert (coding["mean"], coding["spread"], coding["disagreement"]) == (2, 0, False)
        assert comm["mean"] is None and comm["score"] is None and comm["spread"] is None and comm["ratings"] == 0
        # Communication (unrated) is left out of the weights: (3*3 + 2*1) / 4 = 2.75 -> 58
        assert s["overall_score"] == 58
        assert s["recommendations"] == {"strong_no": 0, "no": 1, "yes": 0, "strong_yes": 1}
        assert s["submitted"] == 2
        assert [e["author"] for e in design["evidence"]] == ["A", "B"]
        assert design["evidence"][0]["questions"] == [{"id": 1, "question": "Q1", "covered": ["x"], "total": 2}]

    def test_no_ratings_is_null_not_zero(self):
        s = sc.aggregate(self.TPL, [self.card({"design": None})])
        assert s["overall_score"] is None
        assert all(c["score"] is None for c in s["competencies"])
        assert sc.aggregate(self.TPL, [])["overall_score"] is None

    def test_scale(self):
        assert [sc.to_100(v) for v in (1, 2, 3, 4, None)] == [0, 33, 67, 100, None]
        s = sc.aggregate(self.TPL, [self.card({"design": 4, "coding": 4, "communication": 4})])
        assert s["overall_score"] == 100

    async def test_summary_endpoint(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        await client.put(url + "/mine", json=submission(design=4, coding=1))
        s = (await client.get(url + "/summary")).json()["summary"]
        assert s["submitted"] == 1 and s["competencies"][0]["score"] == 100
        # (4*3 + 1*2) / 5 = 2.8 -> 60
        assert s["overall_score"] == 60


class TestBrief:
    async def test_brief_cites_only_real_interviewers(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        await client.put(url + "/mine", json=submission())
        answer = {"summary": "Strong design evidence.", "points": [
            {"competency": "Design", "text": "Explained sharding.", "cited": ["I1"]},
            {"competency": "Coding", "text": "Invented point.", "cited": ["I9"]},
            {"competency": "Coding", "text": "Uncited point.", "cited": []},
        ]}
        with patch(GROQ, AsyncMock(return_value=json.dumps(answer))) as ai:
            resp = await client.post(url + "/brief")
        assert resp.status_code == 200
        brief = resp.json()["brief"]
        assert brief["points"] == [{"competency": "Design", "text": "Explained sharding.", "cited": ["Test User"]}]
        prompt = ai.call_args.args[1]
        assert EVIDENCE in prompt and "<candidate_data>" in prompt and "Test User" not in prompt  # labels, not names
        assert (await mock_db.usage_quotas.find_one({}))["features"]["scorecards"] == 1

    async def test_brief_needs_submissions_and_ai(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        with patch(GROQ, AsyncMock(return_value="{}")) as ai:
            assert (await client.post(url + "/brief")).status_code == 409
        ai.assert_not_called()
        await client.put(url + "/mine", json=submission())
        with patch(GROQ, AsyncMock(side_effect=AIServiceUnavailable("down"))):
            resp = await client.post(url + "/brief")
        assert resp.status_code == 503 and "AI service is down" in resp.json()["detail"]
        with patch(GROQ, AsyncMock(return_value="no json")):
            assert (await client.post(url + "/brief")).status_code == 503


class TestCountsAndApiKeys:
    async def test_counts(self, client, mock_db, owned_job_id):
        url = await _setup(client, mock_db, owned_job_id)
        await _add_member(client, mock_db, "ana", "Ana")
        await client.post(url + "/requests", json={"uid": "ana"})
        await client.put(url + "/mine", json=submission())
        counts = (await client.get(f"/api/jobs/{owned_job_id}/scorecard-counts")).json()["counts"]
        assert counts == {"c1": {"submitted": 1, "total": 2}}

    async def test_api_key_works_in_its_own_workspace_only(self, client, anon_client, mock_db, owned_job_id):
        from app.main import app
        from app.auth import get_current_user
        url = await _setup(client, mock_db, owned_job_id)
        other = await create_owned_job(mock_db, owner_uid="someone-else")
        key = (await client.post("/api/org/api-keys", json={"name": "ATS"})).json()["key"]
        headers = {"Authorization": f"Bearer {key}"}
        with patch("app.auth.AUTH_DISABLED", False):
            app.dependency_overrides.pop(get_current_user)
            assert (await anon_client.get(f"/api/jobs/{owned_job_id}/scorecard", headers=headers)).status_code == 200
            assert (await anon_client.get(url, headers=headers)).status_code == 200
            assert (await anon_client.get(f"/api/jobs/{other}/scorecard", headers=headers)).status_code == 404
            assert (await anon_client.get(url)).status_code == 401


def test_brief_prose_uses_names_not_labels():
    from app.services.scorecards import check_brief
    r = check_brief({"summary": "Interviewer I1 recommends hiring; I2 disagrees.",
                     "points": [{"text": "I1 saw strong SQL", "cited": ["I1"]}]}, {"I1": "Asha", "I2": "Ben"})
    assert r["summary"] == "Asha recommends hiring; Ben disagrees."
    assert r["points"][0]["text"] == "Asha saw strong SQL"


async def test_interviewer_can_submit_but_not_manage(client, mock_db):
    from tests.test_rbac import _sign_in_as, _user, _workspace
    _, assigned, other = await _workspace(client, mock_db)
    tpl = {"competencies": [{"name": n, "description": "", "anchors": ["a", "b", "c", "d"], "weight": 1}
                            for n in ("SQL", "Python", "Communication")]}
    assert (await client.put(f"/api/jobs/{assigned}/scorecard", json=tpl)).status_code == 200
    comp = (await client.get(f"/api/jobs/{assigned}/scorecard")).json()
    comp_id = (comp.get("scorecard") or comp)["competencies"][0]["id"]

    _sign_in_as(_user("iv"))
    assert (await client.put(f"/api/jobs/{assigned}/scorecard", json=tpl)).status_code == 403
    assert (await client.post(f"/api/jobs/{assigned}/candidates/cand-a/scorecards/requests", json={"uid": "hm"})).status_code == 403
    assert (await client.post(f"/api/jobs/{assigned}/candidates/cand-a/scorecards/brief")).status_code == 403
    card = {"ratings": [{"competency_id": comp_id, "rating": 3, "evidence": "Explained the join and the index choice well."}],
            "recommendation": "yes", "summary": "Good SQL.", "submit": True}
    assert (await client.put(f"/api/jobs/{assigned}/candidates/cand-a/scorecards/mine", json=card)).status_code == 200
    assert (await client.get(f"/api/jobs/{other}/candidates/cand-b/scorecards")).status_code == 404
