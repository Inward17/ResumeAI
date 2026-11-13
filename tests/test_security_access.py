"""
Regression tests for the access-control findings of the 2026-11-13 security review:
cross-workspace candidates (1), API keys after removal (5), invite email HTML (6),
unverified invite emails (7) and the sign-up allow-list (3).
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from tests.conftest import create_owned_job
from tests.test_auth import firebase_auth, make_token, signing_material  # noqa: F401 (fixtures)


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


def _sign_out():
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides.pop(get_current_user, None)


# ── Finding 1: a candidate who never applied to the job ─────────────────

class TestCandidateMustHaveApplied:
    async def test_interview_questions_for_unapplied_candidate_is_404(self, client, mock_db, owned_job_id):
        other_job = await create_owned_job(mock_db, owner_uid="someone-else")
        await mock_db.applications.insert_one({"job_id": other_job, "candidate_id": "theirs"})
        await mock_db.candidates.insert_one({"candidate_id": "theirs", "parsed": {}})
        gen = AsyncMock(return_value=[{"question": "Q"}])
        with patch("app.routes.interview_questions_routes.generate_interview_questions", gen):
            resp = await client.get(f"/api/jobs/{owned_job_id}/candidates/theirs/interview-questions")
        assert resp.status_code == 404
        gen.assert_not_called()  # their resume never reaches the model
        assert await mock_db.applications.count_documents({"job_id": owned_job_id}) == 0  # no link created

    async def test_interview_questions_cache_on_existing_application(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"job_id": owned_job_id, "candidate_id": "c1"})
        await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {}})
        gen = AsyncMock(return_value=[{"question": "Q"}])
        with patch("app.routes.interview_questions_routes.generate_interview_questions", gen):
            resp = await client.get(f"/api/jobs/{owned_job_id}/candidates/c1/interview-questions")
        assert resp.status_code == 200
        assert (await mock_db.applications.find_one({"candidate_id": "c1"}))["interview_questions"] == [{"question": "Q"}]
        assert await mock_db.applications.count_documents({}) == 1

    async def test_evaluation_for_unapplied_candidate_is_404(self, client, mock_db, owned_job_id):
        body = {"questions": [], "total_score": 0, "total_selected": 0, "total_possible": 0}
        resp = await client.post(f"/api/jobs/{owned_job_id}/candidates/nobody/evaluation", json=body)
        assert resp.status_code == 404
        assert await mock_db.evaluations.count_documents({}) == 0
        assert (await client.get(f"/api/jobs/{owned_job_id}/candidates/nobody/evaluation")).status_code == 404


# ── Finding 5: workspace API keys ───────────────────────────────────────

async def _member_key(client, mock_db, test_user):
    """An admin member 'm2' of the test user's workspace, with an API key they created."""
    from app.auth import AuthUser
    await client.get("/api/org")
    org_id = (await mock_db.users.find_one({"uid": test_user.uid}))["org_id"]
    await mock_db.org_members.insert_one({"org_id": org_id, "uid": "m2", "email": "m2@example.com", "role": "admin"})
    await mock_db.users.insert_one({"uid": "m2", "org_id": org_id})
    _sign_in_as(AuthUser(uid="m2", email="m2@example.com"))
    key = (await client.post("/api/org/api-keys", json={"name": "sync"})).json()
    return {"Authorization": f"Bearer {key['key']}"}


class TestApiKeys:
    async def test_key_dies_when_creator_leaves(self, client, anon_client, mock_db, test_user):
        headers = await _member_key(client, mock_db, test_user)
        _sign_out()
        with patch("app.auth.AUTH_DISABLED", False):
            assert (await anon_client.get("/api/jobs", headers=headers)).status_code == 200
            # Membership row gone without the remove route (e.g. edited by hand): still rejected
            await mock_db.org_members.delete_one({"uid": "m2"})
            assert (await anon_client.get("/api/jobs", headers=headers)).status_code == 401

    async def test_remove_member_revokes_their_keys(self, client, mock_db, test_user):
        await _member_key(client, mock_db, test_user)
        _sign_in_as(test_user)
        assert (await client.delete("/api/org/members/m2")).status_code == 200
        assert await mock_db.api_keys.count_documents({"created_by": "m2", "revoked_at": None}) == 0

    async def test_key_cannot_manage_workspace(self, client, anon_client, mock_db, test_user):
        headers = await _member_key(client, mock_db, test_user)
        _sign_out()
        with patch("app.auth.AUTH_DISABLED", False):
            for method, path, body in [
                ("get", "/api/org", None),
                ("patch", "/api/org", {"name": "Pwned"}),
                ("patch", f"/api/org/members/{test_user.uid}", {"role": "member"}),
                ("delete", f"/api/org/members/{test_user.uid}", None),
                ("post", "/api/org/invites", {"email": "x@example.com"}),
                ("get", "/api/org/api-keys", None),
                ("post", "/api/org/api-keys", {"name": "another"}),
                ("post", "/api/invites/some-token/accept", None),
            ]:
                resp = await anon_client.request(method, path, json=body, headers=headers)
                assert resp.status_code == 403, (method, path, resp.status_code)


# ── Findings 6 and 7: invitations ───────────────────────────────────────

class TestInviteEmail:
    async def test_names_are_escaped_and_subject_is_one_line(self):
        from app import org
        resp = MagicMock(status_code=200, content=b"{}")
        resp.json.return_value = {"successful": True}
        http = MagicMock()
        http.__aenter__ = AsyncMock(return_value=http)
        http.__aexit__ = AsyncMock(return_value=False)
        http.post = AsyncMock(return_value=resp)
        with patch.object(org, "COMPOSIO_API_KEY", "test"), patch.object(org.httpx, "AsyncClient", return_value=http):
            err = await org.send_invite_email("a@example.com", '<a href="//evil">Reset</a>', "Eve\r\nBcc: x@example.com",
                                              "http://localhost:3000/join/t")
        assert err is None
        args = http.post.call_args.kwargs["json"]["arguments"]
        assert "<a href=\"//evil\">" not in args["body"] and "&lt;a href=" in args["body"]
        assert "\r" not in args["subject"] and "\n" not in args["subject"]


class TestInviteNeedsVerifiedEmail:
    async def test_unverified_address_cannot_accept(self, client, mock_db):
        from app.auth import AuthUser
        with patch("app.routes.org_routes.send_invite_email", AsyncMock(return_value="not configured")):
            invite = (await client.post("/api/org/invites", json={"email": "friend@example.com"})).json()
        token = invite["join_url"].rsplit("/", 1)[1]

        _sign_in_as(AuthUser(uid="friend", email="friend@example.com", email_verified=False))
        assert (await client.get(f"/api/invites/{token}")).json()["email_matches"] is False
        assert (await client.post(f"/api/invites/{token}/accept")).status_code == 403

        _sign_in_as(AuthUser(uid="friend", email="friend@example.com", email_verified=True))
        assert (await client.get(f"/api/invites/{token}")).json()["email_matches"] is True
        assert (await client.post(f"/api/invites/{token}/accept")).status_code == 200

    async def test_token_claim_sets_email_verified(self, firebase_auth, signing_material):
        from app.auth import verify_id_token
        assert (await verify_id_token(make_token(signing_material[0], email_verified=True))).email_verified is True
        assert (await verify_id_token(make_token(signing_material[0]))).email_verified is False


# ── Finding 3: sign-up allow-list ───────────────────────────────────────

class TestAllowList:
    @pytest.fixture
    def allow_team(self):
        with patch("app.auth.ALLOWED_EMAIL_DOMAINS", {"team.example.com"}), \
             patch("app.auth.ALLOWED_EMAILS", {"contractor@example.org"}):
            yield

    async def _check(self, **user):
        from app.auth import AuthUser, require_allowed_email
        await require_allowed_email(AuthUser(uid=user.pop("uid", "u1"), **user))

    async def test_unset_lists_keep_sign_up_open(self):
        await self._check(email="anyone@example.net")

    async def test_listed_verified_emails_get_in(self, allow_team):
        await self._check(email="Ann@Team.example.com", email_verified=True)
        await self._check(email="contractor@example.org", email_verified=True)

    async def test_others_and_unverified_are_rejected(self, allow_team):
        for user in ({"email": "x@example.net", "email_verified": True},
                     {"email": "ann@team.example.com", "email_verified": False},
                     {"email": "x@team.example.com.evil.net", "email_verified": True}):
            with pytest.raises(HTTPException) as exc:
                await self._check(**user)
            assert exc.value.status_code == 403

    async def test_members_and_invited_people_get_in(self, allow_team, mock_db):
        await mock_db.org_members.insert_one({"org_id": "o1", "uid": "member-uid", "role": "member"})
        await self._check(uid="member-uid", email="member@example.net")
        await mock_db.invites.insert_one({"email": "guest@example.net", "status": "pending",
                                          "expires_at": datetime.utcnow() + timedelta(days=1)})
        await self._check(email="guest@example.net", email_verified=True)
        with pytest.raises(HTTPException):  # an invite needs the address to be verified
            await self._check(email="guest@example.net", email_verified=False)

    async def test_enforced_on_real_tokens(self, allow_team, anon_client, firebase_auth, signing_material):
        signer = signing_material[0]
        outsider = make_token(signer, email="x@example.net", email_verified=True)
        insider = make_token(signer, email="ann@team.example.com", email_verified=True)
        assert (await anon_client.get("/api/jobs", headers={"Authorization": f"Bearer {outsider}"})).status_code == 403
        assert (await anon_client.get("/api/jobs", headers={"Authorization": f"Bearer {insider}"})).status_code == 200
