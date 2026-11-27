"""
Calendar + mail connections and Slack (app/services/integrations.py, app/routes/integration_routes.py).
Every provider request goes to a fake behind httpx.MockTransport.
"""
import time
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet

OAUTH_ENV = {
    "GOOGLE_OAUTH_CLIENT_ID": "g-client", "GOOGLE_OAUTH_CLIENT_SECRET": "g-secret",
    "MICROSOFT_OAUTH_CLIENT_ID": "m-client", "MICROSOFT_OAUTH_CLIENT_SECRET": "m-secret",
    "SLACK_CLIENT_ID": "s-client", "SLACK_CLIENT_SECRET": "s-secret",
    "OAUTH_REDIRECT_BASE_URL": "https://api.example.com",
}


class FakeProviders:
    """Google, Microsoft Graph and Slack, just enough for these features. ``busy`` maps access token -> intervals."""

    def __init__(self):
        self.requests = []
        self.busy = {}
        self.refresh_error = None
        self.slack_error = None
        self.event_status = 200

    def form(self, request):
        return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}

    def __call__(self, request: httpx.Request):
        self.requests.append(request)
        host, path = request.url.host, request.url.path
        auth = request.headers.get("authorization", "").removeprefix("Bearer ")
        if host == "oauth2.googleapis.com" and path == "/token":
            f = self.form(request)
            if f["grant_type"] == "refresh_token":
                if self.refresh_error:
                    return httpx.Response(400, json={"error": self.refresh_error})
                return httpx.Response(200, json={"access_token": "g-access-2", "expires_in": 3600})
            return httpx.Response(200, json={"access_token": "g-access", "refresh_token": "g-refresh",
                                             "expires_in": 3600, "scope": "calendar.events gmail.send"})
        if host == "oauth2.googleapis.com" and path == "/revoke":
            return httpx.Response(200)
        if host == "openidconnect.googleapis.com":
            return httpx.Response(200, json={"email": "Organizer@Example.com"})
        if host == "login.microsoftonline.com":
            f = self.form(request)
            return httpx.Response(200, json={"access_token": "m-access", "refresh_token": "m-refresh-new",
                                             "expires_in": 3600, "scope": f.get("scope", "Calendars.ReadWrite")})
        if host == "graph.microsoft.com":
            if path == "/v1.0/me":
                return httpx.Response(200, json={"mail": "ms.user@example.com"})
            if path.endswith("/getSchedule"):
                items = [{"status": "busy", "start": {"dateTime": s.strftime("%Y-%m-%dT%H:%M:%S.0000000")},
                          "end": {"dateTime": e.strftime("%Y-%m-%dT%H:%M:%S.0000000")}} for s, e in self.busy.get(auth, [])]
                return httpx.Response(200, json={"value": [{"scheduleItems": items}]})
            if path == "/v1.0/me/events":
                return httpx.Response(201, json={"id": "ms-evt", "onlineMeeting": {"joinUrl": "https://teams.example.com/j/1"}})
            return httpx.Response(202)
        if host == "www.googleapis.com":
            if path.endswith("/freeBusy"):
                busy = [{"start": s.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": e.strftime("%Y-%m-%dT%H:%M:%SZ")}
                        for s, e in self.busy.get(auth, [])]
                return httpx.Response(200, json={"calendars": {"primary": {"busy": busy}}})
            if request.method == "POST":
                return httpx.Response(200, json={"id": "g-evt", "hangoutLink": "https://meet.google.com/abc-defg-hij"})
            return httpx.Response(self.event_status, json={})
        if host == "gmail.googleapis.com":
            return httpx.Response(200, json={"id": "msg-1"})
        if host == "slack.com":
            method = path.rsplit("/", 1)[-1]
            if method == "oauth.v2.access":
                return httpx.Response(200, json={"ok": True, "access_token": "xoxb-test", "team": {"name": "Example Team"},
                                                 "scope": "chat:write"})
            if self.slack_error:
                return httpx.Response(200, json={"ok": False, "error": self.slack_error})
            if method == "conversations.list":
                return httpx.Response(200, json={"ok": True, "channels": [{"id": "C0123456", "name": "hiring"}]})
            if method == "users.lookupByEmail":
                return httpx.Response(200, json={"ok": True, "user": {"id": "U0001"}})
            if method == "conversations.open":
                return httpx.Response(200, json={"ok": True, "channel": {"id": "D0001"}})
            return httpx.Response(200, json={"ok": True})
        if host == "hooks.slack.com":
            return httpx.Response(200, text="ok")
        return httpx.Response(404)

    def calls(self, host, path_part=""):
        return [r for r in self.requests if r.url.host == host and path_part in r.url.path]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("PROVIDER_KEYS_SECRET", Fernet.generate_key().decode())
    for k, v in OAUTH_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("COMPOSIO_API_KEY", raising=False)


@pytest.fixture()
def fake():
    providers = FakeProviders()
    real = httpx.AsyncClient
    with patch("app.services.integrations._http", lambda timeout=20: real(transport=httpx.MockTransport(providers))):
        yield providers


def sign_in_as(user):
    from app.main import app
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


async def org_of(client, mock_db, uid="test-user"):
    await client.get("/api/integrations/me")
    return (await mock_db.users.find_one({"uid": uid}))["org_id"]


async def add_member(mock_db, org_id, uid, role="member", email=None, name=None):
    await mock_db.org_members.insert_one({"org_id": org_id, "uid": uid, "role": role, "email": email or f"{uid}@example.com",
                                          "name": name or uid.title(), "joined_at": datetime.utcnow()})
    await mock_db.users.update_one({"uid": uid}, {"$set": {"org_id": org_id}}, upsert=True)


async def connect_calendar(mock_db, uid, org_id, provider="google", token=None, email=None, expires_in=3600):
    """A stored connection, as the OAuth callback leaves it."""
    from app.services import provider_keys
    await mock_db.user_connections.insert_one({
        "uid": uid, "org_id": org_id, "provider": provider, "email": email or f"{uid}@example.com",
        "access_token": provider_keys.encrypt(token or f"{uid}-token"), "refresh_token": provider_keys.encrypt(f"{uid}-refresh"),
        "expires_at": datetime.utcnow() + timedelta(seconds=expires_in), "status": "active", "connected_at": datetime.utcnow(),
    })


async def start_connect(client, provider="google"):
    resp = await client.get(f"/api/integrations/{provider}/connect")
    assert resp.status_code == 200, resp.text
    return parse_qs(urlsplit(resp.json()["url"]).query)


async def callback(client, provider, state, code="auth-code"):
    return await client.get(f"/api/integrations/oauth/callback/{provider}", params={"code": code, "state": state},
                            follow_redirects=False)


def redirect_query(resp):
    from app.org import APP_URL
    loc = resp.headers["location"]
    assert loc.startswith(f"{APP_URL.rstrip('/')}/settings?")
    return {k: v[0] for k, v in parse_qs(urlsplit(loc).query).items()}


class TestNotConfigured:
    async def test_providers_without_env_report_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET")
        body = (await client.get("/api/integrations/me")).json()
        google = next(p for p in body["calendar"] if p["id"] == "google")
        ms = next(p for p in body["calendar"] if p["id"] == "microsoft")
        assert google["configured"] is False and ms["configured"] is True
        resp = await client.get("/api/integrations/google/connect")
        assert resp.status_code == 400 and "isn't configured on this server" in resp.json()["detail"]

    async def test_no_redirect_base_or_secret_means_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("OAUTH_REDIRECT_BASE_URL")
        assert all(not p["configured"] for p in (await client.get("/api/integrations/me")).json()["calendar"])
        monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "https://api.example.com")
        monkeypatch.delenv("PROVIDER_KEYS_SECRET")
        body = (await client.get("/api/integrations/me")).json()
        assert all(not p["configured"] for p in body["calendar"]) and body["slack"]["oauth_configured"] is False


class TestOAuthFlow:
    async def test_connect_url_has_signed_state_pkce_and_minimal_scopes(self, client, mock_db):
        q = await start_connect(client)
        assert q["client_id"] == ["g-client"] and q["code_challenge_method"] == ["S256"]
        assert q["redirect_uri"] == ["https://api.example.com/api/integrations/oauth/callback/google"]
        scopes = q["scope"][0].split()
        assert "https://www.googleapis.com/auth/gmail.send" in scopes and "https://www.googleapis.com/auth/calendar" not in scopes
        state_doc = await mock_db.oauth_states.find_one({})
        assert state_doc["verifier"] not in q["state"][0] and state_doc["uid"] == "test-user"

    async def test_callback_stores_encrypted_tokens_and_redirects(self, client, mock_db, fake):
        q = await start_connect(client)
        resp = await callback(client, "google", q["state"][0])
        assert resp.status_code == 303 and redirect_query(resp) == {"tab": "integrations", "connected": "google"}
        token_call = fake.calls("oauth2.googleapis.com", "/token")[0]
        sent = fake.form(token_call)
        assert sent["code"] == "auth-code" and sent["code_verifier"] and "g-secret" == sent["client_secret"]

        conn = await mock_db.user_connections.find_one({"uid": "test-user", "provider": "google"})
        assert conn["email"] == "organizer@example.com"
        assert conn["access_token"] != "g-access" and conn["refresh_token"] != "g-refresh"
        from app.services import provider_keys
        assert provider_keys.decrypt(conn["refresh_token"]) == "g-refresh"

        body = (await client.get("/api/integrations/me")).text
        assert "g-access" not in body and "g-refresh" not in body and conn["access_token"] not in body
        assert '"email":"organizer@example.com"' in body
        assert await mock_db.oauth_states.count_documents({}) == 0

    async def test_tampered_state_is_rejected(self, client, mock_db, fake):
        q = await start_connect(client)
        body, sig = q["state"][0].split(".")
        import base64, json
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        payload["u"] = "attacker"
        forged = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
        for state in (f"{forged}.{sig}", "garbage", ""):
            resp = await callback(client, "google", state)
            assert redirect_query(resp)["error"] == "expired"
        assert await mock_db.user_connections.count_documents({}) == 0
        assert not fake.requests  # no code exchange

    async def test_state_is_single_use_and_provider_bound(self, client, mock_db, fake):
        q = await start_connect(client)
        assert redirect_query(await callback(client, "microsoft", q["state"][0]))["error"] == "expired"
        assert redirect_query(await callback(client, "google", q["state"][0]))["connected"] == "google"
        assert redirect_query(await callback(client, "google", q["state"][0]))["error"] == "expired"
        assert await mock_db.user_connections.count_documents({}) == 1

    async def test_expired_state_is_rejected(self, client, mock_db, fake):
        q = await start_connect(client)
        with patch("app.services.integrations.time.time", return_value=time.time() + 3600):
            resp = await callback(client, "google", q["state"][0])
        assert redirect_query(resp)["error"] == "expired"
        assert await mock_db.user_connections.count_documents({}) == 0

    async def test_denied_consent_and_removed_member(self, client, mock_db, fake):
        q = await start_connect(client)
        resp = await client.get("/api/integrations/oauth/callback/google",
                                params={"state": q["state"][0], "error": "access_denied"}, follow_redirects=False)
        assert redirect_query(resp)["error"] == "denied"
        q = await start_connect(client)
        await mock_db.org_members.delete_many({"uid": "test-user"})
        assert redirect_query(await callback(client, "google", q["state"][0]))["error"] == "forbidden"
        assert await mock_db.user_connections.count_documents({}) == 0

    async def test_microsoft_callback(self, client, mock_db, fake):
        q = await start_connect(client, "microsoft")
        assert "Mail.Send" in q["scope"][0] and "offline_access" in q["scope"][0]
        assert redirect_query(await callback(client, "microsoft", q["state"][0]))["connected"] == "microsoft"
        conn = await mock_db.user_connections.find_one({"provider": "microsoft"})
        assert conn["email"] == "ms.user@example.com"

    async def test_disconnect_revokes_at_google(self, client, mock_db, fake):
        org_id = await org_of(client, mock_db)
        await connect_calendar(mock_db, "test-user", org_id)
        assert (await client.delete("/api/integrations/google")).status_code == 200
        assert await mock_db.user_connections.count_documents({}) == 0
        assert fake.form(fake.calls("oauth2.googleapis.com", "/revoke")[0])["token"] == "test-user-refresh"
        assert (await client.delete("/api/integrations/google")).status_code == 404


class TestTokenRefresh:
    async def test_expired_access_token_is_refreshed_and_stored(self, client, mock_db, fake):
        from app.services import integrations, provider_keys
        org_id = await org_of(client, mock_db)
        await connect_calendar(mock_db, "test-user", org_id, expires_in=10)
        conn = await integrations.calendar_connection("test-user", org_id)
        assert await integrations.access_token(conn) == "g-access-2"
        assert fake.form(fake.calls("oauth2.googleapis.com", "/token")[0])["refresh_token"] == "test-user-refresh"
        stored = await mock_db.user_connections.find_one({})
        assert provider_keys.decrypt(stored["access_token"]) == "g-access-2" and stored["expires_at"] > datetime.utcnow()

    async def test_revoked_refresh_token_marks_connection_expired(self, client, mock_db, fake):
        from app.services import integrations
        fake.refresh_error = "invalid_grant"
        org_id = await org_of(client, mock_db)
        await connect_calendar(mock_db, "test-user", org_id, expires_in=-10)
        conn = await integrations.calendar_connection("test-user", org_id)
        with pytest.raises(integrations.ProviderError, match="Google calendar access expired.*Reconnect"):
            await integrations.access_token(conn)
        assert (await mock_db.user_connections.find_one({}))["status"] == "expired"
        me = (await client.get("/api/integrations/me")).json()
        assert next(p for p in me["calendar"] if p["id"] == "google")["connection"]["status"] == "expired"

    async def test_microsoft_refresh_sends_scope_and_keeps_rotated_token(self, client, mock_db, fake):
        from app.services import integrations, provider_keys
        org_id = await org_of(client, mock_db)
        await connect_calendar(mock_db, "test-user", org_id, provider="microsoft", expires_in=0)
        conn = await integrations.calendar_connection("test-user", org_id)
        assert await integrations.access_token(conn) == "m-access"
        assert "Calendars.ReadWrite" in fake.form(fake.calls("login.microsoftonline.com")[0])["scope"]
        assert provider_keys.decrypt((await mock_db.user_connections.find_one({}))["refresh_token"]) == "m-refresh-new"


class TestAccess:
    async def test_api_keys_cannot_use_connection_endpoints(self, client, mock_db):
        from app.auth import AuthUser
        org_id = await org_of(client, mock_db)
        sign_in_as(AuthUser(uid="test-user", provider="api_key", org_id=org_id))
        for method, path in [("get", "/api/integrations/me"), ("get", "/api/integrations/google/connect"),
                             ("delete", "/api/integrations/google"), ("get", "/api/integrations/team"),
                             ("get", "/api/integrations/slack/connect"), ("put", "/api/integrations/slack")]:
            kwargs = {"json": {"webhook_url": "https://hooks.slack.com/services/T/B/x"}} if method == "put" else {}
            assert (await getattr(client, method)(path, **kwargs)).status_code == 403, path

    async def test_team_shows_only_own_workspace_connections(self, client, mock_db):
        from app.auth import AuthUser
        org_id = await org_of(client, mock_db)
        await add_member(mock_db, org_id, "ana")
        await connect_calendar(mock_db, "ana", org_id)
        await connect_calendar(mock_db, "outsider", "other-org")
        members = {m["uid"]: m for m in (await client.get("/api/integrations/team")).json()["members"]}
        assert set(members) == {"test-user", "ana"} and members["ana"]["calendar"] == "google"
        assert members["test-user"]["calendar"] is None

    async def test_unknown_provider(self, client):
        assert (await client.get("/api/integrations/yahoo/connect")).status_code == 404
        assert (await client.get("/api/integrations/oauth/callback/yahoo", params={"state": "x"})).status_code == 404


class TestSlack:
    async def test_only_managers_connect_slack(self, client, mock_db, fake):
        from app.auth import AuthUser
        org_id = await org_of(client, mock_db)
        await add_member(mock_db, org_id, "mem")
        sign_in_as(AuthUser(uid="mem", email="mem@example.com", provider="google.com"))
        assert (await client.get("/api/integrations/slack/connect")).status_code == 403
        assert (await client.put("/api/integrations/slack", json={"channel_id": "C0123456"})).status_code == 403
        assert (await client.get("/api/integrations/me")).json()["slack"]["can_manage"] is False

    async def test_slack_install_channel_and_notify(self, client, mock_db, fake):
        from app.services import integrations
        q = await start_connect(client, "slack")
        assert set(q["scope"][0].split(",")) >= {"chat:write", "users:read.email", "im:write"}
        assert "code_challenge" not in q
        assert redirect_query(await callback(client, "slack", q["state"][0]))["connected"] == "slack"
        org_id = (await mock_db.users.find_one({"uid": "test-user"}))["org_id"]
        doc = await mock_db.slack_connections.find_one({"org_id": org_id})
        assert doc["bot_token"] != "xoxb-test" and doc["team"] == "Example Team"

        assert (await client.get("/api/integrations/slack/channels")).json()["channels"] == [{"id": "C0123456", "name": "hiring"}]
        resp = await client.put("/api/integrations/slack", json={"channel_id": "C0123456", "channel_name": "#hiring"})
        assert resp.json()["channel"] == {"id": "C0123456", "name": "hiring"}
        assert "xoxb" not in (await client.get("/api/integrations/me")).text

        fake.requests.clear()
        result = await integrations.slack_notify(org_id, "Interview booked", ["Ana@example.com", "ana@example.com"])
        assert result == {"configured": True, "sent": True, "errors": []}
        posts = [fake.form(r) for r in fake.calls("slack.com", "chat.postMessage")]
        assert {p["channel"] for p in posts} == {"C0123456", "D0001"} and len(posts) == 2
        assert all(r.headers["authorization"] == "Bearer xoxb-test" for r in fake.calls("slack.com"))

    async def test_slack_errors_are_reported_not_raised(self, client, mock_db, fake):
        from app.services import integrations, provider_keys
        org_id = await org_of(client, mock_db)
        await mock_db.slack_connections.insert_one({"org_id": org_id, "bot_token": provider_keys.encrypt("xoxb-test"),
                                                    "channel_id": "C0123456"})
        fake.slack_error = "not_in_channel"
        result = await integrations.slack_notify(org_id, "hi")
        assert result["sent"] is False and "invite the app" in result["errors"][0]

    @pytest.mark.parametrize("url", [
        "http://hooks.slack.com/services/T/B/x", "https://hooks.slack.com.evil.example/services/T",
        "https://evil.example/services/T", "https://hooks.slack.com:8443/services/T", "https://user@hooks.slack.com/services/T",
        "https://hooks.slack.com/other/T", "https://127.0.0.1/services/T",
    ])
    async def test_webhook_must_be_slack(self, client, url):
        resp = await client.put("/api/integrations/slack", json={"webhook_url": url})
        assert resp.status_code == 400

    async def test_webhook_saved_encrypted_and_used(self, client, mock_db, fake):
        from app.services import integrations
        url = "https://hooks.slack.com/services/T000/B000/secretpart"
        resp = await client.put("/api/integrations/slack", json={"webhook_url": url})
        assert resp.status_code == 200 and resp.json()["webhook"] is True and "secretpart" not in resp.text
        org_id = (await mock_db.users.find_one({"uid": "test-user"}))["org_id"]
        assert "secretpart" not in str(await mock_db.slack_connections.find_one({}))
        assert (await integrations.slack_notify(org_id, "hello"))["sent"] is True
        assert str(fake.calls("hooks.slack.com")[0].url) == url
        assert (await client.delete("/api/integrations/slack")).status_code == 200
        assert (await integrations.slack_notify(org_id, "hello"))["configured"] is False
