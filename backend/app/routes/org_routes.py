"""
Organization routes: members, email invites, workspace API keys, usage & limits.
"""
import secrets
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from app.auth import AuthUser, get_current_user
from app.database import db
from app.org import (
    email_delivery_configured, hash_secret, join_url, membership, new_api_key, oid, require_manager, send_invite_email,
)
from app.services.usage_service import provider_usage

router = APIRouter(tags=["organization"])

INVITE_TTL = timedelta(days=14)


class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class InviteCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    role: Literal["admin", "member"] = "member"


class RoleUpdate(BaseModel):
    role: Literal["admin", "member"]


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


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
    await db.users.update_one({"uid": uid, "org_id": m["org_id"]}, {"$unset": {"org_id": ""}})
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
    inv = await _pending_invite(token)
    org = await db.orgs.find_one({"_id": ObjectId(inv["org_id"])})
    return {"org_name": org["name"] if org else "Workspace", "email": inv["email"], "role": inv["role"],
            "invited_by": inv.get("invited_by_name"), "email_matches": (user.email or "").lower() == inv["email"]}


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, user: AuthUser = Depends(get_current_user)):
    inv = await _pending_invite(token)
    # The link alone isn't enough: it must be the invited person
    if (user.email or "").lower() != inv["email"]:
        raise HTTPException(403, f"This invitation is for {inv['email']}. Sign in with that email to accept it.")
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
    m = await membership(user)
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    job_ids = [str(j["_id"]) async for j in db.jobs.find({"org_id": m["org_id"]}, {"_id": 1})]
    workspace = {
        "jobs": len(job_ids),
        "active_jobs": await db.jobs.count_documents({"org_id": m["org_id"], "status": "Active"}),
        "candidates_this_month": await db.applications.count_documents({"job_id": {"$in": job_ids}, "application_date": {"$gte": month_start}}),
        "candidates_total": await db.applications.count_documents({"job_id": {"$in": job_ids}}),
        "members": await db.org_members.count_documents({"org_id": m["org_id"]}),
        "api_keys": await db.api_keys.count_documents({"org_id": m["org_id"], "revoked_at": None}),
        "month_start": month_start,
    }
    return {"plan": "Self-hosted", "workspace": workspace, **await provider_usage(refresh)}
