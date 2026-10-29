"""
LinkedIn profile lookup for verification.

Primary: Firecrawl's Alexandria `fullenrich/people/match` (exact profile URL ->
headline, employment history, education, skills). 5 Firecrawl credits per
profile found, 0 when not found.
Fallback: the Apify actor, used when Firecrawl isn't configured, errors, or
finds nothing.

Both return items in the shape unified_verification.py reads (Apify's field
names: positions[].timePeriod, educations[].schoolName, ...).
"""
import os
import asyncio
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")
FIRECRAWL_TIMEOUT = float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "60"))

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "yZnhB5JewWf9xSmoM")

_apify = None
if APIFY_TOKEN:
    from apify_client import ApifyClient
    _apify = ApifyClient(APIFY_TOKEN)


async def scrape_linkedin_profiles(urls: list) -> dict:
    """Look up LinkedIn profiles; Firecrawl first, Apify for any it couldn't resolve."""
    if not FIRECRAWL_API_KEY and not _apify:
        raise Exception("LinkedIn lookup not configured (set FIRECRAWL_API_KEY or APIFY_TOKEN)")

    results, missing = [], list(urls)
    if FIRECRAWL_API_KEY:
        found = await asyncio.gather(*(_firecrawl_lookup(u) for u in urls), return_exceptions=True)
        missing = []
        for url, item in zip(urls, found):
            if isinstance(item, dict):
                results.append(item)
            else:
                if isinstance(item, Exception):
                    logger.warning("Firecrawl LinkedIn lookup failed for %s: %s", url, item)
                missing.append(url)

    if missing and _apify:
        try:
            results.extend(await asyncio.to_thread(_run_apify, missing))
        except Exception as e:
            if not results:
                raise Exception(f"Scraping failed: {e}")
            logger.warning("Apify fallback failed: %s", e)

    return {"status": "success", "data": results}


async def _firecrawl_lookup(url: str) -> dict | None:
    body = {"alexandria": {"provider": "fullenrich", "capability": "people/match", "options": {"linkedin_url": _canonical(url)}}}
    async with httpx.AsyncClient(timeout=FIRECRAWL_TIMEOUT) as http:
        resp = await http.post(f"{FIRECRAWL_API_URL}/v2/scrape", json=body,
                               headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"})
    resp.raise_for_status()
    payload = resp.json()
    calls = (payload.get("data") or {}).get("alexandria") or []
    if isinstance(calls, dict):
        calls = [calls]
    for call in calls:
        if call.get("error"):
            raise Exception(call["error"].get("message") if isinstance(call["error"], dict) else call["error"])
        people = (call.get("data") or {}).get("people") or []
        if people:
            return _to_apify_shape(people[0], url)
    return None


def _canonical(url: str) -> str:
    """https://www.linkedin.com/in/<handle> — fullenrich matches the URL exactly."""
    u = url.strip().split("?")[0].rstrip("/")
    if not u.startswith("http"):
        u = "https://" + u
    return u.replace("://linkedin.com", "://www.linkedin.com").replace("://in.linkedin.com", "://www.linkedin.com")


def _period(start, end):
    def part(value):
        try:
            d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return {"month": d.month, "year": d.year}
        except (TypeError, ValueError):
            return None
    s, e = part(start), part(end)
    return {"startDate": s, "endDate": e} if s or e else None


def _to_apify_shape(p: dict, url: str) -> dict:
    loc = p.get("location") or {}
    jobs = (p.get("employment") or {}).get("all") or []
    profile = (p.get("social_profiles") or {}).get("professional_network") or {}
    return {
        "source": "firecrawl",
        "id": p.get("id"),
        "publicIdentifier": profile.get("handle"),
        "profileUrl": profile.get("url") or url,
        "firstName": p.get("first_name"),
        "lastName": p.get("last_name"),
        "headline": p.get("headline"),
        "summary": p.get("description"),
        "location": ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x) or None,
        "countryCode": loc.get("country_code"),
        "positions": [{
            "title": j.get("title"),
            "companyName": (j.get("company") or {}).get("name"),
            "companyUrl": (j.get("company") or {}).get("website"),
            "timePeriod": _period(j.get("start_at"), j.get("end_at")),
        } for j in jobs],
        "educations": [{
            "schoolName": e.get("school_name"),
            "degreeName": e.get("degree") or e.get("degree_name"),
            "fieldOfStudy": e.get("field_of_study") or e.get("major"),
            "timePeriod": _period(e.get("start_at"), e.get("end_at")),
        } for e in p.get("educations") or []],
        "skills": [s for s in p.get("skills") or [] if isinstance(s, str)],
    }


def _run_apify(urls: list) -> list:
    run = _apify.actor(APIFY_ACTOR_ID).call(run_input={
        "urls": [{"url": u} for u in urls],
        "scrapeCompany": False,
        "findContacts": False,
    })
    return list(_apify.dataset(run["defaultDatasetId"]).iterate_items())


if __name__ == "__main__":
    # Self-check of the mapping with the response shape Firecrawl returned for a real profile
    sample = {"id": "x", "first_name": "Bill", "last_name": "Gates", "headline": "Chair",
              "location": {"city": "Seattle", "region": "Washington", "country": "United States", "country_code": "US"},
              "employment": {"all": [{"title": "Co-founder", "company": {"name": "Microsoft", "website": "https://microsoft.com"},
                                      "start_at": "1975-01-01T00:00:00Z"}]},
              "social_profiles": {"professional_network": {"url": "https://www.linkedin.com/in/williamhgates", "handle": "williamhgates"}},
              "educations": [{"school_name": "Harvard University", "start_at": "1973-01-01T00:00:00Z", "end_at": "1975-01-01T00:00:00Z"}]}
    out = _to_apify_shape(sample, "https://linkedin.com/in/williamhgates/")
    assert out["positions"][0] == {"title": "Co-founder", "companyName": "Microsoft", "companyUrl": "https://microsoft.com",
                                   "timePeriod": {"startDate": {"month": 1, "year": 1975}, "endDate": None}}
    assert out["educations"][0]["timePeriod"]["endDate"] == {"month": 1, "year": 1975}
    assert out["location"] == "Seattle, Washington, United States" and out["publicIdentifier"] == "williamhgates"
    assert _canonical("linkedin.com/in/jane-doe/?trk=x") == "https://www.linkedin.com/in/jane-doe"
    print("linkedinScraper self-check OK")
