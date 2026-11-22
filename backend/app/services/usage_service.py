"""
Live status and limits of the external API keys the backend runs on.

Each provider is asked directly where it exposes quota (GitHub rate limits,
Firecrawl credits, Apify monthly spend, Composio connections). Gemini and
Groq have no quota endpoint, so for them the key and model are validated.

Checks use the effective key (app.services.provider_keys.key_for): the
workspace's own key when it has one, else the server's. Keys always travel
in headers, never in URLs.
"""
import asyncio
import hashlib
import os
import time
from datetime import datetime, timezone

import httpx

from app.services.provider_keys import key_for, source

TIMEOUT = 8
CACHE_SECONDS = 60
GEMINI_MODEL = "gemini-2.5-flash"
_cache: dict = {}  # (provider, key fingerprint) -> (time, row)


def _metric(label, used=None, limit=None, unit="", resets_at=None):
    return {"label": label, "used": used, "limit": limit, "unit": unit, "resets_at": resets_at}


def _iso(ts):
    if ts in (None, ""):
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return str(ts)


async def _github(http, key):
    if not key:
        return {"metrics": [], "note": "Without a token GitHub allows only 60 requests an hour."}
    r = await http.get("https://api.github.com/rate_limit", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    res = r.json()["resources"]
    core, search = res["core"], res.get("search", {})
    return {"metrics": [
        _metric("Core API requests", core["used"], core["limit"], "per hour", _iso(core["reset"])),
        _metric("Search requests", search.get("used"), search.get("limit"), "per minute", _iso(search.get("reset"))),
    ]}


async def _firecrawl(http, key):
    base = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
    r = await http.get(f"{base}/v2/team/credit-usage", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    d = r.json().get("data") or {}
    remaining = d.get("remainingCredits", d.get("remaining_credits"))
    plan = d.get("planCredits", d.get("plan_credits"))
    used = plan - remaining if isinstance(plan, (int, float)) and isinstance(remaining, (int, float)) else None
    return {"metrics": [_metric("Credits", used, plan, "this billing period",
                                d.get("billingPeriodEnd") or d.get("billing_period_end"))],
            "note": "LinkedIn lookups cost 5 credits per profile found."}


async def _apify(http, key):
    r = await http.get("https://api.apify.com/v2/users/me/limits", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    d = r.json().get("data") or {}
    return {"metrics": [_metric("Monthly spend", (d.get("current") or {}).get("monthlyUsageUsd"),
                                (d.get("limits") or {}).get("maxMonthlyUsageUsd"), "USD",
                                (d.get("monthlyUsageCycle") or {}).get("endAt"))],
            "note": "Fallback for LinkedIn lookups when Firecrawl finds nothing."}


async def _gemini(http, key):
    r = await http.get(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}",
                       headers={"x-goog-api-key": key})
    # Google retires models too, and then every parse fails
    if r.status_code == 404:
        return {"metrics": [], "status": "error", "error": f"Model {GEMINI_MODEL} is no longer available."}
    r.raise_for_status()
    return {"metrics": [_metric("Concurrent parse calls", None, int(os.getenv("PARSE_CONCURRENCY", "4")), "set by PARSE_CONCURRENCY")],
            "note": f"Key is valid and {GEMINI_MODEL} is available. Google doesn't expose remaining quota through the API; see Google AI Studio."}


async def _groq(http, key):
    r = await http.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    # A valid key isn't enough: Groq retires models, and then every AI call fails
    from app.services.interview_questions_service import GROQ_MODEL
    if GROQ_MODEL not in {m.get("id") for m in r.json().get("data", [])}:
        return {"metrics": [], "status": "error",
                "error": f"Model {GROQ_MODEL} is no longer available. Set GROQ_MODEL to a current Groq model."}
    return {"metrics": [], "note": f"Key is valid and {GROQ_MODEL} is available. Groq reports rate limits per model on each request, not through an API."}


async def _composio(http, key):
    params = {"toolkit_slugs": "gmail"}
    if os.getenv("COMPOSIO_USER_ID"):
        params["user_ids"] = os.getenv("COMPOSIO_USER_ID")
    r = await http.get(f"{os.getenv('COMPOSIO_API_URL', 'https://backend.composio.dev/api/v3')}/connected_accounts",
                       params=params, headers={"x-api-key": key})
    r.raise_for_status()
    items = r.json().get("items") or []
    active = [i for i in items if str(i.get("status", "")).upper() == "ACTIVE"]
    return {"metrics": [_metric("Connected Gmail accounts", len(active))],
            "note": "Sends team invitation emails." if active else "No active Gmail connection: invites fall back to copyable links."}


# id: (name, what ResumeAI uses it for, check)
PROVIDERS = {
    "gemini": ("Google Gemini", "Resume parsing, project reviews and GitHub analysis", _gemini),
    "groq": ("Groq", "Interview questions and the fact checker", _groq),
    "firecrawl": ("Firecrawl", "LinkedIn lookups, portfolio and project pages", _firecrawl),
    "github": ("GitHub", "Repository verification", _github),
    "apify": ("Apify", "LinkedIn fallback when Firecrawl finds nothing", _apify),
    "composio": ("Composio", "Team invite emails via Gmail", _composio),
}
AI_PROVIDERS = ("gemini", "groq")
INTEGRATION_PROVIDERS = ("firecrawl", "github", "apify", "composio")


async def check(pid: str, key: str = None, refresh: bool = False) -> dict:
    """Status row for one provider with ``key`` (default: the effective key); cached a minute per key."""
    name, purpose, fn = PROVIDERS[pid]
    key = key_for(pid) if key is None else key
    ck = (pid, hashlib.sha256(key.encode()).hexdigest())
    hit = _cache.get(ck)
    if hit and not refresh and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    row = {"id": pid, "name": name, "purpose": purpose, "metrics": [], "note": None, "error": None,
           "checked_at": datetime.now(timezone.utc).isoformat()}
    # GitHub works (rate-limited) without a token; everything else needs its key
    if not key and pid != "github":
        return {**row, "status": "not_configured"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as http:
            result = await fn(http, key)
        row = {**row, "status": "ok" if key else "limited", **result}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        row = {**row, "status": "error", "error": "Key rejected" if code in (400, 401, 403) else f"HTTP {code}"}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        row = {**row, "status": "error", "error": f"Unreachable: {type(exc).__name__}"}
    _cache[ck] = (time.time(), row)
    return row


async def provider_status(pids, refresh: bool = False) -> list:
    """Rows for ``pids``, checked concurrently, each with where its key comes from."""
    rows = await asyncio.gather(*(check(p, refresh=refresh) for p in pids))
    return [{**r, "source": source(r["id"])} for r in rows]


if __name__ == "__main__":
    async def demo():
        async def boom(_http, _key):
            raise httpx.ConnectError("x")
        PROVIDERS["t"] = ("T", "", boom)
        from app.services.provider_keys import ENV
        ENV["t"] = "X_MISSING"
        off = await check("t")
        err = await check("t", key="k")
        assert off["status"] == "not_configured" and err["status"] == "error" and err["error"].startswith("Unreachable")
        print("usage self-check OK")
    asyncio.run(demo())
