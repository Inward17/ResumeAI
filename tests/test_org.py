"""
Workspaces, invitations and API keys (app/org.py, app/routes/org_routes.py).
"""
from unittest.mock import AsyncMock, patch

from tests.conftest import create_owned_job


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


class TestInvites:
    async def test_invited_person_joins_and_sees_shared_jobs(self, client, mock_db, test_user):
        from app.auth import AuthUser
        job_id = await create_owned_job(mock_db, job_title="Shared role")

        with patch("app.routes.org_routes.send_invite_email", AsyncMock(return_value="not configured")):
            resp = await client.post("/api/org/invites", json={"email": "Friend@Example.com", "role": "member"})
        assert resp.status_code == 200
        invite = resp.json()
        assert invite["email"] == "friend@example.com" and invite["email_sent"] is False
        token = invite["join_url"].rsplit("/", 1)[1]

        # Someone else holding the link can't use it
        _sign_in_as(AuthUser(uid="stranger", email="stranger@example.com"))
        assert (await client.post(f"/api/invites/{token}/accept")).status_code == 403

        _sign_in_as(AuthUser(uid="friend", email="friend@example.com", name="Friend"))
        assert (await client.post(f"/api/invites/{token}/accept")).status_code == 200
        assert [j["id"] for j in (await client.get("/api/jobs")).json()] == [job_id]
        assert (await client.post(f"/api/invites/{token}/accept")).status_code == 404  # single use

        # Members can't invite; the owner sees both people
        assert (await client.post("/api/org/invites", json={"email": "x@example.com"})).status_code == 403
        _sign_in_as(test_user)
        roles = {m["uid"]: m["role"] for m in (await client.get("/api/org")).json()["members"]}
        assert roles == {"test-user": "owner", "friend": "member"}

    async def test_removed_member_loses_access(self, client, mock_db, test_user):
        from app.auth import AuthUser
        job_id = await create_owned_job(mock_db)
        await client.get("/api/org")  # creates the owner's workspace
        org_id = (await mock_db.users.find_one({"uid": "test-user"}))["org_id"]
        await mock_db.org_members.insert_one({"org_id": org_id, "uid": "m2", "email": "m2@example.com", "role": "member"})
        await mock_db.users.insert_one({"uid": "m2", "org_id": org_id})

        assert (await client.delete("/api/org/members/m2")).status_code == 200
        _sign_in_as(AuthUser(uid="m2", email="m2@example.com"))
        assert (await client.get(f"/api/jobs/{job_id}")).status_code == 404


class TestApiKeys:
    async def test_key_authenticates_until_revoked(self, client, anon_client, mock_db, test_user):
        from app.main import app
        from app.auth import get_current_user
        job_id = await create_owned_job(mock_db)
        created = (await client.post("/api/org/api-keys", json={"name": "ATS sync"})).json()
        assert created["key"].startswith("rai_")
        stored = await mock_db.api_keys.find_one({})
        assert created["key"] not in str(stored)  # only the hash is kept

        headers = {"Authorization": f"Bearer {created['key']}"}
        with patch("app.auth.AUTH_DISABLED", False):
            # Both clients share the app, so drop the signed-in override for key-only requests
            app.dependency_overrides.pop(get_current_user)
            resp = await anon_client.get("/api/jobs", headers=headers)
            assert resp.status_code == 200 and [j["id"] for j in resp.json()] == [job_id]
            assert (await anon_client.get("/api/jobs", headers={"Authorization": "Bearer rai_wrong"})).status_code == 401

            _sign_in_as(test_user)
            assert (await client.delete(f"/api/org/api-keys/{created['id']}")).status_code == 200
            app.dependency_overrides.pop(get_current_user)
            assert (await anon_client.get("/api/jobs", headers=headers)).status_code == 401
