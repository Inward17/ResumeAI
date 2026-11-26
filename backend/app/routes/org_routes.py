"""
Organization routes: members, email invites, workspace API keys, AI usage,
provider integrations (workspace keys) and plan & usage.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from app.auth import AuthUser, get_current_user
from app.database import db
from app.org import (
    PERMISSIONS, email_delivery_configured, hash_secret, job_filter, join_url, membership, new_api_key, oid,
    reject_api_key, require_manager, send_invite_email,
)
from app.services import provider_keys
from app.services.quota import QUOTAS, quota_limit, rate_limit
from app.services.usage_service import AI_PROVIDERS, INTEGRATION_PROVIDERS, PROVIDERS, check, provider_status

router = APIRouter(tags=["organization"])

INVITE_TTL = timedelta(days=14)


class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


# Every role but owner: there is one owner, set when the workspace is created
AssignableRole = Literal["admin", "member", "hiring_manager", "interviewer"]


class InviteCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    role: AssignableRole = "member"


class RoleUpdate(BaseModel):
    role: AssignableRole


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class ProviderKeyIn(BaseModel):
    # No whitespace or newlines anywhere: a key goes straight into a request header
    key: str = Field(min_length=8, max_length=512, pattern=r"^[!-~]+$")


def _invite_out(inv: dict, include_link: bool) -> dict:
    out = {
        "id": str(inv["_id"]), "email": inv["email"], "role": inv["role"], "status": inv["status"],
        "invited_by": inv.get("invited_by_name"), "created_at": inv["created_at"], "expires_at": inv["expires_at"],
        "email_sent": inv.get("email_sent", False), "email_error": inv.get("email_error"),
    }
    if include_link:
        out["join_url"] = join_url(inv["token"])
    return out


def _key_out(k: dict) -> dict:
    return {"id": str(k["_id"]), "name": k["name"], "prefix": k["prefix"], "created_by": k.get("created_by_name"),
            "created_at": k["created_at"], "last_used_at": k.get("last_used_at")}


# ── Organization & members ──────────────────────────────────────────────

@router.get("/org")
async def get_org(user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    m = await membership(user)
    org = await db.orgs.find_one({"_id": ObjectId(m["org_id"])})
    members = await db.org_members.find({"org_id": m["org_id"]}, {"_id": 0}).sort("joined_at", 1).to_list(500)
    pictures = {u["uid"]: u.get("picture") async for u in db.users.find({"uid": {"$in": [x["uid"] for x in members]}}, {"uid": 1, "picture": 1})}
    manager = m["role"] in ("owner", "admin")
    invites = []
    if manager:
        invites = [_invite_out(i, True) async for i in db.invites.find({"org_id": m["org_id"], "status": "pending"}).sort("created_at", -1)]
    return {
        "id": m["org_id"], "name": org["name"] if org else "Workspace", "role": m["role"], "me": user.uid,
        # What the caller may do with jobs and candidates, so the UI can hide the rest (the API enforces it)
        "permissions": sorted(PERMISSIONS.get(m["role"], ())),
        "members": [{**x, "picture": pictures.get(x["uid"])} for x in members],
        "invites": invites,
        "email_delivery": email_delivery_configured(),
    }


@router.patch("/org")
async def rename_org(body: OrgUpdate, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    await db.orgs.update_one({"_id": ObjectId(m["org_id"])}, {"$set": {"name": body.name.strip()}})
    return {"name": body.name.strip()}


@router.patch("/org/members/{uid}")
async def change_role(uid: str, body: RoleUpdate, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    target = await db.org_members.find_one({"org_id": m["org_id"], "uid": uid})
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(400, "The owner's role can't be changed")
    await db.org_members.update_one({"_id": target["_id"]}, {"$set": {"role": body.role}})
    return {"uid": uid, "role": body.role}


@router.delete("/org/members/{uid}")
async def remove_member(uid: str, user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    m = await membership(user)
    target = await db.org_members.find_one({"org_id": m["org_id"], "uid": uid})
    if not target:
        raise HTTPException(404, "Member not found")
    leaving = uid == user.uid
    if not leaving and m["role"] not in ("owner", "admin"):
        raise HTTPException(403, "Only owners and admins can remove members")
    if target["role"] == "owner":
        raise HTTPException(400, "The owner can't leave or be removed")
    await db.org_members.delete_one({"_id": target["_id"]})
    # Their keys for this workspace stop working with them
    await db.api_keys.update_many({"org_id": m["org_id"], "created_by": uid, "revoked_at": None},
                                  {"$set": {"revoked_at": datetime.utcnow()}})
    await db.users.update_one({"uid": uid, "org_id": m["org_id"]}, {"$unset": {"org_id": ""}})
    await db.jobs.update_many({"org_id": m["org_id"]}, {"$pull": {"team_uids": uid}})
    return {"removed": uid}


# ── Invites ─────────────────────────────────────────────────────────────

@router.post("/org/invites")
async def create_invite(body: InviteCreate, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    email = body.email.strip().lower()
    if await db.org_members.find_one({"org_id": m["org_id"], "email": email}):
        raise HTTPException(409, f"{email} is already a member")
    # Re-inviting replaces the earlier pending invite
    await db.invites.update_many({"org_id": m["org_id"], "email": email, "status": "pending"}, {"$set": {"status": "revoked"}})

    org = await db.orgs.find_one({"_id": ObjectId(m["org_id"])})
    now = datetime.utcnow()
    inviter = user.name or user.email or "A teammate"
    invite = {
        "org_id": m["org_id"], "email": email, "role": body.role, "token": secrets.token_urlsafe(24),
        "status": "pending", "invited_by": user.uid, "invited_by_name": inviter,
        "created_at": now, "expires_at": now + INVITE_TTL,
    }
    error = await send_invite_email(email, org["name"] if org else "a workspace", inviter, join_url(invite["token"]))
    invite.update(email_sent=error is None, email_error=error)
    invite["_id"] = (await db.invites.insert_one(invite)).inserted_id
    return _invite_out(invite, True)


@router.delete("/org/invites/{invite_id}")
async def revoke_invite(invite_id: str, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    res = await db.invites.update_one({"_id": oid(invite_id), "org_id": m["org_id"], "status": "pending"},
                                      {"$set": {"status": "revoked"}})
    if not res.modified_count:
        raise HTTPException(404, "Invite not found")
    return {"revoked": invite_id}


async def _pending_invite(token: str) -> dict:
    inv = await db.invites.find_one({"token": token})
    if not inv or inv["status"] != "pending":
        raise HTTPException(404, "This invitation is no longer valid")
    if inv["expires_at"] < datetime.utcnow():
        raise HTTPException(410, "This invitation has expired — ask for a new one")
    return inv


@router.get("/invites/{token}")
async def preview_invite(token: str, user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    inv = await _pending_invite(token)
    org = await db.orgs.find_one({"_id": ObjectId(inv["org_id"])})
    return {"org_name": org["name"] if org else "Workspace", "email": inv["email"], "role": inv["role"],
            "invited_by": inv.get("invited_by_name"), "email_matches": user.email_verified and (user.email or "").lower() == inv["email"],
            "email_verified": user.email_verified}


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    inv = await _pending_invite(token)
    # The link alone isn't enough: it must be the invited person, with a verified address
    if (user.email or "").lower() != inv["email"]:
        raise HTTPException(403, f"This invitation is for {inv['email']}. Sign in with that email to accept it.")
    if not user.email_verified:
        raise HTTPException(403, "Verify your email address, then open this invitation again.")
    now = datetime.utcnow()
    await db.org_members.update_one(
        {"org_id": inv["org_id"], "uid": user.uid},
        {"$setOnInsert": {"org_id": inv["org_id"], "uid": user.uid, "email": inv["email"], "name": user.name,
                          "role": inv["role"], "joined_at": now}},
        upsert=True,
    )
    await db.users.update_one({"uid": user.uid}, {"$set": {"org_id": inv["org_id"]}}, upsert=True)
    await db.invites.update_one({"_id": inv["_id"]}, {"$set": {"status": "accepted", "accepted_by": user.uid, "accepted_at": now}})
    return {"org_id": inv["org_id"]}


# ── Workspace API keys ──────────────────────────────────────────────────

@router.get("/org/api-keys")
async def list_api_keys(user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    m = await membership(user)
    return [_key_out(k) async for k in db.api_keys.find({"org_id": m["org_id"], "revoked_at": None}).sort("created_at", -1)]


@router.post("/org/api-keys")
async def create_api_key(body: ApiKeyCreate, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    raw = new_api_key()
    doc = {"org_id": m["org_id"], "name": body.name.strip(), "prefix": raw[:12], "key_hash": hash_secret(raw),
           "created_by": user.uid, "created_by_name": user.name or user.email, "created_at": datetime.utcnow(),
           "last_used_at": None, "revoked_at": None}
    doc["_id"] = (await db.api_keys.insert_one(doc)).inserted_id
    # The full key is returned once and never stored
    return {**_key_out(doc), "key": raw}


@router.delete("/org/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    res = await db.api_keys.update_one({"_id": oid(key_id), "org_id": m["org_id"], "revoked_at": None},
                                       {"$set": {"revoked_at": datetime.utcnow()}})
    if not res.modified_count:
        raise HTTPException(404, "API key not found")
    return {"revoked": key_id}


# ── Plan & usage ────────────────────────────────────────────────────────

@router.get("/org/usage")
async def get_usage(refresh: bool = False, user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    m = await membership(user)
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Restricted roles count only the jobs they are assigned to
    jobs = job_filter({**m, "uid": user.uid})
    job_ids = [str(j["_id"]) async for j in db.jobs.find(jobs, {"_id": 1})]
    workspace = {
        "jobs": len(job_ids),
        "active_jobs": await db.jobs.count_documents({**jobs, "status": "Active"}),
        "candidates_this_month": await db.applications.count_documents({"job_id": {"$in": job_ids}, "application_date": {"$gte": month_start}}),
        "candidates_total": await db.applications.count_documents({"job_id": {"$in": job_ids}}),
        "members": await db.org_members.count_documents({"org_id": m["org_id"]}),
        "api_keys": await db.api_keys.count_documents({"org_id": m["org_id"], "revoked_at": None}),
        "month_start": month_start,
    }
    return {"plan": "Self-hosted", "workspace": workspace}


# ── AI usage ────────────────────────────────────────────────────────────

HISTORY_DAYS = 30


@router.get("/org/ai-usage")
async def get_ai_usage(refresh: bool = False, user: AuthUser = Depends(get_current_user)):
    """Today's AI calls and uploads against the daily limits, by feature, the last 30 days, and Gemini/Groq status."""
    reject_api_key(user)
    m = await membership(user)
    now = datetime.now(timezone.utc)
    today = now.date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(HISTORY_DAYS - 1, -1, -1)]
    counts = {}  # (kind, date) -> doc
    async for d in db.usage_quotas.find({"org_id": m["org_id"]}):
        kind, date = d["_id"].rsplit(":", 2)[1:]
        counts[(kind, date)] = d
    used = lambda kind, date: (counts.get((kind, date)) or {}).get("count", 0)
    features = {**(counts.get(("ai_call", days[-1])) or {}).get("features", {}),
                **(counts.get(("resume_upload", days[-1])) or {}).get("features", {})}
    return {
        "today": {kind: {"used": used(kind, days[-1]), "limit": quota_limit(kind), "label": QUOTAS[kind][2]} for kind in QUOTAS},
        "features": features,
        "resets_at": datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat(),
        "history": [{"date": d, "ai_calls": used("ai_call", d), "uploads": used("resume_upload", d)} for d in days],
        "providers": await provider_status(AI_PROVIDERS, refresh),
    }


# ── Integrations (workspace provider keys) ──────────────────────────────

def _provider(pid: str) -> str:
    if pid not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    return pid


@router.get("/org/integrations")
async def list_integrations(refresh: bool = False, user: AuthUser = Depends(get_current_user)):
    """Every provider with where its key comes from and its live status. Stored keys never leave the server."""
    reject_api_key(user)
    m = await membership(user)
    saved = {k["provider"]: k async for k in db.provider_keys.find({"org_id": m["org_id"]})}
    rows = await provider_status(AI_PROVIDERS + INTEGRATION_PROVIDERS, refresh)
    for row in rows:
        k = saved.get(row["id"])
        row["workspace_key"] = {"last4": k["last4"], "added_by": k.get("added_by_name"), "added_at": k["added_at"]} if k else None
    return {"providers": rows, "can_manage": m["role"] in ("owner", "admin"), "keys_enabled": provider_keys.enabled()}


@router.post("/org/integrations/{pid}/test")
async def test_integration(pid: str, user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    await membership(user)
    rate_limit(user.uid, "provider_test")
    row = await check(_provider(pid), refresh=True)
    return {**row, "source": provider_keys.source(pid)}


@router.put("/org/integrations/{pid}")
async def save_provider_key(pid: str, body: ProviderKeyIn, user: AuthUser = Depends(get_current_user)):
    """Store the workspace's own key, only after the provider accepts it."""
    m = await require_manager(user)
    rate_limit(user.uid, "provider_keys")
    _provider(pid)
    if not provider_keys.enabled():
        raise HTTPException(400, "Set PROVIDER_KEYS_SECRET on the server to allow workspace keys")
    row = await check(pid, key=body.key, refresh=True)
    if row["status"] != "ok":
        raise HTTPException(400, f"{row['name']} didn't accept this key: {row.get('error') or 'check failed'}. Nothing was saved.")
    await db.provider_keys.update_one(
        {"org_id": m["org_id"], "provider": pid},
        {"$set": {"ciphertext": provider_keys.encrypt(body.key), "last4": body.key[-4:], "added_by": user.uid,
                  "added_by_name": user.name or user.email, "added_at": datetime.utcnow()}},
        upsert=True,
    )
    provider_keys.forget(m["org_id"])
    return {"provider": pid, "source": "workspace", "last4": body.key[-4:]}


@router.delete("/org/integrations/{pid}")
async def remove_provider_key(pid: str, user: AuthUser = Depends(get_current_user)):
    m = await require_manager(user)
    rate_limit(user.uid, "provider_keys")
    res = await db.provider_keys.delete_one({"org_id": m["org_id"], "provider": _provider(pid)})
    if not res.deleted_count:
        raise HTTPException(404, "This workspace has no key for that provider")
    provider_keys.forget(m["org_id"])
    return {"removed": pid}
