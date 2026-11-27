"""
Hiring reports (app/routes/reports.py) and status history (app/services/status_history.py).
"""
import csv
import io
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from bson import ObjectId

from tests.conftest import TEST_USER_UID, create_owned_job

NOW = datetime(2026, 11, 26, 12, 0, 0)


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def _h(*pairs):
    return [{"status": s, "at": at, "by": "u"} for s, at in pairs]


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


async def _workspace_job(mock_db, test_user, **fields):
    from app.org import ensure_org
    org_id = await ensure_org(test_user)
    return await create_owned_job(mock_db, org_id=org_id, **fields)


# ── Status history on every status path ─────────────────────────────────

class TestStatusHistory:
    async def test_new_application_starts_history(self, mock_db):
        from app.routes.resume import _create_application
        job_id = "a" * 24
        await mock_db.jobs.insert_one({"_id": ObjectId(job_id), "required_skills": ["Python"]})
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {"skills": "Python"}})
        scoring = {"skill_scores": [{"skill": "Python", "score": 8, "found": True, "evidence": {}}], "jd_match_score": 8}
        with patch("app.routes.resume.run_unified_skill_scoring", AsyncMock(return_value=scoring)):
            await _create_application("c1", job_id)
            await _create_application("c1", job_id)  # re-scoring doesn't add an entry
        app = await mock_db.applications.find_one({"candidate_id": "c1"})
        assert [e["status"] for e in app["status_history"]] == ["Under Review"]
        assert app["status_history"][0]["by"] is None

    async def test_status_endpoint_appends_once_per_change(self, client, mock_db, test_user):
        job_id = await _workspace_job(mock_db, test_user)
        await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": "c1", "status": "Under Review"})
        url = f"/api/v1/jobs/{job_id}/candidates/c1/status"
        assert (await client.put(url, json={"status": "Shortlisted"})).status_code == 200
        assert (await client.put(url, json={"status": "shortlisted"})).status_code == 200  # same status
        assert (await client.put(url, json={"status": "Rejected"})).status_code == 200
        app = await mock_db.applications.find_one({"candidate_id": "c1"})
        assert [e["status"] for e in app["status_history"]] == ["Shortlisted", "Rejected"]
        assert {e["by"] for e in app["status_history"]} == {TEST_USER_UID}
        assert app["status"] == "Rejected"
        missing = await client.put(f"/api/v1/jobs/{job_id}/candidates/nobody/status", json={"status": "Shortlisted"})
        assert missing.status_code == 404

    async def test_history_is_bounded(self, mock_db):
        from app.services.status_history import HISTORY_LIMIT, set_status
        await mock_db.applications.insert_one({"job_id": "j", "candidate_id": "c", "status": "Under Review"})
        for i in range(HISTORY_LIMIT + 5):
            await set_status("j", "c", "Shortlisted" if i % 2 else "Interview", "u")
        app = await mock_db.applications.find_one({"candidate_id": "c"})
        assert len(app["status_history"]) == HISTORY_LIMIT

    async def test_evaluation_moves_to_interview_with_history(self, client, mock_db, test_user):
        job_id = await _workspace_job(mock_db, test_user)
        await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": "c1", "status": "Shortlisted"})
        await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": "c2", "status": "Offer"})
        body = {"questions": [], "total_score": 50, "total_selected": 1, "total_possible": 2}
        r = await client.post(f"/api/jobs/{job_id}/candidates/c1/evaluation", json=body)
        assert r.json()["candidate_status"] == "Interview"
        r = await client.post(f"/api/jobs/{job_id}/candidates/c2/evaluation", json=body)
        assert r.json()["candidate_status"] is None  # later stages are left alone
        c1 = await mock_db.applications.find_one({"candidate_id": "c1"})
        c2 = await mock_db.applications.find_one({"candidate_id": "c2"})
        assert [e["status"] for e in c1["status_history"]] == ["Interview"]
        assert "status_history" not in c2 and c2["status"] == "Offer"


# ── Maths ───────────────────────────────────────────────────────────────

def _row(status, history=None, applied=None, job_id="j1", cid=None, **app):
    from app.routes.reports import app_row
    doc = {"job_id": job_id, "candidate_id": cid or f"c-{id(history)}-{status}", "status": status,
           "application_date": applied, **app}
    if history is not None:
        doc["status_history"] = history
    return app_row(doc, NOW)


class TestMaths:
    def test_median_and_p90(self):
        from app.routes.reports import percentile, summarize
        values = list(range(1, 11))  # 1..10
        assert percentile(values, 90) == 9
        assert percentile([5], 90) == 5
        assert percentile([], 90) is None
        assert summarize(values) == {"median_days": 5.5, "p90_days": 9, "count": 10}
        assert summarize([]) == {"median_days": None, "p90_days": None, "count": 0}

    def test_funnel_counts_and_conversion(self):
        from app.routes.reports import funnel
        rows = (
            [_row("Under Review", _h(("Under Review", _ago(5))), _ago(5), cid=f"u{i}") for i in range(6)]
            + [_row("Shortlisted", _h(("Under Review", _ago(9)), ("Shortlisted", _ago(4))), _ago(9), cid=f"s{i}") for i in range(2)]
            # rejected after the interview still counts as reaching Interview
            + [_row("Rejected", _h(("Under Review", _ago(9)), ("Shortlisted", _ago(6)), ("Interview", _ago(3)),
                                   ("Rejected", _ago(1))), _ago(9), cid="r1")]
            + [_row("Hired", _h(("Under Review", _ago(20)), ("Hired", _ago(2))), _ago(20), cid="h1")]
        )
        f = funnel(rows)
        stages = {s["stage"]: s for s in f["stages"]}
        assert stages["Under Review"]["current"] == 6 and stages["Under Review"]["reached"] == 10
        assert stages["Shortlisted"]["reached"] == 4  # 2 shortlisted + rejected + hired
        assert stages["Interview"]["reached"] == 2
        assert stages["Offer"]["reached"] == 1 and stages["Hired"]["reached"] == 1
        assert f["rejected"] == 1
        rates = {c["from"]: c["rate"] for c in f["conversions"]}
        assert rates == {"Under Review": 40.0, "Shortlisted": 50.0, "Interview": 50.0, "Offer": 100.0}
        assert f["biggest_drop"]["from"] == "Under Review"
        assert [c["biggest_drop"] for c in f["conversions"]] == [True, False, False, False]

    def test_biggest_drop_ignores_small_stages(self):
        from app.routes.reports import funnel
        rows = [_row("Under Review", cid=f"u{i}") for i in range(8)] + [_row("Shortlisted", cid=f"s{i}") for i in range(4)]
        f = funnel(rows)
        # Shortlisted -> Interview is 0% but only 4 candidates reached Shortlisted
        assert f["biggest_drop"]["from"] == "Under Review" and f["biggest_drop"]["rate"] == 33.3

    def test_empty_funnel_has_no_rates(self):
        from app.routes.reports import funnel
        f = funnel([])
        assert f["biggest_drop"] is None
        assert all(c["rate"] is None for c in f["conversions"])

    def test_time_in_stage_and_milestones(self):
        from app.routes.reports import milestones, time_in_stage
        rows = [
            _row("Interview", _h(("Under Review", _ago(10)), ("Shortlisted", _ago(8)), ("Interview", _ago(2))), _ago(10)),
            _row("Hired", _h(("Under Review", _ago(30)), ("Shortlisted", _ago(26)), ("Interview", _ago(20)),
                             ("Offer", _ago(15)), ("Hired", _ago(10))), _ago(30)),
            # legacy row without history: excluded from durations
            _row("Shortlisted", None, _ago(40), updated_at=_ago(1)),
        ]
        t = {s["stage"]: s for s in time_in_stage(rows)}
        assert t["Under Review"] == {"stage": "Under Review", "median_days": 3.0, "p90_days": 4.0, "count": 2}
        assert t["Shortlisted"]["median_days"] == 6.0 and t["Shortlisted"]["count"] == 2
        assert t["Interview"]["count"] == 1 and t["Offer"]["median_days"] == 5.0
        m = milestones(rows)
        assert m["first_review"]["median_days"] == 3.0
        assert m["shortlist"]["median_days"] == 3.0
        assert m["hire"] == {"median_days": 20.0, "p90_days": 20.0, "count": 1}

    def test_legacy_rows_are_partial_best_effort(self):
        r = _row("Shortlisted", None, _ago(40), updated_at=_ago(9))
        assert r["partial"] is True
        assert r["days_in_stage"] == 9.0
        assert _row("Under Review", None, _ago(12))["days_in_stage"] == 12.0

    def test_stuck_uses_threshold(self):
        from app.routes.reports import stuck
        rows = [
            _row("Shortlisted", _h(("Shortlisted", _ago(8))), cid="a"),
            _row("Shortlisted", _h(("Shortlisted", _ago(6))), cid="b"),
            _row("Under Review", _h(("Under Review", _ago(20))), cid="c"),
            _row("Hired", _h(("Hired", _ago(50))), cid="d"),        # final stages are never stuck
            _row("Rejected", _h(("Rejected", _ago(50))), cid="e"),
        ]
        assert [r["candidate_id"] for r in stuck(rows, 7)] == ["c", "a"]
        assert [r["candidate_id"] for r in stuck(rows, 5)] == ["c", "a", "b"]
        assert stuck(rows, 30) == []

    def test_stage_entry_is_latest_matching_entry(self):
        r = _row("Shortlisted", _h(("Shortlisted", _ago(30)), ("Interview", _ago(20)), ("Shortlisted", _ago(2))))
        assert r["days_in_stage"] == 2.0

    def test_overdue_feedback(self):
        from app.routes.reports import overdue_feedback
        rows = [
            _row("Interview", _h(("Interview", _ago(5))), cid="late"),
            _row("Interview", _h(("Interview", _ago(5))), cid="done"),
            _row("Interview", _h(("Interview", _ago(1))), cid="recent"),
        ]
        out = overdue_feedback(rows, {("j1", "done")}, 3)
        assert [r["candidate_id"] for r in out] == ["late"]

    def test_job_health_flags(self):
        from app.routes.reports import job_health, stuck
        jobs = [
            {"_id": "j1", "job_title": "Quiet", "status": "Active", "posted_at": _ago(60)},
            {"_id": "j2", "job_title": "Busy", "status": "Active", "posted_at": _ago(60)},
            {"_id": "j3", "job_title": "Closed old", "status": "Closed", "posted_at": _ago(90)},
            {"_id": "j4", "job_title": "Empty new", "is_active": True, "posted_at": _ago(3)},
            {"_id": "j5", "job_title": "Empty old", "is_active": True, "posted_at": _ago(30)},
        ]
        rows = [
            _row("Under Review", _h(("Under Review", _ago(20))), _ago(20), job_id="j1", cid="a"),
            _row("Shortlisted", _h(("Under Review", _ago(2)), ("Shortlisted", _ago(1))), _ago(2), job_id="j2", cid="b"),
            _row("Rejected", _h(("Under Review", _ago(3))), _ago(3), job_id="j2", cid="c"),
        ]
        health = {j["job_id"]: j for j in job_health(jobs, rows, stuck(rows, 7), [], NOW)}
        assert health["j1"]["no_new_candidates"] is True and health["j1"]["stuck"] == 1
        assert health["j2"]["no_new_candidates"] is False
        assert health["j2"]["shortlisted_pct"] == 50.0 and health["j2"]["candidates"] == 2
        assert health["j3"]["no_new_candidates"] is False  # closed jobs aren't flagged
        assert health["j4"]["no_new_candidates"] is False and health["j4"]["shortlisted_pct"] is None
        assert health["j5"]["no_new_candidates"] is True
        assert health["j1"]["open_days"] == 60
        assert health["j2"]["last_activity"] == _ago(1)

    def test_screening_null_is_not_zero(self):
        from app.routes.reports import screening
        rows = [
            _row("Under Review", cid="v1", score_details={"overall_score": 40, "score_source": "verified"}),
            _row("Under Review", cid="v2", score_details={"overall_score": 80, "score_source": "verified"}),
            # unverified candidates have no credibility: not counted as 0
            _row("Under Review", cid="u1", score_details={"overall_score": 0, "score_source": "unverified"}),
            _row("Under Review", cid="u2", score_details={}),
        ]
        verification = {
            "v1": {"verificationStatus": {"github": "verified", "discrepancies": [{"severity": "major"}]}},
            "v2": {"verificationStatus": {"discrepancies": [{"severity": "minor"}]}, "githubData": {"redFlags": []}},
            "u1": {"githubData": {"redFlags": ["Copied repository"]}},
        }
        s = screening(rows, verification, {"done": 6, "failed": 3, "verification_failed": 1},
                      [{"status": "failed", "error": "Could not parse this resume (TimeoutError). Reading the file took too long", "count": 2},
                       {"status": "failed", "error": "Worker stopped responding 3 times", "count": 1},
                       {"status": "verification_failed", "error": "boom", "count": 1}])
        assert s["scored"] == 2 and s["low_credibility"] == 1 and s["low_credibility_pct"] == 50.0
        assert s["red_flags"] == 2 and s["red_flags_pct"] == 50.0
        assert s["verification_sources"]["github"] == {"verified": 1, "pending": 3}
        assert s["tasks_total"] == 10 and s["tasks_failed"] == 4 and s["tasks_failed_pct"] == 40.0
        assert s["verification_failures"] == 1
        assert {r["reason"]: r["count"] for r in s["failure_reasons"]} == {
            "Timed out reading the file": 2, "Processing interrupted": 1, "Verification failed": 1}
        empty = screening([], {}, {}, [])
        assert empty["low_credibility_pct"] is None and empty["tasks_failed_pct"] is None


# ── Pain points ─────────────────────────────────────────────────────────

def _report(**over):
    from app.routes.reports import funnel, milestones, screening
    base = {
        "filters": {"job_id": None},
        "funnel": funnel([]),
        "jobs": [],
        "screening": screening([], {}, {}, []),
        "milestones": milestones([]),
        "ai_usage": {"ai_call": {"used": 10, "limit": 300, "label": "AI calls"}},
    }
    base.update(over)
    return base


class TestPainPoints:
    def test_nothing_wrong_means_no_items(self):
        from app.routes.reports import pain_points
        assert pain_points(_report(), [], [], 7, 3) == []

    def test_stuck_severity_title_and_link(self):
        from app.routes.reports import pain_points, stuck
        rows = [_row("Shortlisted", _h(("Shortlisted", _ago(9))), cid=f"s{i}") for i in range(12)] \
            + [_row("Under Review", _h(("Under Review", _ago(9))), job_id="j2", cid="u1")] \
            + [_row("Interview", _h(("Interview", _ago(9))), job_id=j, cid=f"i{j}") for j in ("j1", "j2", "j3")]
        items = pain_points(_report(), stuck(rows, 7), [], 7, 3)
        by_id = {i["id"]: i for i in items}
        assert by_id["stuck-shortlisted"]["severity"] == "high"
        assert by_id["stuck-shortlisted"]["title"] == "12 candidates stuck in Shortlisted for over 7 days"
        assert by_id["stuck-shortlisted"]["link"] == {"job_id": "j1", "status": "Shortlisted", "section": "stuck"}
        assert by_id["stuck-interview"]["severity"] == "medium" and by_id["stuck-interview"]["link"]["job_id"] is None
        assert by_id["stuck-under-review"]["severity"] == "low"
        assert by_id["stuck-under-review"]["title"] == "1 candidate stuck in Under Review for over 7 days"
        assert [i["severity"] for i in items] == ["high", "medium", "low"]  # most severe first
        assert all(i["suggestion"] for i in items)

    def test_other_rules(self):
        from app.routes.reports import funnel, pain_points, screening
        rows = [_row("Under Review", cid=f"u{i}") for i in range(19)] + [_row("Shortlisted", cid="s")]
        scr = screening(
            [_row("Under Review", cid=f"v{i}", score_details={"overall_score": 30 if i < 3 else 90}) for i in range(6)],
            {"v0": {"githubData": {"redFlags": ["x"]}}}, {"done": 7, "failed": 3}, [])
        report = _report(
            funnel=funnel(rows), screening=scr,
            jobs=[{"job_id": "q1", "no_new_candidates": True}],
            ai_usage={"ai_call": {"used": 300, "limit": 300, "label": "AI calls"},
                      "resume_upload": {"used": 400, "limit": 500, "label": "resume uploads"}},
        )
        overdue = [_row("Interview", cid=f"o{i}") for i in range(5)]
        items = {i["id"]: i for i in pain_points(report, [], overdue, 7, 3)}
        assert items["drop-off"]["severity"] == "medium" and items["drop-off"]["metric"] == 5.0
        assert items["drop-off"]["title"] == "Only 5% of candidates move from Under Review to Shortlisted"
        assert items["overdue-feedback"]["severity"] == "high"
        assert items["overdue-feedback"]["title"] == "5 interviews with no feedback after 3 days"
        assert items["no-new-candidates"]["link"]["job_id"] == "q1"
        assert items["no-new-candidates"]["title"] == "1 active job has had no new candidates for 14 days"
        assert items["low-credibility"]["metric"] == 50.0
        assert items["red-flags"]["severity"] == "low"
        assert items["processing-failures"]["severity"] == "high"
        assert items["processing-failures"]["title"] == "3 of 10 resume uploads failed (30%)"
        assert items["quota-ai_call"]["severity"] == "high"
        assert items["quota-resume_upload"]["severity"] == "medium"

    def test_small_samples_are_not_flagged(self):
        from app.routes.reports import funnel, pain_points, screening
        rows = [_row("Under Review", cid=f"u{i}") for i in range(5)]
        scr = screening([_row("Under Review", cid="v", score_details={"overall_score": 10})], {}, {"failed": 2}, [])
        ids = {i["id"] for i in pain_points(_report(funnel=funnel(rows), screening=scr), [], [], 7, 3)}
        assert ids == set()


# ── CSV ─────────────────────────────────────────────────────────────────

class TestCsv:
    def test_formula_injection_guard(self):
        from app.routes.reports import safe_cell
        for bad in ("=HYPERLINK(\"x\")", "+1", "-2+3", "@SUM(A1)", "\tx", "\rx"):
            assert safe_cell(bad) == "'" + bad
        assert safe_cell("Jane Doe") == "Jane Doe"
        assert safe_cell(-5) == "-5"  # numbers stay numbers
        assert safe_cell(None) == ""
        assert safe_cell(True) == "yes"

    def test_escaping_round_trips(self):
        from app.routes.reports import to_csv
        text = to_csv(["Name", "Note"], [['Doe, "Jane"', "line1\nline2"], ["=cmd", None]])
        rows = list(csv.reader(io.StringIO(text)))
        assert rows == [["Name", "Note"], ['Doe, "Jane"', "line1\nline2"], ["'=cmd", ""]]


# ── Routes: access, isolation, export ───────────────────────────────────

class TestRoutes:
    async def _seed(self, mock_db, test_user):
        job_id = await _workspace_job(mock_db, test_user, job_title="Backend engineer", status="Active")
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {"personal_info": {"full_name": "=Sam Example"}}})
        await mock_db.applications.insert_one({
            "job_id": job_id, "candidate_id": "c1", "status": "Shortlisted",
            "application_date": datetime.utcnow() - timedelta(days=20),
            "status_history": _h(("Under Review", datetime.utcnow() - timedelta(days=20)),
                                 ("Shortlisted", datetime.utcnow() - timedelta(days=10))),
            "score_details": {"overall_score": 70, "score_source": "verified"},
        })
        await mock_db.applications.insert_one({  # legacy: no history
            "job_id": job_id, "candidate_id": "c2", "status": "Under Review",
            "application_date": datetime.utcnow() - timedelta(days=1),
        })
        await mock_db.tasks.insert_many([
            {"task_id": "t1", "job_id": job_id, "status": "done", "created_at": datetime.utcnow()},
            {"task_id": "t2", "job_id": job_id, "status": "failed", "created_at": datetime.utcnow(),
             "error": "Could not parse this resume (ValueError). Check the file opens normally, then re-upload it."},
        ])
        return job_id

    async def test_overview(self, client, mock_db, test_user):
        job_id = await self._seed(mock_db, test_user)
        r = await client.get("/api/reports/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["totals"] == {"jobs": 1, "candidates": 2}
        assert data["partial_data"] is True and data["partial_count"] == 1
        assert data["stuck"]["count"] == 1
        assert data["stuck"]["candidates"][0]["name"] == "=Sam Example"
        assert data["stuck"]["candidates"][0]["job_id"] == job_id
        assert data["screening"]["tasks_failed"] == 1
        assert data["screening"]["failure_reasons"] == [{"reason": "Could not parse the resume", "count": 1}]
        assert data["ai_usage"]["ai_call"]["limit"] > 0
        assert data["pain_points"][0]["id"] == "stuck-shortlisted"
        # threshold and job filter
        assert (await client.get("/api/reports/overview?stuck_days=15")).json()["stuck"]["count"] == 0
        assert (await client.get(f"/api/reports/overview?job_id={job_id}")).json()["totals"]["jobs"] == 1
        # date range filters on application date
        since = (datetime.utcnow() - timedelta(days=5)).date().isoformat()
        assert (await client.get(f"/api/reports/overview?from={since}")).json()["totals"]["candidates"] == 1
        until = (datetime.utcnow() - timedelta(days=5)).date().isoformat()
        assert (await client.get(f"/api/reports/overview?to={until}")).json()["totals"]["candidates"] == 1
        assert (await client.get("/api/reports/overview?stuck_days=0")).status_code == 422

    async def test_workspace_isolation(self, client, mock_db, test_user):
        from app.auth import AuthUser
        job_id = await self._seed(mock_db, test_user)
        _sign_in_as(AuthUser(uid="other", email="other@example.com"))
        data = (await client.get("/api/reports/overview")).json()
        assert data["totals"] == {"jobs": 0, "candidates": 0}
        assert data["stuck"]["candidates"] == [] and data["screening"]["tasks_total"] == 0
        assert (await client.get(f"/api/reports/overview?job_id={job_id}")).status_code == 404
        assert (await client.get("/api/reports/overview?job_id=not-an-id")).status_code == 404
        r = await client.get(f"/api/reports/export.csv?report=stuck&job_id={job_id}")
        assert r.status_code == 404

    async def test_api_keys_rejected(self, client, mock_db, test_user):
        from app.auth import AuthUser
        from app.org import ensure_org
        org_id = await ensure_org(test_user)
        _sign_in_as(AuthUser(uid=TEST_USER_UID, provider="api_key", org_id=org_id))
        assert (await client.get("/api/reports/overview")).status_code == 403
        assert (await client.get("/api/reports/export.csv?report=jobs")).status_code == 403

    async def test_requires_sign_in(self, anon_client):
        assert (await anon_client.get("/api/reports/overview")).status_code == 401

    async def test_csv_exports(self, client, mock_db, test_user):
        await self._seed(mock_db, test_user)
        r = await client.get("/api/reports/export.csv?report=stuck")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers["content-disposition"]
        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0][:3] == ["Job", "Candidate", "Stage"]
        assert rows[1][1] == "'=Sam Example"  # formula guard on candidate text
        jobs = list(csv.reader(io.StringIO((await client.get("/api/reports/export.csv?report=jobs")).text)))
        assert jobs[1][0] == "Backend engineer" and jobs[1][3] == "2"
        funnel = list(csv.reader(io.StringIO((await client.get("/api/reports/export.csv?report=funnel")).text)))
        assert [r[0] for r in funnel[1:]] == ["Under Review", "Shortlisted", "Interview", "Offer", "Hired", "Rejected"]
        assert (await client.get("/api/reports/export.csv?report=secrets")).status_code == 422


async def test_restricted_roles_see_only_assigned_jobs(client, mock_db):
    from tests.test_rbac import _sign_in_as, _user, _workspace
    _, assigned, other = await _workspace(client, mock_db)
    _sign_in_as(_user("iv"))
    data = (await client.get("/api/reports/overview")).json()
    assert data["totals"]["jobs"] == 1
    assert (await client.get(f"/api/reports/overview?job_id={other}")).status_code == 404
    assert (await client.get(f"/api/reports/overview?job_id={assigned}")).status_code == 200
