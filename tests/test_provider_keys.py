"""
Settings > AI and Integrations: per-workspace provider keys (app/services/provider_keys.py),
per-feature AI usage and history (app/services/quota.py, GET /api/org/ai-usage).
All provider HTTP calls go to an httpx.MockTransport.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

PROVIDER_ENVS = ("GEMINI_API_KEY", "GROQ_API_KEY", "FIRECRAWL_API_KEY", "GITHUB_TOKEN", "APIFY_TOKEN", "COMPOSIO_API_KEY")
WS_KEY = "ws-key-1234567890-abcd"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """A valid secret and server keys that are clearly not the workspace's."""
    monkeypatch.setenv("PROVIDER_KEYS_SECRET", Fernet.generate_key().decode())
    for name in PROVIDER_ENVS:
        monkeypatch.setenv(name, f"server-{name.lower()}")


@pytest.fixture()
def calls():
    return []


@pytest.fixture()
def provider_http(calls):
    """Route every usage_service request to a fake provider that accepts any key except 'bad-…'."""
    def handler(request: httpx.Request):
        calls.append(request)
        auth = request.headers.get("authorization", "") + request.headers.get("x-goog-api-key", "") + request.headers.get("x-api-key", "")
        if "bad-" in auth:
            return httpx.Response(401, json={})
        if "groq.com" in request.url.host:
            from app.services.interview_questions_service import GROQ_MODEL
            return httpx.Response(200, json={"data": [{"id": GROQ_MODEL}]})
        if "github.com" in request.url.host:
            res = {"core": {"used": 1, "limit": 5000, "reset": 0}, "search": {}}
            return httpx.Response(200, json={"resources": res})
        return httpx.Response(200, json={"data": {}, "items": []})

    real = httpx.AsyncClient
    with patch("app.services.usage_service.httpx.AsyncClient",
               lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
        yield


async def _org_id(client, mock_db):
    await client.get("/api/org")  # creates the signed-in user's workspace
    return (await mock_db.users.find_one({"uid": "test-user"}))["org_id"]


def _sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


class TestKeyStorage:
    async def test_encryption_round_trip(self):
        from app.services import provider_keys
        token = provider_keys.encrypt(WS_KEY)
        assert WS_KEY not in token and provider_keys.decrypt(token) == WS_KEY

    async def test_saved_key_is_never_returned(self, client, mock_db, provider_http):
        resp = await client.put("/api/org/integrations/groq", json={"key": WS_KEY})
        assert resp.status_code == 200 and resp.json()["last4"] == "abcd"
        stored = await mock_db.provider_keys.find_one({"provider": "groq"})
        assert stored["ciphertext"] != WS_KEY and "key" not in stored

        body = (await client.get("/api/org/integrations")).text
        assert WS_KEY not in body and stored["ciphertext"] not in body
        groq = next(p for p in (await client.get("/api/org/integrations")).json()["providers"] if p["id"] == "groq")
        assert groq["source"] == "workspace" and groq["workspace_key"]["last4"] == "abcd"

    async def test_save_refused_when_provider_rejects_key(self, client, mock_db, provider_http):
        resp = await client.put("/api/org/integrations/firecrawl", json={"key": "bad-key-0000000"})
        assert resp.status_code == 400
        assert "Key rejected" in resp.json()["detail"] and "bad-key" not in resp.json()["detail"]
        assert await mock_db.provider_keys.count_documents({}) == 0

    async def test_invalid_input_rejected(self, client, provider_http):
        assert (await client.put("/api/org/integrations/groq", json={"key": "short"})).status_code == 422
        assert (await client.put("/api/org/integrations/groq", json={"key": "has space in it"})).status_code == 422
        assert (await client.put("/api/org/integrations/groq", json={"key": "line1\nline2xx"})).status_code == 422
        assert (await client.put("/api/org/integrations/openai", json={"key": WS_KEY})).status_code == 404

    async def test_no_secret_means_no_workspace_keys(self, client, monkeypatch, provider_http):
        monkeypatch.delenv("PROVIDER_KEYS_SECRET")
        resp = await client.put("/api/org/integrations/groq", json={"key": WS_KEY})
        assert resp.status_code == 400 and "PROVIDER_KEYS_SECRET" in resp.json()["detail"]
        assert (await client.get("/api/org/integrations")).json()["keys_enabled"] is False

    async def test_only_owner_or_admin_can_change_keys(self, client, mock_db, provider_http):
        from app.auth import AuthUser
        org_id = await _org_id(client, mock_db)
        assert (await client.put("/api/org/integrations/groq", json={"key": WS_KEY})).status_code == 200
        await mock_db.org_members.insert_one({"org_id": org_id, "uid": "m2", "email": "m2@example.com", "role": "member"})
        await mock_db.users.insert_one({"uid": "m2", "org_id": org_id})
        _sign_in_as(AuthUser(uid="m2", email="m2@example.com"))

        assert (await client.put("/api/org/integrations/groq", json={"key": WS_KEY})).status_code == 403
        assert (await client.delete("/api/org/integrations/groq")).status_code == 403
        listing = (await client.get("/api/org/integrations")).json()
        assert listing["can_manage"] is False  # members still see status
        assert await mock_db.provider_keys.count_documents({}) == 1

    async def test_owner_removes_key_and_server_key_applies_again(self, client, mock_db, provider_http):
        await client.put("/api/org/integrations/groq", json={"key": WS_KEY})
        assert (await client.delete("/api/org/integrations/groq")).status_code == 200
        assert (await client.delete("/api/org/integrations/groq")).status_code == 404
        groq = next(p for p in (await client.get("/api/org/integrations")).json()["providers"] if p["id"] == "groq")
        assert groq["source"] == "server" and groq["workspace_key"] is None


class TestKeyResolution:
    async def test_key_for_prefers_workspace_and_falls_back_to_env(self, mock_db):
        from app.services import provider_keys
        await mock_db.provider_keys.insert_one({"org_id": "o1", "provider": "gemini",
                                                "ciphertext": provider_keys.encrypt(WS_KEY), "last4": "abcd"})
        assert provider_keys.key_for("gemini") == "server-gemini_api_key"

        async def in_workspace(org_id):
            await provider_keys.use_org(org_id)
            return provider_keys.key_for("gemini"), provider_keys.key_for("groq")

        import asyncio
        # A task copies the context, so the workspace doesn't leak out of it
        assert await asyncio.create_task(in_workspace("o1")) == (WS_KEY, "server-groq_api_key")
        assert await asyncio.create_task(in_workspace("o2")) == ("server-gemini_api_key", "server-groq_api_key")
        assert provider_keys.key_for("gemini") == "server-gemini_api_key"

    async def test_route_checks_use_the_workspace_key_in_a_header(self, client, mock_db, provider_http, calls):
        await client.put("/api/org/integrations/groq", json={"key": WS_KEY})
        calls.clear()
        resp = await client.post("/api/org/integrations/groq/test")
        assert resp.status_code == 200 and resp.json()["status"] == "ok" and resp.json()["source"] == "workspace"
        assert calls[0].headers["authorization"] == f"Bearer {WS_KEY}"

    async def test_fact_checker_groq_call_carries_workspace_key(self, mock_db):
        from app.services import provider_keys, fact_checker_service as fc
        await mock_db.provider_keys.insert_one({"org_id": "o1", "provider": "groq",
                                                "ciphertext": provider_keys.encrypt(WS_KEY), "last4": "abcd"})
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        real = httpx.AsyncClient

        async def run():
            await provider_keys.use_org("o1")
            with patch.object(fc.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
                return await fc._call_groq("system", "user")

        import asyncio
        assert await asyncio.create_task(run()) == "ok"
        assert seen[0].headers["authorization"] == f"Bearer {WS_KEY}" and WS_KEY not in str(seen[0].url)

    async def test_resume_task_runs_with_its_workspace_keys(self, mock_db):
        from app.routes import resume
        from app.services import provider_keys
        job_id = str((await mock_db.jobs.insert_one({"job_title": "x", "org_id": "o1"})).inserted_id)
        await mock_db.provider_keys.insert_one({"org_id": "o1", "provider": "gemini",
                                                "ciphertext": provider_keys.encrypt(WS_KEY), "last4": "abcd"})
        seen = {}

        async def prepare(task, path):
            seen["gemini"] = provider_keys.key_for("gemini")
            return {"kind": "cover_letter"}

        with patch.object(resume.cover_letter_service, "prepare_upload", prepare), \
                patch.object(resume.cover_letter_service, "after_resume", AsyncMock()):
            import asyncio
            await asyncio.create_task(resume.process_resume_task({"job_id": job_id, "filename": "f.pdf", "task_id": "t1"}))
        assert seen["gemini"] == WS_KEY

    async def test_no_provider_check_puts_a_key_in_the_url(self, provider_http, calls):
        from app.services.usage_service import PROVIDERS, check
        for pid in PROVIDERS:
            await check(pid, key=f"{pid}-{WS_KEY}", refresh=True)
        assert len(calls) == len(PROVIDERS)
        for request in calls:
            assert WS_KEY not in str(request.url)


class TestAiUsage:
    async def test_feature_counters_increment_and_roll_back_at_limit(self, mock_db, monkeypatch):
        from app.services.quota import use_quota
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "3")
        await use_quota("o1", "ai_call", feature="fact_checker")
        await use_quota("o1", "ai_call", 2, feature="project_reviews")
        with pytest.raises(HTTPException):
            await use_quota("o1", "ai_call", feature="fact_checker")
        doc = await mock_db.usage_quotas.find_one({"org_id": "o1"})
        assert doc["count"] == 3 and doc["features"] == {"fact_checker": 1, "project_reviews": 2}

    async def test_ai_usage_returns_today_features_and_30_days(self, client, mock_db, provider_http, monkeypatch):
        from app.services.quota import use_quota
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "50")
        org_id = await _org_id(client, mock_db)
        await use_quota(org_id, "ai_call", feature="interview_questions")
        await use_quota(org_id, "resume_upload", 4, feature="resume_parsing")
        await use_quota("someone-else", "ai_call", feature="fact_checker")

        data = (await client.get("/api/org/ai-usage")).json()
        assert data["today"]["ai_call"] == {"used": 1, "limit": 50, "label": "AI calls"}
        assert data["today"]["resume_upload"]["used"] == 4
        assert data["features"] == {"interview_questions": 1, "resume_parsing": 4}
        assert len(data["history"]) == 30 and data["history"][-1]["ai_calls"] == 1 and data["history"][-1]["uploads"] == 4
        assert sum(d["ai_calls"] for d in data["history"]) == 1
        assert [p["id"] for p in data["providers"]] == ["gemini", "groq"]
        assert data["resets_at"].endswith("T00:00:00+00:00")


class TestRemovedMember:
    async def test_stale_workspace_pointer_does_not_load_keys(self, mock_db):
        import asyncio
        from app.auth import AuthUser
        from app.services import provider_keys
        await mock_db.provider_keys.insert_one({"org_id": "o1", "provider": "groq",
                                                "ciphertext": provider_keys.encrypt(WS_KEY), "last4": "abcd"})
        await mock_db.users.insert_one({"uid": "gone", "org_id": "o1"})  # not in org_members

        async def run(user):
            await provider_keys.use_user(user)
            return provider_keys.key_for("groq")

        assert await asyncio.create_task(run(AuthUser(uid="gone"))) == "server-groq_api_key"
        await mock_db.org_members.insert_one({"org_id": "o1", "uid": "gone", "role": "member"})
        assert await asyncio.create_task(run(AuthUser(uid="gone"))) == WS_KEY
