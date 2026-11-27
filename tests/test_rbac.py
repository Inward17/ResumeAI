"""
Roles and permissions (app/org.py PERMISSIONS, app/auth.py require_job_action, job hiring teams).
"""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import TEST_USER_UID, create_owned_job


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


async def _workspace(client, mock_db):
    """Owner's workspace with a hiring manager, an interviewer and a recruiter; two jobs and one candidate each."""
    assigned = await create_owned_job(mock_db, job_title="Assigned")
    other = await create_owned_job(mock_db, job_title="Other")
    await client.get("/api/org")  # creates the owner's workspace and moves the jobs into it
    org_id = (await mock_db.users.find_one({"uid": TEST_USER_UID}))["org_id"]
    for uid, role in (("hm", "hiring_manager"), ("iv", "interviewer"), ("rec", "member")):
        await mock_db.org_members.insert_one({"org_id": org_id, "uid": uid, "email": f"{uid}@example.com", "role": role})
        await mock_db.users.insert_one({"uid": uid, "org_id": org_id})
    for job_id, cid in ((assigned, "cand-a"), (other, "cand-b")):
        await mock_db.applications.insert_one({"job_id": job_id, "candidate_id": cid, "status": "Under Review"})
        await mock_db.candidates.insert_one({"candidate_id": cid, "parsed": {"personal_info": {"full_name": cid}}})
    assert (await client.put(f"/api/jobs/{assigned}/team", json={"team_uids": ["hm", "iv"]})).status_code == 200
    return org_id, assigned, other


def _user(uid):
    from app.auth import AuthUser
    return AuthUser(uid=uid, email=f"{uid}@example.com", name=uid)


class TestPermissionTable:
    def test_table(self):
        from app.org import PERMISSIONS, ROLES, can
        assert set(PERMISSIONS) == set(ROLES)
        for role in ("owner", "admin", "member"):
            assert PERMISSIONS[role] == PERMISSIONS["owner"]
        assert can("hiring_manager", "candidate.status") and can("hiring_manager", "ai.run")
        assert not can("hiring_manager", "candidate.upload") and not can("hiring_manager", "job.assign_team")
        for action in ("candidate.view", "interview.questions", "evaluation.write", "fact_check"):
            assert can("interviewer", action)
        for action in ("candidate.status", "ai.run", "candidate.upload", "candidate.verify", "job.create", "job.delete"):
            assert not can("interviewer", action)
        assert not can("nonsense", "candidate.view")


@pytest.mark.parametrize("uid", ["hm", "iv"])
class TestRestrictedRoles:
    async def test_unassigned_job_is_invisible(self, client, mock_db, uid):
        _, assigned, other = await _workspace(client, mock_db)
        _sign_in_as(_user(uid))
        assert [j["id"] for j in (await client.get("/api/jobs")).json()] == [assigned]
        assert (await client.get(f"/api/jobs/{other}")).status_code == 404
        assert (await client.get(f"/api/v1/jobs/{other}/candidates")).status_code == 404
        assert (await client.get(f"/api/v1/jobs/{other}/tasks")).status_code == 404
        assert (await client.put(f"/api/v1/jobs/{other}/candidates/cand-b/status", json={"status": "Shortlisted"})).status_code == 404
        assert (await client.post(f"/api/v1/jobs/{other}/upload", files={"files": ("a.txt", b"x")})).status_code == 404
        assert (await client.delete(f"/api/jobs/{other}")).status_code == 404
        assert (await client.get(f"/api/v1/verification/verification-status/cand-b")).status_code == 404
        assert (await client.post("/api/fact-checker/cand-b", json={"message": "hi"})).status_code == 404
        assert (await client.get(f"/api/jobs/{other}/candidates/cand-b/evaluation")).status_code == 404

    async def test_assigned_job_follows_the_table(self, client, mock_db, uid):
        _, assigned, _ = await _workspace(client, mock_db)
        _sign_in_as(_user(uid))
        assert (await client.get(f"/api/jobs/{assigned}")).status_code == 200
        cands = (await client.get(f"/api/v1/jobs/{assigned}/candidates")).json()["candidates"]
        assert [c["candidate_id"] for c in cands] == ["cand-a"]
        assert (await client.get("/api/v1/verification/verification-status/cand-a")).status_code == 200

        # Recruiter-only actions
        assert (await client.post(f"/api/v1/jobs/{assigned}/upload", files={"files": ("a.txt", b"x")})).status_code == 403
        assert (await client.delete(f"/api/jobs/{assigned}")).status_code == 403
        assert (await client.put(f"/api/jobs/{assigned}", json={"job_title": "X"})).status_code == 403
        assert (await client.put(f"/api/jobs/{assigned}/team", json={"team_uids": []})).status_code == 403
        assert (await client.post("/api/jobs", json={"job_title": "X", "job_description": "Y", "required_skills": []})).status_code == 403
        assert (await client.post(f"/api/v1/jobs/{assigned}/candidates/cand-a/cover-letter", json={"text": "hi"})).status_code == 403

        # Evaluations are open to every role on an assigned job
        evaluation = {"questions": [], "total_score": 50, "total_selected": 1, "total_possible": 2}
        assert (await client.post(f"/api/jobs/{assigned}/candidates/cand-a/evaluation", json=evaluation)).status_code == 200

        status = await client.put(f"/api/v1/jobs/{assigned}/candidates/cand-a/status", json={"status": "Shortlisted"})
        retry = await client.post(f"/api/v1/jobs/{assigned}/candidates/cand-a/project-reviews?retry=true")
        if uid == "hm":
            assert status.status_code == 200
            assert retry.status_code != 403  # allowed; fails later for lack of a review to retry
        else:
            assert status.status_code == 403 and "Interviewer" in status.json()["detail"]
            assert retry.status_code == 403

    async def test_usage_counts_only_assigned_jobs(self, client, mock_db, uid):
        await _workspace(client, mock_db)
        _sign_in_as(_user(uid))
        workspace = (await client.get("/api/org/usage")).json()["workspace"]
        assert workspace["jobs"] == 1 and workspace["candidates_total"] == 1

    async def test_permissions_in_org(self, client, mock_db, uid):
        await _workspace(client, mock_db)
        _sign_in_as(_user(uid))
        perms = (await client.get("/api/org")).json()["permissions"]
        assert "candidate.view" in perms and "candidate.upload" not in perms
        assert ("candidate.status" in perms) == (uid == "hm")


class TestTeamsAndRoles:
    async def test_recruiter_sees_everything_and_assigns(self, client, mock_db):
        _, assigned, other = await _workspace(client, mock_db)
        _sign_in_as(_user("rec"))
        assert {j["id"] for j in (await client.get("/api/jobs")).json()} == {assigned, other}
        resp = await client.put(f"/api/jobs/{other}/team", json={"team_uids": ["iv", "iv"]})
        assert resp.status_code == 200 and resp.json()["team_uids"] == ["iv"]

    async def test_team_rejects_non_members(self, client, mock_db):
        _, assigned, _ = await _workspace(client, mock_db)
        resp = await client.put(f"/api/jobs/{assigned}/team", json={"team_uids": ["hm", "stranger"]})
        assert resp.status_code == 400
        assert (await mock_db.jobs.find_one({"job_title": "Assigned"}))["team_uids"] == ["hm", "iv"]

    async def test_removed_member_leaves_teams(self, client, mock_db):
        _, assigned, _ = await _workspace(client, mock_db)
        assert (await client.delete("/api/org/members/hm")).status_code == 200
        assert (await mock_db.jobs.find_one({"job_title": "Assigned"}))["team_uids"] == ["iv"]

    async def test_only_managers_change_roles(self, client, mock_db):
        await _workspace(client, mock_db)
        assert (await client.patch("/api/org/members/iv", json={"role": "hiring_manager"})).status_code == 200
        assert (await client.patch("/api/org/members/iv", json={"role": "owner"})).status_code == 422
        for uid in ("rec", "hm"):
            _sign_in_as(_user(uid))
            assert (await client.patch("/api/org/members/iv", json={"role": "admin"})).status_code == 403
            assert (await client.post("/api/org/invites", json={"email": "n@example.com", "role": "interviewer"})).status_code == 403

    async def test_invite_with_new_role(self, client, mock_db):
        await _workspace(client, mock_db)
        with patch("app.routes.org_routes.send_invite_email", AsyncMock(return_value=None)):
            resp = await client.post("/api/org/invites", json={"email": "n@example.com", "role": "interviewer"})
        assert resp.status_code == 200 and resp.json()["role"] == "interviewer"


class TestApiKeys:
    async def test_key_keeps_recruiter_rights_even_if_creator_is_restricted(self, client, anon_client, mock_db):
        from app.main import app
        from app.auth import get_current_user
        org_id, assigned, other = await _workspace(client, mock_db)
        created = (await client.post("/api/org/api-keys", json={"name": "ATS"})).json()
        # The creator becomes an interviewer: the key still acts as a Recruiter (documented in SECURITY.md)
        await mock_db.org_members.update_one({"uid": TEST_USER_UID}, {"$set": {"role": "interviewer"}})
        headers = {"Authorization": f"Bearer {created['key']}"}
        with patch("app.auth.AUTH_DISABLED", False):
            app.dependency_overrides.pop(get_current_user)
            resp = await anon_client.get("/api/jobs", headers=headers)
            assert {j["id"] for j in resp.json()} == {assigned, other}
            resp = await anon_client.put(f"/api/v1/jobs/{other}/candidates/cand-b/status",
                                         json={"status": "Shortlisted"}, headers=headers)
            assert resp.status_code == 200
