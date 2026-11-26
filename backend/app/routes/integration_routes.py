"""
Calendar & email connections (each user's own Google / Microsoft account) and the
workspace's Slack app or webhook. See app.services.integrations for the OAuth flow.

``public_router`` holds only the OAuth callback: the provider redirects the browser
there without our bearer token, so the signed, single-use state is what authenticates it.
"""
import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.auth import AuthUser, get_current_user
from app.database import db
from app.org import APP_URL, MANAGER_ROLES, membership, reject_api_key, require_manager
from app.services import integrations, provider_keys
from app.services.integrations import CALENDAR_PROVIDERS, NAMES, ProviderError
from app.services.quota import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])
public_router = APIRouter(prefix="/integrations", tags=["integrations"])


class SlackSettings(BaseModel):
    channel_id: Optional[str] = Field(None, pattern=r"^[A-Z0-9]{6,20}$")
    channel_name: Optional[str] = Field(None, max_length=80)
    webhook_url: Optional[str] = Field(None, max_length=300)


async def _member(user: AuthUser) -> dict:
    """Connections belong to a signed-in person: workspace API keys can't use or change them."""
    reject_api_key(user)
    return await membership(user)


def _connection_out(c: Optional[dict]) -> Optional[dict]:
    if not c:
        return None
    return {"email": c.get("email"), "scopes": c.get("scopes", ""), "connected_at": c.get("connected_at"),
            "status": c.get("status", "active")}


def _slack_out(doc: Optional[dict], role: str) -> dict:
    doc = doc or {}
    return {
        "oauth_configured": integrations.configured("slack"),
        "webhook_allowed": provider_keys.enabled(),
        "connected": bool(doc.get("bot_token")),
        "team": doc.get("team"),
        "channel": {"id": doc["channel_id"], "name": doc.get("channel_name")} if doc.get("channel_id") else None,
        "webhook": bool(doc.get("webhook")),
        "can_manage": role in MANAGER_ROLES,
    }


@router.get("/me")
async def my_connections(user: AuthUser = Depends(get_current_user)):
    """The caller's calendar connections and the workspace's Slack setup. Never includes tokens."""
    m = await _member(user)
    conns = {c["provider"]: c async for c in db.user_connections.find({"uid": user.uid, "org_id": m["org_id"]})}
    return {
        "calendar": [{"id": p, "name": NAMES[p], "configured": integrations.configured(p),
                      "connection": _connection_out(conns.get(p))} for p in CALENDAR_PROVIDERS],
        "slack": _slack_out(await db.slack_connections.find_one({"org_id": m["org_id"]}), m["role"]),
    }


@router.get("/team")
async def team_calendars(user: AuthUser = Depends(get_current_user)):
    """Workspace members and whether each has a calendar connected (for picking interviewers)."""
    m = await _member(user)
    members = await db.org_members.find({"org_id": m["org_id"]}, {"_id": 0, "uid": 1, "name": 1, "email": 1}).to_list(500)
    conns = {}
    async for c in db.user_connections.find({"org_id": m["org_id"]}, {"uid": 1, "provider": 1, "status": 1}):
        if c.get("status", "active") == "active":
            conns.setdefault(c["uid"], c["provider"])
    return {"members": [{**x, "calendar": conns.get(x["uid"])} for x in members], "me": user.uid}


# Slack routes come before /{provider} so "slack" isn't taken as a calendar provider

@router.get("/slack/channels")
async def slack_channels(user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    rate_limit(user.uid, "slack")
    try:
        return {"channels": await integrations.slack_channels(m["org_id"])}
    except ProviderError as exc:
        raise HTTPException(400, str(exc))


@router.put("/slack")
async def save_slack(body: SlackSettings, user: AuthUser = Depends(get_current_user)):
    """Pick the notification channel (Slack app) or save an incoming-webhook URL."""
    m = await require_manager(user)
    if body.webhook_url:
        if not integrations.valid_slack_webhook(body.webhook_url):
            raise HTTPException(400, "Use a Slack incoming-webhook URL (https://hooks.slack.com/services/...)")
        if not provider_keys.enabled():
            raise HTTPException(400, "Set PROVIDER_KEYS_SECRET on the server to save a webhook")
        update = {"webhook": provider_keys.encrypt(body.webhook_url)}
    elif body.channel_id:
        if not await db.slack_connections.find_one({"org_id": m["org_id"], "bot_token": {"$exists": True}}, {"_id": 1}):
            raise HTTPException(400, "Connect the Slack app first")
        update = {"channel_id": body.channel_id, "channel_name": (body.channel_name or "").lstrip("#")[:80]}
    else:
        raise HTTPException(400, "Give a channel or a webhook URL")
    await db.slack_connections.update_one({"org_id": m["org_id"]}, {"$set": update}, upsert=True)
    return _slack_out(await db.slack_connections.find_one({"org_id": m["org_id"]}), m["role"])


@router.delete("/slack")
async def remove_slack(user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    doc = await db.slack_connections.find_one_and_delete({"org_id": m["org_id"]})
    if not doc:
        raise HTTPException(404, "Slack isn't set up for this workspace")
    if doc.get("bot_token"):
        try:
            await integrations.revoke("slack", provider_keys.decrypt(doc["bot_token"]))
        except Exception:  # unreadable token: nothing to revoke
            pass
    return {"removed": "slack"}


@router.get("/{provider}/connect")
async def connect(provider: str, user: AuthUser = Depends(get_current_user)):
    """The provider's sign-in URL; the browser goes there and comes back through the callback."""
    if provider == "slack":
        m = await require_manager(user)
    elif provider in CALENDAR_PROVIDERS:
        m = await _member(user)
    else:
        raise HTTPException(404, "Unknown provider")
    rate_limit(user.uid, "oauth_connect")
    if not integrations.configured(provider):
        raise HTTPException(400, f"{NAMES[provider]} isn't configured on this server")
    return {"url": await integrations.authorize_url(provider, user.uid, m["org_id"])}


@router.delete("/{provider}")
async def disconnect(provider: str, user: AuthUser = Depends(get_current_user)):
    if provider not in CALENDAR_PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    m = await _member(user)
    doc = await db.user_connections.find_one_and_delete({"uid": user.uid, "org_id": m["org_id"], "provider": provider})
    if not doc:
        raise HTTPException(404, f"No {NAMES[provider]} account is connected")
    try:
        token = doc.get("refresh_token") or doc.get("access_token")
        if token:
            await integrations.revoke(provider, provider_keys.decrypt(token))
    except Exception:  # unreadable token: nothing to revoke
        pass
    return {"removed": provider}


@public_router.get("/oauth/callback/{provider}")
async def oauth_callback(provider: str, request: Request, code: Optional[str] = None,
                         state: Optional[str] = None, error: Optional[str] = None):
    """Provider redirect target. Always sends the browser back to Settings > Integrations (APP_URL only)."""
    def back(**query):
        return RedirectResponse(f"{APP_URL.rstrip('/')}/settings?{urlencode({'tab': 'integrations', **query})}", 303)

    if provider not in NAMES:
        raise HTTPException(404, "Unknown provider")
    rate_limit(f"ip:{request.client.host if request.client else '?'}", "oauth_callback")
    try:
        st = await integrations.consume_state(state, provider)
    except ProviderError:
        return back(error="expired", provider=provider)
    if error or not code:
        return back(error="denied", provider=provider)
    member = await db.org_members.find_one({"org_id": st["org_id"], "uid": st["uid"]}, {"role": 1})
    if not member or (provider == "slack" and member["role"] not in MANAGER_ROLES):
        return back(error="forbidden", provider=provider)
    try:
        await integrations.complete(provider, code, st)
    except (ProviderError, KeyError) as exc:
        logger.warning("%s OAuth exchange failed for uid %s: %s", provider, st["uid"], exc)
        return back(error="exchange", provider=provider)
    return back(connected=provider)
