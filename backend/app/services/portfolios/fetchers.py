"""Read portfolio and community profiles, all returning the same shape.

Stack Overflow: official Stack Exchange API, no key (300 requests a day per IP).
Kaggle: a direct request only checks the profile exists (404 = not found, no
Firecrawl credit spent); the profile itself is read through Firecrawl.
Behance, Dribbble and personal websites: Firecrawl scrape with JSON extraction.
Our server never fetches a candidate-supplied website itself (SSRF).

Firecrawl cost: one scrape per source per candidate per verification (about 5
credits with JSON extraction; more if Firecrawl needs its enhanced proxy).
Without FIRECRAWL_API_KEY, or with PORTFOLIO_CHECKS_ENABLED=false, those
sources report status "not_configured".

Everything extracted is candidate-controlled text: it is cleaned and capped here
and must be treated as untrusted data downstream.
"""
import asyncio
import html
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from app.services.coding_profiles.fetchers import HEADERS
from app.services.portfolios.links import PLATFORMS, profile_url, public_url

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(8.0, connect=5.0)
FIRECRAWL_PLATFORMS = ("behance", "dribbble", "kaggle", "website")
KAGGLE_TIERS = ["novice", "contributor", "expert", "master", "grandmaster"]
KAGGLE_CATEGORIES = ("competitions", "datasets", "notebooks", "discussions")

_FIELDS = ("name", "headline", "location", "followers", "appreciations", "reputation", "badges", "top_tags",
           "tiers", "medals", "competitions", "projects", "skills", "experience", "education")


class NotFound(Exception):
    pass


class NotConfigured(Exception):
    pass


def _firecrawl_settings() -> tuple:
    """(api key, api url, timeout seconds); read per call so the switch takes effect without a restart."""
    if os.getenv("PORTFOLIO_CHECKS_ENABLED", "true").strip().lower() in ("0", "false", "no", "off"):
        raise NotConfigured("Portfolio checks are switched off (PORTFOLIO_CHECKS_ENABLED)")
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key:
        raise NotConfigured("Firecrawl not configured")
    return key, os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev"), float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "60"))


# ── Cleaning untrusted extraction output ───────────────────────────

def _text(value, limit: int = 200) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit] or None


def _count(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        m = re.fullmatch(r"\s*([\d.,]+)\s*([kKmM]?)\s*", value)
        if not m:
            return None
        try:
            n = float(m.group(1).replace(",", ""))
        except ValueError:
            return None
        value = n * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1)
    if isinstance(value, (int, float)) and 0 <= value < 1e10:
        return int(value)
    return None


def _texts(value, limit: int, item_limit: int = 60) -> List[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        t = _text(v, item_limit)
        if t and t not in out:
            out.append(t)
    return out[:limit]


def _records(value, fields: Dict[str, int], limit: int) -> List[dict]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        if isinstance(v, dict):
            rec = {k: _text(v.get(k), n) for k, n in fields.items()}
            if any(rec.values()):
                out.append(rec)
    return out[:limit]


def clean_portfolio(data) -> dict:
    """Validated subset of a Behance/Dribbble/website extraction."""
    data = data if isinstance(data, dict) else {}
    projects = []
    for p in data.get("projects") if isinstance(data.get("projects"), list) else []:
        if not isinstance(p, dict) or not _text(p.get("title")):
            continue
        link = public_url(p.get("url"), https_only=True)
        projects.append({"title": _text(p["title"], 120), "description": _text(p.get("description"), 300),
                         "tools": _texts(p.get("tools"), 12), "dates": _text(p.get("dates"), 40), "url": link})
    return {
        "name": _text(data.get("name"), 80),
        "headline": _text(data.get("headline"), 160),
        "location": _text(data.get("location"), 80),
        "followers": _count(data.get("followers")),
        "appreciations": _count(data.get("appreciations")),
        "projects": projects[:10],
        "skills": _texts(data.get("skills"), 30),
        "experience": _records(data.get("experience"), {"role": 100, "organisation": 100, "dates": 40}, 10),
        "education": _records(data.get("education"), {"degree": 120, "institution": 120, "dates": 40}, 6),
    }


def clean_kaggle(data) -> dict:
    data = data if isinstance(data, dict) else {}
    raw_tiers = data.get("tiers") if isinstance(data.get("tiers"), dict) else {}
    tiers = {}
    for cat in KAGGLE_CATEGORIES:
        tier = (_text(raw_tiers.get(cat), 20) or "").lower()
        if tier in KAGGLE_TIERS:
            tiers[cat] = tier
    raw_medals = data.get("medals") if isinstance(data.get("medals"), dict) else {}
    medals = {m: _count(raw_medals.get(m)) for m in ("gold", "silver", "bronze") if _count(raw_medals.get(m)) is not None}
    return {
        "name": _text(data.get("name"), 80),
        "headline": _text(data.get("headline"), 160),
        "location": _text(data.get("location"), 80),
        "tiers": tiers,
        "medals": medals,
        "competitions": _count(data.get("competitions")),
    }


# ── Firecrawl ──────────────────────────────────────────────────────

_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}
PORTFOLIO_SCHEMA = {
    "type": "object",
    "properties": {
        "name": _STR, "headline": _STR, "location": _STR,
        "followers": {"type": "integer"}, "appreciations": {"type": "integer"},
        "projects": {"type": "array", "items": {"type": "object", "properties": {
            "title": _STR, "description": _STR, "tools": _STR_LIST, "dates": _STR, "url": _STR}}},
        "skills": _STR_LIST,
        "experience": {"type": "array", "items": {"type": "object", "properties": {
            "role": _STR, "organisation": _STR, "dates": _STR}}},
        "education": {"type": "array", "items": {"type": "object", "properties": {
            "degree": _STR, "institution": _STR, "dates": _STR}}},
    },
}
PORTFOLIO_PROMPT = (
    "Extract the portfolio owner's public profile from this page: their name, headline, location, follower and "
    "appreciation (or like) counts if shown, up to 10 projects (title, short description, tools or technologies, "
    "dates, link), skills, work experience (role, organisation, dates) and education (degree, institution, dates). "
    "Use only what the page states; leave a field empty when it is not shown. Do not include email addresses, "
    "phone numbers or street addresses."
)
KAGGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": _STR, "headline": _STR, "location": _STR,
        "tiers": {"type": "object", "properties": {c: _STR for c in KAGGLE_CATEGORIES}},
        "medals": {"type": "object", "properties": {m: {"type": "integer"} for m in ("gold", "silver", "bronze")}},
        "competitions": {"type": "integer"},
    },
}
KAGGLE_PROMPT = (
    "Extract this Kaggle profile: the user's display name, bio or occupation, location, the progression tier "
    "(Novice, Contributor, Expert, Master or Grandmaster) for each of competitions, datasets, notebooks and "
    "discussions, total gold, silver and bronze medals, and the number of competitions entered. Leave a field "
    "empty when it is not shown."
)


async def firecrawl_extract(client: httpx.AsyncClient, url: str, schema: dict, prompt: str):
    """One Firecrawl scrape of url with JSON extraction. Raises NotFound on a 404 page."""
    key, api_url, timeout = _firecrawl_settings()
    body = {"url": url, "formats": [{"type": "json", "schema": schema, "prompt": prompt}],
            "onlyMainContent": False, "timeout": max(int(timeout * 1000) - 5000, 10000), "proxy": "auto"}
    resp = await client.post(f"{api_url}/v2/scrape", json=body, headers={"Authorization": f"Bearer {key}"},
                             timeout=httpx.Timeout(timeout, connect=10.0))
    resp.raise_for_status()
    data = (resp.json() or {}).get("data") or {}
    if (data.get("metadata") or {}).get("statusCode") in (404, 410):
        raise NotFound
    return data.get("json")


async def fetch_portfolio_page(client: httpx.AsyncClient, platform: str, handle: str) -> dict:
    data = clean_portfolio(await firecrawl_extract(client, profile_url(platform, handle), PORTFOLIO_SCHEMA, PORTFOLIO_PROMPT))
    if not (data["name"] or data["headline"] or data["projects"]):
        raise ValueError("no readable profile on the page")
    return data


async def fetch_kaggle(client: httpx.AsyncClient, handle: str) -> dict:
    # Free existence check first, so a typo costs no Firecrawl credit. Kaggle answers
    # 404 for unknown users only to a plain user agent (a browser one always gets 200).
    r = await client.get(profile_url("kaggle", handle), headers={"User-Agent": "ResumeAI-profile-check"})
    if r.status_code == 404:
        raise NotFound
    data = clean_kaggle(await firecrawl_extract(client, profile_url("kaggle", handle), KAGGLE_SCHEMA, KAGGLE_PROMPT))
    if not (data["name"] or data["tiers"]):
        raise ValueError("no readable profile on the page")
    return data


# ── Stack Overflow (official API) ──────────────────────────────────

_SE_API = "https://api.stackexchange.com/2.3"
_se_backoff_until = 0.0


def _se_backoff(body: dict) -> None:
    """The API asks clients to wait `backoff` seconds before the next call to that method."""
    global _se_backoff_until
    if isinstance(body.get("backoff"), (int, float)):
        _se_backoff_until = max(_se_backoff_until, time.monotonic() + body["backoff"])


async def fetch_stackoverflow(client: httpx.AsyncClient, user_id: str) -> dict:
    if time.monotonic() < _se_backoff_until:
        raise RuntimeError("stack exchange backoff")
    params = {"site": "stackoverflow"}
    r = await client.get(f"{_SE_API}/users/{user_id}", params=params)
    body = r.json() if r.content else {}
    _se_backoff(body)
    if r.status_code != 200 or "error_id" in body:
        raise RuntimeError(f"stack exchange error {body.get('error_id', r.status_code)}")
    user = (body.get("items") or [None])[0]
    if not isinstance(user, dict):
        raise NotFound
    tags = []
    try:
        t = await client.get(f"{_SE_API}/users/{user_id}/top-tags", params={**params, "pagesize": 8})
        tbody = t.json()
        _se_backoff(tbody)
        tags = _texts([i.get("tag_name") for i in tbody.get("items") or [] if isinstance(i, dict)], 8, 40)
    except Exception:
        pass  # top tags are optional
    badges = user.get("badge_counts") if isinstance(user.get("badge_counts"), dict) else {}
    return {
        # Display names come HTML-escaped from the API
        "name": _text(html.unescape(user.get("display_name") or ""), 80),
        "location": _text(html.unescape(user.get("location") or ""), 80),
        "reputation": _count(user.get("reputation")),
        "badges": {k: _count(badges.get(k)) or 0 for k in ("gold", "silver", "bronze")},
        "top_tags": tags,
    }


FETCHERS = {
    "behance": lambda c, h: fetch_portfolio_page(c, "behance", h),
    "dribbble": lambda c, h: fetch_portfolio_page(c, "dribbble", h),
    "website": lambda c, h: fetch_portfolio_page(c, "website", h),
    "kaggle": fetch_kaggle,
    "stackoverflow": fetch_stackoverflow,
}


async def fetch_portfolio(client: httpx.AsyncClient, platform: str, handle: str) -> dict:
    """Common-shape result for one source. Never raises."""
    result = {"platform": platform, "handle": handle, "profile_url": None, "status": "unavailable",
              **{f: None for f in _FIELDS}, "checked_at": datetime.utcnow(), "issues": []}
    try:
        result["profile_url"] = profile_url(platform, handle)
    except (KeyError, ValueError):
        return result
    try:
        result.update(await FETCHERS[platform](client, handle))
        result["status"] = "found"
    except NotFound:
        result["status"] = "not_found"
    except NotConfigured as e:
        result["status"] = "not_configured"
        result["note"] = str(e)
    except Exception as e:
        logger.warning("%s portfolio lookup failed: %s", platform, type(e).__name__)
        result["note"] = "Could not read the profile"
    return result


async def fetch_all(portfolios: Dict[str, str]) -> List[dict]:
    """Look up every listed source concurrently: one request (or one Firecrawl scrape) each."""
    portfolios = {p: h for p, h in (portfolios or {}).items() if p in PLATFORMS}
    if not portfolios:
        return []
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=False) as client:
        return list(await asyncio.gather(*(fetch_portfolio(client, p, h) for p, h in portfolios.items())))
