"""
Per-workspace daily quotas (MongoDB) and a per-user request rate limit (memory)
for the routes that spend money on external APIs: resume uploads (Gemini) and
AI calls (Groq interview questions and fact checks).
"""
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument

from app.database import db

# kind: (env var, default per day, what the limit counts)
QUOTAS = {
    "resume_upload": ("QUOTA_RESUME_UPLOADS_PER_DAY", 500, "resume uploads"),
    "ai_call": ("QUOTA_AI_CALLS_PER_DAY", 300, "AI calls (interview questions and fact checks)"),
}


async def use_quota(org_id: str, kind: str, amount: int = 1):
    """Count ``amount`` against the workspace's limit for today (UTC); 429 if it would go over."""
    env, default, label = QUOTAS[kind]
    limit = int(os.getenv(env, str(default)))
    now = datetime.now(timezone.utc)
    resets_at = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    key = {"_id": f"{org_id}:{kind}:{now.date().isoformat()}"}
    # Atomic $inc, then give the units back if that took us over the limit
    doc = await db.usage_quotas.find_one_and_update(
        key,
        {"$inc": {"count": amount},
         "$setOnInsert": {"org_id": org_id, "kind": kind,
                          # TTL index (app.database) removes old days
                          "expires_at": (resets_at + timedelta(days=1)).replace(tzinfo=None)}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    if doc["count"] > limit:
        await db.usage_quotas.update_one(key, {"$inc": {"count": -amount}})
        used = doc["count"] - amount
        raise HTTPException(429, (
            f"Daily limit reached: your workspace can make {limit} {label} per day "
            f"and has used {used}" + (f" ({amount} requested)" if amount > 1 else "") +
            f". The limit resets at 00:00 UTC ({resets_at.strftime('%Y-%m-%d %H:%M')} UTC)."
        ))


# ponytail: in-memory sliding window, so each process (API server, worker
# replicas) keeps its own count and restarts reset it; move to Redis or a
# Mongo counter if the backend runs more than one API process.
_hits = defaultdict(deque)


def rate_limit(uid: str, bucket: str):
    """At most RATE_LIMIT_PER_MINUTE requests per user per bucket in any 60 seconds; 429 otherwise."""
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    now = time.monotonic()
    hits = _hits[(uid, bucket)]
    while hits and now - hits[0] >= 60:
        hits.popleft()
    if len(hits) >= limit:
        wait = int(60 - (now - hits[0])) + 1
        raise HTTPException(429, f"Too many requests: at most {limit} per minute. Try again in {wait} seconds.",
                            headers={"Retry-After": str(wait)})
    hits.append(now)
