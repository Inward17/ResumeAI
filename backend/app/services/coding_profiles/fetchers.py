"""One small fetcher per platform, all returning the same shape.

LeetCode (GraphQL) and HackerRank (REST) are public but unofficial endpoints,
Codeforces has an official API, HackerEarth and CodeChef are read from their
profile pages. Page readers fail soft: if the layout changed they report the
profile as unavailable rather than guess numbers.
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import lxml.html

from app.services.coding_profiles.handles import PROFILE_URLS, profile_url, valid_handle

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(8.0, connect=5.0)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en",
}


class NotFound(Exception):
    pass


class LayoutChanged(Exception):
    pass


def _int(value) -> Optional[int]:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


# ── LeetCode ────────────────────────────────────────────────────────

_LEETCODE_QUERY = """query profile($u: String!) {
  matchedUser(username: $u) { username profile { realName } submitStatsGlobal { acSubmissionNum { difficulty count } } }
  userContestRanking(username: $u) { rating attendedContestsCount badge { name } }
}"""


async def fetch_leetcode(client: httpx.AsyncClient, handle: str) -> dict:
    r = await client.post("https://leetcode.com/graphql", json={"query": _LEETCODE_QUERY, "variables": {"u": handle}},
                          headers={"Referer": "https://leetcode.com"})
    r.raise_for_status()
    data = r.json().get("data") or {}
    user = data.get("matchedUser")
    if not user:
        raise NotFound
    solved = {s.get("difficulty"): s.get("count") for s in (user.get("submitStatsGlobal") or {}).get("acSubmissionNum") or []}
    contest = data.get("userContestRanking") or {}
    return {
        "name": ((user.get("profile") or {}).get("realName") or "").strip() or None,
        "problems_solved": _int(solved.get("All")),
        "rating": _int(contest.get("rating")),
        "title": (contest.get("badge") or {}).get("name"),
        "contests": _int(contest.get("attendedContestsCount")),
    }


# ── HackerRank ──────────────────────────────────────────────────────

async def fetch_hackerrank(client: httpx.AsyncClient, handle: str) -> dict:
    base = "https://www.hackerrank.com/rest"
    profile, badges = await asyncio.gather(
        client.get(f"{base}/contests/master/hackers/{handle}/profile"),
        client.get(f"{base}/hackers/{handle}/badges"),
    )
    if profile.status_code == 404:
        raise NotFound
    profile.raise_for_status()
    model = profile.json().get("model")
    if not isinstance(model, dict):
        raise LayoutChanged("no profile model")
    name = (model.get("name") or " ".join(filter(None, [model.get("personal_first_name"), model.get("personal_last_name")]))).strip()
    badge_list: List[dict] = []
    if badges.status_code == 200:
        for b in badges.json().get("models") or []:
            if isinstance(b, dict) and b.get("badge_name"):
                badge_list.append({"name": b["badge_name"], "stars": _int(b.get("stars")) or 0, "solved": _int(b.get("solved"))})
    best = max(badge_list, key=lambda b: b["stars"], default=None)
    solved = [b["solved"] for b in badge_list if b["solved"] is not None]
    return {
        "name": name or None,
        "problems_solved": sum(solved) if solved else None,
        "stars": best["stars"] if best else None,
        "title": f"{best['stars']}★ {best['name']}" if best and best["stars"] else None,
        "badges": badge_list,
    }


# ── Codeforces (official API) ───────────────────────────────────────

async def fetch_codeforces(client: httpx.AsyncClient, handle: str) -> dict:
    r = await client.get("https://codeforces.com/api/user.info", params={"handles": handle})
    body = r.json()
    if body.get("status") != "OK":
        if "not found" in str(body.get("comment", "")).lower():
            raise NotFound
        raise RuntimeError("codeforces api error")
    user = (body.get("result") or [None])[0]
    if not isinstance(user, dict):
        raise LayoutChanged("no user")
    contests = None
    try:
        # Codeforces allows about one call per two seconds; the count is optional
        hist = (await client.get("https://codeforces.com/api/user.rating", params={"handle": handle})).json()
        if hist.get("status") == "OK":
            contests = len(hist.get("result") or [])
    except Exception:
        pass
    return {
        "name": " ".join(filter(None, [user.get("firstName"), user.get("lastName")])).strip() or None,
        "rating": _int(user.get("rating")),
        "max_rating": _int(user.get("maxRating")),
        "title": user.get("rank"),
        "max_title": user.get("maxRank"),
        "contests": contests,
    }


# ── HackerEarth (page) ──────────────────────────────────────────────

_HE_NAME = re.compile(r'"full_name":"((?:[^"\\]|\\.)*)"')
_HE_BADGE = re.compile(r'"name":"([A-Za-z ]+)","description":"[^"]*","level":(\d+),"points":\d+,[^{}]*"category":"he_level"')
_HE_POINTS = re.compile(r'"global_badge_progress":\{"current_score":(\d+)')


def parse_hackerearth(html: str) -> dict:
    # The profile data sits in an escaped JSON string in the page's scripts
    text = html.replace('\\"', '"')
    m = _HE_NAME.search(text)
    if not m or '"profileData"' not in text:
        raise LayoutChanged("no profile data")
    try:
        name = json.loads(f'"{m.group(1)}"').strip()
    except ValueError:
        name = None
    levels = [(int(lvl), title) for title, lvl in _HE_BADGE.findall(text)]
    points = _HE_POINTS.search(text)
    return {
        "name": name or None,
        "title": max(levels)[1] if levels else None,
        "rating": None,
        "points": int(points.group(1)) if points else None,
    }


async def fetch_hackerearth(client: httpx.AsyncClient, handle: str) -> dict:
    r = await client.get(profile_url("hackerearth", handle))
    if r.status_code == 404:
        raise NotFound
    if r.status_code != 200:
        raise RuntimeError(f"status {r.status_code}")
    return parse_hackerearth(r.text)


# ── CodeChef (page) ─────────────────────────────────────────────────

_CODECHEF_STARS = [(2500, 7), (2200, 6), (2000, 5), (1800, 4), (1600, 3), (1400, 2), (0, 1)]


def codechef_stars(rating: Optional[int]) -> Optional[int]:
    if rating is None:
        return None
    return next(stars for floor, stars in _CODECHEF_STARS if rating >= floor)


def parse_codechef(html: str) -> dict:
    doc = lxml.html.fromstring(html)
    heading = doc.xpath('//div[contains(@class,"user-details-container")]//h1')
    blocks = doc.xpath('//div[@id="rating-block-all"]') or doc.xpath('//div[contains(@class,"rating-header")]')
    if not heading or not blocks:
        raise LayoutChanged("no profile header")
    block = blocks[0]
    number = block.xpath('.//div[contains(@class,"rating-number")]')
    rating = number[0].text_content().strip() if number else ""
    star_spans = block.xpath('.//div[contains(@class,"rating-star")]/span')
    block_text = block.text_content()
    highest = re.search(r"Highest Rating\s*(\d+)", block_text)
    page_text = doc.text_content()
    solved = re.search(r"Total Problems Solved:\s*(\d+)", page_text)
    contests = re.search(r"Contests Participated:\s*(\d+)", page_text)
    rating = int(rating) if rating.isdigit() else None
    max_rating = int(highest.group(1)) if highest else None
    return {
        "name": heading[0].text_content().strip() or None,
        "rating": rating,
        "max_rating": max_rating if max_rating else rating,
        "stars": len(star_spans) or codechef_stars(rating),
        "title": f"{len(star_spans)}★" if star_spans else None,
        "problems_solved": int(solved.group(1)) if solved else None,
        "contests": int(contests.group(1)) if contests else None,
    }


async def fetch_codechef(client: httpx.AsyncClient, handle: str) -> dict:
    r = await client.get(profile_url("codechef", handle))
    # Unknown users are redirected to the home page
    if r.status_code in (301, 302, 404):
        raise NotFound
    if r.status_code != 200:
        raise RuntimeError(f"status {r.status_code}")
    return parse_codechef(r.text)


FETCHERS = {
    "leetcode": fetch_leetcode,
    "hackerrank": fetch_hackerrank,
    "hackerearth": fetch_hackerearth,
    "codeforces": fetch_codeforces,
    "codechef": fetch_codechef,
}

_FIELDS = ("name", "problems_solved", "rating", "max_rating", "title", "max_title", "stars", "contests")


async def fetch_profile(client: httpx.AsyncClient, platform: str, handle: str) -> dict:
    """Common-shape result for one profile. Never raises."""
    result = {"platform": platform, "handle": handle, "profile_url": None, "status": "unavailable",
              **{f: None for f in _FIELDS}, "checked_at": datetime.utcnow(), "issues": []}
    if platform not in FETCHERS or not valid_handle(platform, handle):
        return result
    result["profile_url"] = profile_url(platform, handle)
    try:
        data = await FETCHERS[platform](client, handle)
        result.update(data)
        result["status"] = "found"
    except NotFound:
        result["status"] = "not_found"
    except LayoutChanged:
        logger.warning("%s profile page layout changed; could not read it", platform)
        result["note"] = "Could not read the profile page"
    except Exception as e:
        logger.warning("%s profile lookup failed: %s", platform, type(e).__name__)
    return result


async def fetch_all(handles: Dict[str, str]) -> List[dict]:
    """Look up every listed profile concurrently."""
    handles = {p: h for p, h in (handles or {}).items() if p in PROFILE_URLS}
    if not handles:
        return []
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=False) as client:
        return list(await asyncio.gather(*(fetch_profile(client, p, h) for p, h in handles.items())))
