"""
Calendar + mail connections (per user: Google, Microsoft) and the workspace Slack app.

OAuth 2.0 authorization code flow, run on the server:
  connect   authorize URL with a signed ``state`` (HMAC-SHA256 over uid + workspace + provider +
            nonce + expiry). The nonce's PKCE verifier stays in ``db.oauth_states``, never in the URL.
  callback  state checked, nonce consumed once, code exchanged, tokens Fernet-encrypted with
            PROVIDER_KEYS_SECRET (app.services.provider_keys) in ``db.user_connections`` /
            ``db.slack_connections``.
Tokens never leave the server. Every provider request in this feature goes through ``_http``
so tests can swap the transport.

Env: GOOGLE_OAUTH_CLIENT_ID/SECRET, MICROSOFT_OAUTH_CLIENT_ID/SECRET, MICROSOFT_OAUTH_TENANT
(default "common"), SLACK_CLIENT_ID/SECRET, OAUTH_REDIRECT_BASE_URL (public backend URL),
PROVIDER_KEYS_SECRET. A provider missing any of them reports configured() == False.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import InvalidToken

from app.database import db
from app.services import provider_keys

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 600
CALENDAR_PROVIDERS = ("google", "microsoft")

GOOGLE_SCOPES = [
    "openid", "email",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/gmail.send",
]
MICROSOFT_SCOPES = ["offline_access", "User.Read", "Calendars.ReadWrite", "Mail.Send"]
# channels:read lists channels for the picker; users:read is required alongside users:read.email
SLACK_SCOPES = ["chat:write", "channels:read", "users:read", "users:read.email", "im:write"]

NAMES = {"google": "Google", "microsoft": "Microsoft", "slack": "Slack"}
_ENV = {
    "google": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
    "microsoft": ("MICROSOFT_OAUTH_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_SECRET"),
    "slack": ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"),
}


class ProviderError(Exception):
    """A provider call failed. The message is safe to show: no tokens, no raw provider bodies."""


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _ms_base() -> str:
    return f"https://login.microsoftonline.com/{_env('MICROSOFT_OAUTH_TENANT') or 'common'}/oauth2/v2.0"


def _authorize_endpoint(provider: str) -> str:
    return {"google": "https://accounts.google.com/o/oauth2/v2/auth",
            "microsoft": _ms_base() + "/authorize",
            "slack": "https://slack.com/oauth/v2/authorize"}[provider]


def _token_endpoint(provider: str) -> str:
    return {"google": "https://oauth2.googleapis.com/token",
            "microsoft": _ms_base() + "/token",
            "slack": "https://slack.com/api/oauth.v2.access"}[provider]


def configured(provider: str) -> bool:
    cid, secret = _ENV[provider]
    return bool(_env(cid) and _env(secret) and _env("OAUTH_REDIRECT_BASE_URL") and provider_keys.enabled())


def redirect_uri(provider: str) -> str:
    return f"{_env('OAUTH_REDIRECT_BASE_URL').rstrip('/')}/api/integrations/oauth/callback/{provider}"


def _http(timeout: float = 20) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


# ── Signed state ────────────────────────────────────────────────────────

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _state_key() -> bytes:
    # Derived from the token-encryption secret, so there is one secret to manage
    return hashlib.sha256(b"oauth-state:" + _env("PROVIDER_KEYS_SECRET").encode()).digest()


def sign_state(payload: dict) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{_b64(hmac.new(_state_key(), body.encode(), hashlib.sha256).digest())}"


def verify_state(state: Optional[str], provider: str) -> dict:
    """The state's payload if the signature, provider and expiry check out; ProviderError otherwise."""
    try:
        body, sig = (state or "").split(".")
        expected = _b64(hmac.new(_state_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("signature")
        payload = json.loads(_unb64(body))
    except (ValueError, TypeError):
        raise ProviderError("The sign-in link is invalid. Start again from Settings.")
    if payload.get("p") != provider or payload.get("e", 0) < time.time():
        raise ProviderError("The sign-in link expired. Start again from Settings.")
    return payload


async def authorize_url(provider: str, uid: str, org_id: str) -> str:
    nonce, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    expires = time.time() + STATE_TTL_SECONDS
    await db.oauth_states.insert_one({"_id": nonce, "verifier": verifier, "uid": uid, "org_id": org_id,
                                      "provider": provider, "expires_at": datetime.utcfromtimestamp(expires)})
    state = sign_state({"u": uid, "o": org_id, "p": provider, "n": nonce, "e": int(expires)})
    params = {"client_id": _env(_ENV[provider][0]), "redirect_uri": redirect_uri(provider),
              "response_type": "code", "state": state}
    if provider == "slack":
        params["scope"] = ",".join(SLACK_SCOPES)
    else:
        challenge = _b64(hashlib.sha256(verifier.encode()).digest())
        params.update(code_challenge=challenge, code_challenge_method="S256")
        if provider == "google":
            params.update(scope=" ".join(GOOGLE_SCOPES), access_type="offline", prompt="consent",
                          include_granted_scopes="true")
        else:
            params.update(scope=" ".join(MICROSOFT_SCOPES), response_mode="query", prompt="select_account")
    return f"{_authorize_endpoint(provider)}?{urlencode(params)}"


async def consume_state(state: Optional[str], provider: str) -> dict:
    """Check the state and use its nonce up (single use). Returns the stored {uid, org_id, verifier}."""
    payload = verify_state(state, provider)
    doc = await db.oauth_states.find_one_and_delete({"_id": payload["n"], "provider": provider,
                                                     "uid": payload["u"], "org_id": payload["o"]})
    if not doc or doc["expires_at"] < datetime.utcnow():
        raise ProviderError("The sign-in link was already used or expired. Start again from Settings.")
    return doc


# ── Tokens ──────────────────────────────────────────────────────────────

async def _token_request(provider: str, data: dict) -> dict:
    cid, secret = _ENV[provider]
    data = {**data, "client_id": _env(cid), "client_secret": _env(secret)}
    try:
        async with _http() as http:
            resp = await http.post(_token_endpoint(provider), data=data)
        body = resp.json() if resp.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("%s token endpoint unreachable: %s", provider, type(exc).__name__)
        raise ProviderError(f"Couldn't reach {NAMES[provider]}. Try again.")
    error = body.get("error") if isinstance(body, dict) else None
    if resp.status_code >= 400 or error or (provider == "slack" and not body.get("ok")):
        code = error if isinstance(error, str) else f"HTTP {resp.status_code}"
        raise ProviderError(f"{NAMES[provider]} refused the request ({code[:60]})")
    return body


def _expiry(tokens: dict) -> datetime:
    return datetime.utcnow() + timedelta(seconds=int(tokens.get("expires_in") or 3600))


async def _account_email(provider: str, access_token: str) -> str:
    url = ("https://openidconnect.googleapis.com/v1/userinfo" if provider == "google"
           else "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName")
    try:
        async with _http() as http:
            resp = await http.get(url, headers={"Authorization": f"Bearer {access_token}"})
        data = resp.json() if resp.status_code < 400 else {}
    except (httpx.HTTPError, ValueError):
        data = {}
    return (data.get("email") or data.get("mail") or data.get("userPrincipalName") or "").lower()


async def complete(provider: str, code: str, state_doc: dict) -> None:
    """Exchange the authorization code and store the connection (encrypted)."""
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(provider)}
    if provider != "slack":
        data["code_verifier"] = state_doc["verifier"]
    tokens = await _token_request(provider, data)
    now = datetime.utcnow()
    if provider == "slack":
        await db.slack_connections.update_one(
            {"org_id": state_doc["org_id"]},
            {"$set": {"bot_token": provider_keys.encrypt(tokens["access_token"]),
                      "team": (tokens.get("team") or {}).get("name"), "scopes": tokens.get("scope", ""),
                      "connected_by": state_doc["uid"], "connected_at": now}},
            upsert=True)
        return
    fields = {
        "email": await _account_email(provider, tokens["access_token"]),
        "scopes": tokens.get("scope", ""),
        "access_token": provider_keys.encrypt(tokens["access_token"]),
        "expires_at": _expiry(tokens), "status": "active", "connected_at": now,
    }
    if tokens.get("refresh_token"):
        fields["refresh_token"] = provider_keys.encrypt(tokens["refresh_token"])
    await db.user_connections.update_one(
        {"uid": state_doc["uid"], "org_id": state_doc["org_id"], "provider": provider}, {"$set": fields}, upsert=True)


def expired_message(provider: str) -> str:
    return f"{NAMES[provider]} calendar access expired. Reconnect it in Settings > Integrations."


async def calendar_connection(uid: str, org_id: str) -> Optional[dict]:
    """The user's calendar connection in this workspace (Google first), or None."""
    conns = await db.user_connections.find({"uid": uid, "org_id": org_id}).to_list(5)
    conns.sort(key=lambda c: CALENDAR_PROVIDERS.index(c["provider"]) if c["provider"] in CALENDAR_PROVIDERS else 9)
    return conns[0] if conns else None


async def access_token(conn: dict) -> str:
    """A valid access token for the connection, refreshed when it is about to expire."""
    provider = conn["provider"]
    if conn.get("status") == "expired":
        raise ProviderError(expired_message(provider))
    try:
        if conn["expires_at"] > datetime.utcnow() + timedelta(seconds=60):
            return provider_keys.decrypt(conn["access_token"])
        refresh = provider_keys.decrypt(conn["refresh_token"]) if conn.get("refresh_token") else None
    except InvalidToken:
        refresh = None  # secret rotated: the stored tokens are unreadable
    if not refresh:
        await _mark_expired(conn)
        raise ProviderError(expired_message(provider))
    data = {"grant_type": "refresh_token", "refresh_token": refresh}
    if provider == "microsoft":
        data["scope"] = " ".join(MICROSOFT_SCOPES)
    try:
        tokens = await _token_request(provider, data)
    except ProviderError as exc:
        if "invalid_grant" in str(exc) or "HTTP 401" in str(exc):
            await _mark_expired(conn)
            raise ProviderError(expired_message(provider))
        raise
    update = {"access_token": provider_keys.encrypt(tokens["access_token"]), "expires_at": _expiry(tokens)}
    if tokens.get("refresh_token"):  # Microsoft rotates refresh tokens
        update["refresh_token"] = provider_keys.encrypt(tokens["refresh_token"])
    await db.user_connections.update_one({"_id": conn["_id"]}, {"$set": update})
    conn.update(update)
    return tokens["access_token"]


async def _mark_expired(conn: dict) -> None:
    await db.user_connections.update_one({"_id": conn["_id"]}, {"$set": {"status": "expired"}})
    conn["status"] = "expired"


async def api(conn: dict, method: str, url: str, what: str, **kwargs) -> dict:
    """Call a calendar/mail API as the connection's user. Returns the JSON body ({} when empty)."""
    token = await access_token(conn)
    headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
    name = NAMES[conn["provider"]]
    try:
        async with _http() as http:
            resp = await http.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        logger.warning("%s %s failed: %s", name, what, type(exc).__name__)
        raise ProviderError(f"Couldn't reach {name} to {what}. Try again.")
    if resp.status_code == 401:
        await _mark_expired(conn)
        raise ProviderError(expired_message(conn["provider"]))
    if resp.status_code >= 400:
        logger.warning("%s %s returned HTTP %s", name, what, resp.status_code)
        raise ProviderError(f"{name} couldn't {what} (HTTP {resp.status_code}).")
    try:
        return resp.json() if resp.content else {}
    except ValueError:
        return {}


async def revoke(provider: str, token: str) -> None:
    """Best effort: tell the provider to drop the grant. Microsoft has no per-app revoke endpoint."""
    try:
        async with _http(10) as http:
            if provider == "google":
                await http.post("https://oauth2.googleapis.com/revoke", data={"token": token})
            elif provider == "slack":
                await http.post("https://slack.com/api/auth.revoke", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        pass


# ── Slack ───────────────────────────────────────────────────────────────

def valid_slack_webhook(url: str) -> bool:
    """Only Slack's incoming-webhook host (SSRF rule): https, hooks.slack.com, default port, /services/ path."""
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname == "hooks.slack.com" and parts.port is None
                and not parts.username and parts.path.startswith("/services/") and len(url) <= 300)
    except ValueError:
        return False


async def _slack(token: str, method: str, **payload) -> dict:
    try:
        async with _http(10) as http:
            resp = await http.post(f"https://slack.com/api/{method}", data=payload,
                                   headers={"Authorization": f"Bearer {token}"})
        body = resp.json()
    except (httpx.HTTPError, ValueError):
        raise ProviderError("Couldn't reach Slack")
    if not body.get("ok"):
        hint = " (invite the app to the channel with /invite)" if body.get("error") == "not_in_channel" else ""
        raise ProviderError(f"Slack: {str(body.get('error') or 'error')[:60]}{hint}")
    return body


async def slack_channels(org_id: str) -> list:
    doc = await db.slack_connections.find_one({"org_id": org_id})
    if not doc or not doc.get("bot_token"):
        raise ProviderError("Slack isn't connected")
    body = await _slack(provider_keys.decrypt(doc["bot_token"]), "conversations.list",
                        types="public_channel", exclude_archived="true", limit="200")
    return [{"id": c["id"], "name": c["name"]} for c in body.get("channels", [])]


async def slack_notify(org_id: str, text: str, dm_emails=()) -> dict:
    """Post to the workspace channel (app or webhook) and DM the people with these emails.

    Never raises: returns {"configured", "sent", "errors"} so a Slack outage never fails a booking.
    """
    doc = await db.slack_connections.find_one({"org_id": org_id})
    if not doc or not (doc.get("bot_token") or doc.get("webhook")):
        return {"configured": False, "sent": False, "errors": []}
    sent, errors = False, []
    try:
        if doc.get("bot_token"):
            token = provider_keys.decrypt(doc["bot_token"])
            if doc.get("channel_id"):
                try:
                    await _slack(token, "chat.postMessage", channel=doc["channel_id"], text=text)
                    sent = True
                except ProviderError as exc:
                    errors.append(str(exc))
            for email in {e.lower() for e in dm_emails if e}:
                try:
                    user = (await _slack(token, "users.lookupByEmail", email=email))["user"]["id"]
                    channel = (await _slack(token, "conversations.open", users=user))["channel"]["id"]
                    await _slack(token, "chat.postMessage", channel=channel, text=text)
                    sent = True
                except (ProviderError, KeyError) as exc:
                    errors.append(f"DM to an interviewer failed: {exc}")
        elif doc.get("webhook"):
            async with _http(10) as http:
                resp = await http.post(provider_keys.decrypt(doc["webhook"]), json={"text": text})
            if resp.status_code < 400:
                sent = True
            else:
                errors.append(f"Slack webhook returned HTTP {resp.status_code}")
    except InvalidToken:
        errors.append("The saved Slack credentials can't be read (server secret changed). Reconnect Slack.")
    except httpx.HTTPError:
        errors.append("Couldn't reach Slack")
    return {"configured": True, "sent": sent, "errors": errors}
