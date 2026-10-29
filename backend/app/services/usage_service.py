"""
Live usage and limits of the external API keys the backend runs on.

Each provider is asked directly where it exposes quota (GitHub rate limits,
Firecrawl credits, Apify monthly spend, Composio connections). Gemini and
Groq have no quota endpoint, so for them the key is validated and the app's
own counts are shown instead.
"""
import asyncio
import os
import time
from datetime import datetime, timezone

import httpx

TIMEOUT = 8
CACHE_SECONDS = 60
_cache = {"at": 0.0, "data": None}


def _metric(label, used=None, limit=None, unit="", resets_at=None):
    return {"label": label, "used": used, "limit": limit, "unit": unit, "resets_at": resets_at}


def _iso(ts):
    if ts in (None, ""):
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return str(ts)


async def _github(http):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"metrics": [], "note": "Without a token GitHub allows only 60 requests an hour."}
    r = await http.get("https://api.github.com/rate_limit", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    res = r.json()["resources"]
    core, search = res["core"], res.get("search", {})
    return {"metrics": [
        _metric("Core API requests", core["used"], core["limit"], "per hour", _iso(core["reset"])),
        _metric("Search requests", search.get("used"), search.get("limit"), "per minute", _iso(search.get("reset"))),
    ]}


async def _firecrawl(http):
    key = os.getenv("FIRECRAWL_API_KEY")
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


async def _apify(http):
    r = await http.get("https://api.apify.com/v2/users/me/limits", params={"token": os.getenv("APIFY_TOKEN")})
    r.raise_for_status()
    d = r.json().get("data") or {}
    return {"metrics": [_metric("Monthly spend", (d.get("current") or {}).get("monthlyUsageUsd"),
                                (d.get("limits") or {}).get("maxMonthlyUsageUsd"), "USD",
                                (d.get("monthlyUsageCycle") or {}).get("endAt"))],
            "note": "Fallback for LinkedIn lookups when Firecrawl finds nothing."}


async def _gemini(http):
    r = await http.get("https://generativelanguage.googleapis.com/v1beta/models",
                       params={"key": os.getenv("GEMINI_API_KEY"), "pageSize": 1})
    r.raise_for_status()
    return {"metrics": [_metric("Concurrent parse calls", None, int(os.getenv("PARSE_CONCURRENCY", "4")), "set by PARSE_CONCURRENCY")],
            "note": "Google doesn't expose remaining quota through the API — see Google AI Studio for exact limits."}


async def _groq(http):
    r = await http.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"})
    r.raise_for_status()
    return {"metrics": [], "note": "Key is valid. Groq reports rate limits per model on each request, not through an API."}


async def _composio(http):
    params = {"toolkit_slugs": "gmail"}
    if os.getenv("COMPOSIO_USER_ID"):
        params["user_ids"] = os.getenv("COMPOSIO_USER_ID")
    r = await http.get(f"{os.getenv('COMPOSIO_API_URL', 'https://backend.composio.dev/api/v3')}/connected_accounts",
                       params=params, headers={"x-api-key": os.getenv("COMPOSIO_API_KEY")})
    r.raise_for_status()
    items = r.json().get("items") or []
    active = [i for i in items if str(i.get("status", "")).upper() == "ACTIVE"]
    return {"metrics": [_metric("Connected Gmail accounts", len(active))],
            "note": "Sends team invitation emails." if active else "No active Gmail connection — invites fall back to copyable links."}


PROVIDERS = [
    # id, name, purpose, env var that enables it, check
    ("gemini", "Google Gemini", "Resume parsing", "GEMINI_API_KEY", _gemini),
    ("github", "GitHub", "Repository verification", "GITHUB_TOKEN", _github),
    ("firecrawl", "Firecrawl", "LinkedIn lookups", "FIRECRAWL_API_KEY", _firecrawl),
    ("apify", "Apify", "LinkedIn fallback", "APIFY_TOKEN", _apify),
    ("groq", "Groq", "Fact checker & interview questions", "GROQ_API_KEY", _groq),
    ("composio", "Composio", "Invite emails via Gmail", "COMPOSIO_API_KEY", _composio),
]


async def _check(http, pid, name, purpose, env, fn):
    row = {"id": pid, "name": name, "purpose": purpose, "env": env, "metrics": [], "note": None, "error": None}
    # GitHub works (rate-limited) without a token; everything else needs its key
    if not os.getenv(env) and pid != "github":
        return {**row, "status": "not_configured"}
    try:
        result = await fn(http)
        status = "ok" if os.getenv(env) else "limited"
        return {**row, **result, "status": status}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        return {**row, "status": "error", "error": "Key rejected" if code in (401, 403) else f"HTTP {code}"}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {**row, "status": "error", "error": f"Unreachable: {type(exc).__name__}"}


async def provider_usage(refresh: bool = False) -> dict:
    """All providers, checked concurrently; cached for a minute."""
    if not refresh and _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        rows = await asyncio.gather(*(_check(http, *p) for p in PROVIDERS))
    data = {"providers": list(rows), "checked_at": datetime.now(timezone.utc).isoformat()}
    _cache.update(at=time.time(), data=data)
    return data


if __name__ == "__main__":
    async def demo():
        async def boom(_):
            raise httpx.ConnectError("x")
        os.environ["X_TEST_KEY"] = "1"
        async with httpx.AsyncClient() as http:
            off = await _check(http, "t", "T", "", "X_MISSING", boom)
            err = await _check(http, "t", "T", "", "X_TEST_KEY", boom)
        assert off["status"] == "not_configured" and err["status"] == "error" and err["error"].startswith("Unreachable")
        print("usage self-check OK")
    asyncio.run(demo())
