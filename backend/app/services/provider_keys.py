"""
Per-workspace provider keys ("bring your own key").

A workspace can store its own key for a provider; it is encrypted with
Fernet (PROVIDER_KEYS_SECRET) in ``db.provider_keys``. Code that calls a
provider asks ``key_for(provider)``, which returns the key of the workspace
doing the work, or the server's env var when the workspace has none.

The workspace is set per request (dependency in app.main) and per resume
task (app.routes.resume.process_resume_task) with ``use_org``. It lives in a
ContextVar, so it follows the work into asyncio.create_task and to_thread
and never leaks between concurrent requests.
"""
import logging
import os
import time
from contextvars import ContextVar

from cryptography.fernet import Fernet, InvalidToken

from app.database import db

logger = logging.getLogger(__name__)

# provider id -> server env var
ENV = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "firecrawl": "FIRECRAWL_API_KEY",
    "github": "GITHUB_TOKEN",
    "apify": "APIFY_TOKEN",
    "composio": "COMPOSIO_API_KEY",
}

CACHE_SECONDS = 30
_current: ContextVar[dict] = ContextVar("workspace_provider_keys", default={})
# ponytail: per-process cache, so another process (the worker) may use a
# removed key for up to CACHE_SECONDS; fine for a key the owner just replaced.
_cache: dict = {}  # org_id -> (monotonic time, {provider: key})


def _fernet():
    secret = os.getenv("PROVIDER_KEYS_SECRET", "").strip()
    if not secret:
        return None
    try:
        return Fernet(secret.encode())
    except ValueError:
        logger.error("PROVIDER_KEYS_SECRET is not a valid Fernet key; workspace keys are disabled")
        return None


def enabled() -> bool:
    return _fernet() is not None


def encrypt(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def key_for(provider: str) -> str:
    """The current workspace's key for ``provider``, else the server's; '' if neither."""
    return _current.get().get(provider) or os.getenv(ENV[provider], "")


def source(provider: str) -> str:
    """'workspace', 'server' or 'none': where key_for's answer comes from."""
    if _current.get().get(provider):
        return "workspace"
    return "server" if os.getenv(ENV[provider]) else "none"


async def load(org_id: str) -> dict:
    """{provider: decrypted key} for the workspace, cached briefly."""
    hit = _cache.get(org_id)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    keys = {}
    async for doc in db.provider_keys.find({"org_id": org_id}):
        try:
            keys[doc["provider"]] = decrypt(doc["ciphertext"])
        except InvalidToken:
            # Secret was rotated: the stored key is unreadable, so the server key applies
            logger.warning("Stored %s key of workspace %s can't be decrypted", doc["provider"], org_id)
    _cache[org_id] = (time.monotonic(), keys)
    return keys


async def use_org(org_id) -> None:
    """Make ``org_id``'s keys the ones key_for returns in this context."""
    if org_id and enabled():
        _current.set(await load(org_id))


async def use_user(user) -> None:
    """use_org for the caller's active workspace. Read-only: never creates a workspace (app.org.ensure_org does)."""
    if not enabled():
        return
    org_id = getattr(user, "org_id", None)  # workspace API keys carry theirs
    if not org_id:
        org_id = ((await db.users.find_one({"uid": user.uid}, {"org_id": 1})) or {}).get("org_id")
        # Never spend a workspace's keys for someone who is no longer in it
        if org_id and not await db.org_members.find_one({"org_id": org_id, "uid": user.uid}, {"_id": 1}):
            return
    await use_org(org_id)


def forget(org_id: str) -> None:
    _cache.pop(org_id, None)
