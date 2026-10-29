"""
Organizations: every user works inside one active organization.

- A personal organization is created the first time a user is seen; their
  existing jobs move into it.
- Jobs are shared by everyone in the organization (jobs.org_id).
- Members join through email invites (link always; email via Composio Gmail
  when COMPOSIO_API_KEY is set).
- Workspace API keys ("rai_...") act as the member who created them, inside
  that key's organization.

ponytail: one active org per user (users.org_id); add an org switcher if
people need to belong to several at once.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import HTTPException

from app.database import db

logger = logging.getLogger(__name__)

ROLES = ("owner", "admin", "member")
MANAGER_ROLES = ("owner", "admin")
API_KEY_PREFIX = "rai_"

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")
COMPOSIO_API_URL = os.getenv("COMPOSIO_API_URL", "https://backend.composio.dev/api/v3")
# Composio user whose Gmail account is connected (and optionally which connected account)
COMPOSIO_USER_ID = os.getenv("COMPOSIO_USER_ID", "default")
COMPOSIO_GMAIL_ACCOUNT_ID = os.getenv("COMPOSIO_GMAIL_ACCOUNT_ID")
APP_URL = os.getenv("APP_URL") or os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")[0]


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def join_url(token: str) -> str:
    return f"{APP_URL.rstrip('/')}/join/{token}"


async def ensure_org(user) -> str:
    """The user's active organization id, creating a personal one on first use."""
    if getattr(user, "org_id", None):  # API keys carry their organization
        return user.org_id
    doc = await db.users.find_one({"uid": user.uid}, {"org_id": 1})
    if doc and doc.get("org_id"):
        return doc["org_id"]

    member = await db.org_members.find_one({"uid": user.uid}, sort=[("joined_at", 1)])
    if member:
        org_id = member["org_id"]
    else:
        now = datetime.utcnow()
        label = (user.name or (user.email or "My").split("@")[0]).split(" ")[0]
        org_id = str((await db.orgs.insert_one({"name": f"{label}'s workspace", "created_by": user.uid, "created_at": now})).inserted_id)
        await db.org_members.insert_one({"org_id": org_id, "uid": user.uid, "email": (user.email or "").lower(),
                                         "name": user.name, "role": "owner", "joined_at": now})
        # Jobs created before organizations existed become this workspace's jobs
        await db.jobs.update_many({"owner_uid": user.uid, "org_id": {"$exists": False}}, {"$set": {"org_id": org_id}})

    await db.users.update_one({"uid": user.uid}, {"$set": {"org_id": org_id}, "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
    return org_id


async def membership(user) -> dict:
    """{org_id, role} for the caller; 403 if they were removed from their active org."""
    org_id = await ensure_org(user)
    member = await db.org_members.find_one({"org_id": org_id, "uid": user.uid})
    if not member:
        # Removed from the org: fall back to (or create) another workspace
        await db.users.update_one({"uid": user.uid}, {"$unset": {"org_id": ""}})
        org_id = await ensure_org(user)
        member = await db.org_members.find_one({"org_id": org_id, "uid": user.uid})
    return {"org_id": org_id, "role": member["role"] if member else "member"}


async def require_manager(user) -> dict:
    m = await membership(user)
    if m["role"] not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owners and admins can do this")
    return m


async def user_for_api_key(raw: str):
    """AuthUser for a workspace API key, or None if it is unknown/revoked."""
    from app.auth import AuthUser
    key = await db.api_keys.find_one({"key_hash": hash_secret(raw), "revoked_at": None})
    if not key:
        return None
    await db.api_keys.update_one({"_id": key["_id"]}, {"$set": {"last_used_at": datetime.utcnow()}})
    creator = await db.users.find_one({"uid": key["created_by"]}, {"email": 1, "name": 1}) or {}
    return AuthUser(uid=key["created_by"], email=creator.get("email"), name=creator.get("name"),
                    provider="api_key", org_id=key["org_id"])


def email_delivery_configured() -> bool:
    return bool(COMPOSIO_API_KEY)


async def send_invite_email(to: str, org_name: str, inviter: str, url: str) -> Optional[str]:
    """Send the invite through Composio's Gmail tool. Returns an error message, or None on success."""
    if not COMPOSIO_API_KEY:
        return "Email sending is not configured (set COMPOSIO_API_KEY)"
    body = {
        "user_id": COMPOSIO_USER_ID,
        "arguments": {
            "recipient_email": to,
            "subject": f"{inviter} invited you to {org_name} on ResumeAI",
            "is_html": True,
            "body": (
                f"<p>{inviter} invited you to join <b>{org_name}</b> on ResumeAI, "
                f"where your team screens and verifies candidates together.</p>"
                f'<p><a href="{url}">Accept the invitation</a></p>'
                f"<p style=\"color:#756e63;font-size:12px\">Sign in with {to} to accept. The link expires in 14 days.</p>"
            ),
        },
    }
    if COMPOSIO_GMAIL_ACCOUNT_ID:
        body["connected_account_id"] = COMPOSIO_GMAIL_ACCOUNT_ID
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(f"{COMPOSIO_API_URL}/tools/execute/GMAIL_SEND_EMAIL", json=body,
                                   headers={"x-api-key": COMPOSIO_API_KEY})
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400 or data.get("successful") is False:
            err = data.get("error") or data.get("message") or f"HTTP {resp.status_code}"
            return err if isinstance(err, str) else str(err)
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Composio invite email failed: %s", exc)
        return f"Could not reach Composio: {exc}"


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    k = new_api_key()
    assert k.startswith("rai_") and len(k) > 40 and hash_secret(k) == hash_secret(k) and hash_secret(k) != hash_secret(k + "x")
    assert join_url("abc").endswith("/join/abc")
    print("org self-check OK")
