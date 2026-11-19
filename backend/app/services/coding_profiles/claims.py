"""Competitive-programming claims on a resume, and checks against fetched profiles."""
import re
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from app.services.coding_profiles.fetchers import codechef_stars

_PLATFORM_WORDS = {
    "leetcode": r"leet\s?code",
    "hackerrank": r"hacker\s?rank",
    "hackerearth": r"hacker\s?earth",
    "codeforces": r"code\s?forces",
    "codechef": r"code\s?chef",
}
_PLATFORM_RE = {p: re.compile(rf"\b{w}\b", re.I) for p, w in _PLATFORM_WORDS.items()}

CF_RANKS = ["newbie", "pupil", "specialist", "expert", "candidate master", "master",
            "international master", "grandmaster", "international grandmaster", "legendary grandmaster", "tourist"]
_CF_RANK_RE = re.compile(r"\b(" + "|".join(sorted(CF_RANKS, key=len, reverse=True)) + r")\b", re.I)
LEETCODE_BADGES = ["knight", "guardian"]
_LC_BADGE_RE = re.compile(r"\b(knight|guardian)\b", re.I)

_RATING_RE = re.compile(r"(?:rating|rated)\D{0,12}?(\d{3,4})\b|\b(\d{3,4})\s*\+?\s*(?:max\s+|peak\s+)?(?:rating|rated)\b", re.I)
_PROBLEMS_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{1,5})\s*\+?\s*(?:[a-z/&-]+\s+){0,2}(?:problems|questions|challenges)\b", re.I)
_STARS_RE = re.compile(r"\b([1-7])\s*(?:-|\s)?\s*(?:stars?|★)", re.I)
_DOMAIN_RE = re.compile(r"\bin\s+([a-z][a-z +#]{1,30})", re.I)

# A claim counts as overstated only past these margins
RATING_MARGIN = 100
PROBLEMS_RATIO = 0.8
NAME_MATCH_THRESHOLD = 60


def _platforms_in(text: str) -> List[str]:
    return [p for p, rx in _PLATFORM_RE.items() if rx.search(text)]


_LINK_RE = re.compile(r"\S*(?:https?://|www\.|\.(?:com|org|net|io|dev|in|co)\b)\S*", re.I)
_SENTENCE_RE = re.compile(r"\n|(?<=[.!?])\s+")


def detect_claims(text: str) -> List[dict]:
    """Claims like "LeetCode Knight", "5-star on CodeChef", "solved 500+ problems".

    platform is None for a claim that names no single platform (a combined total).
    """
    claims: List[dict] = []
    # Links are not claims: a handle like "tourist" must not read as a title
    text = _LINK_RE.sub(" ", text or "")
    # One sentence at a time, so "LeetCode Knight. Codeforces Expert." keeps both
    # ("B.Tech" and "3.9" have no space after the dot and stay whole)
    for line in _SENTENCE_RE.split(text):
        line_platforms = _platforms_in(line)
        for clause in re.split(r"[,;|•·]|\band\b", line):
            found = _platforms_in(clause)
            if len(found) == 1:
                platform = found[0]
            elif not found and len(line_platforms) == 1:
                platform = line_platforms[0]
            else:
                platform = None
            snippet = clause.strip()[:120]

            def add(kind, value, **extra):
                claims.append({"platform": platform, "kind": kind, "value": value, "text": snippet, **extra})

            m = _PROBLEMS_RE.search(clause)
            if m and ("solv" in clause.lower() or platform):
                add("problems", int(m.group(1).replace(",", "")))
            if platform is None:
                continue
            m = _RATING_RE.search(clause)
            if m:
                value = int(m.group(1) or m.group(2))
                if 300 <= value <= 4000:
                    add("rating", value)
            if platform in ("codechef", "hackerrank"):
                m = _STARS_RE.search(clause)
                if m:
                    domain = _DOMAIN_RE.search(clause[m.end():]) if platform == "hackerrank" else None
                    add("stars", int(m.group(1)), domain=domain.group(1).strip() if domain else None)
            if platform == "codeforces":
                m = _CF_RANK_RE.search(clause)
                if m:
                    add("title", m.group(1).lower())
            if platform == "leetcode":
                m = _LC_BADGE_RE.search(clause)
                if m:
                    add("title", m.group(1).lower())
    # The same claim can be found twice when a line repeats it
    unique = {(c["platform"], c["kind"], c["value"], c.get("domain")): c for c in claims}
    return list(unique.values())


def _rank_index(order: List[str], value: Optional[str]) -> int:
    value = (value or "").lower()
    return order.index(value) + 1 if value in order else 0


def _hackerrank_stars(profile: dict, domain: Optional[str]) -> Tuple[int, str]:
    badges = profile.get("badges") or []
    if domain:
        match = max(badges, key=lambda b: fuzz.token_set_ratio(domain.lower(), b["name"].lower()), default=None)
        if match and fuzz.token_set_ratio(domain.lower(), match["name"].lower()) >= 80:
            return match["stars"], f"{match['stars']} stars in {match['name']}"
        return 0, f"no {domain} badge"
    best = max((b["stars"] for b in badges), default=0)
    return best, f"{best} stars at most"


def _check_claim(claim: dict, profile: dict) -> Optional[str]:
    """Message when the claim overstates the profile by a clear margin, else None."""
    kind, value, platform = claim["kind"], claim["value"], profile["platform"]
    if kind == "rating":
        actual = profile.get("max_rating") or profile.get("rating")
        if actual is not None and value > actual + RATING_MARGIN:
            return f"Resume claims rating {value}; profile shows {actual}"
    elif kind == "problems":
        actual = profile.get("problems_solved")
        if actual is not None and actual < value * PROBLEMS_RATIO:
            return f"Resume claims {value} problems solved; profile shows {actual}"
    elif kind == "stars" and platform == "codechef":
        actual = max(profile.get("stars") or 0, codechef_stars(profile.get("max_rating")) or 0)
        if value > actual:
            return f"Resume claims {value}★; profile shows {actual}★ at best"
    elif kind == "stars" and platform == "hackerrank":
        actual, shown = _hackerrank_stars(profile, claim.get("domain"))
        if value > actual:
            return f"Resume claims {value} stars{' in ' + claim['domain'] if claim.get('domain') else ''}; profile shows {shown}"
    elif kind == "title" and platform == "codeforces":
        best = max(_rank_index(CF_RANKS, profile.get("max_title")), _rank_index(CF_RANKS, profile.get("title")))
        if _rank_index(CF_RANKS, value) > best:
            return f"Resume claims Codeforces {value}; best rank on profile is {profile.get('max_title') or 'unrated'}"
    elif kind == "title" and platform == "leetcode":
        if _rank_index(LEETCODE_BADGES, value) > _rank_index(LEETCODE_BADGES, profile.get("title")):
            return f"Resume claims LeetCode {value.title()}; profile badge is {profile.get('title') or 'none'}"
    return None


def name_conflicts(profile_name: Optional[str], resume_name: Optional[str]) -> bool:
    """True only for a clear mismatch; a missing name is not a conflict."""
    if not profile_name or not resume_name:
        return False
    return fuzz.token_set_ratio(profile_name.lower(), resume_name.lower()) < NAME_MATCH_THRESHOLD


def check_profiles(profiles: List[dict], claims: List[dict], resume_name: Optional[str]) -> Tuple[str, List[dict]]:
    """Add issues to each found profile; return (status, discrepancies as dicts).

    status: verified (found, nothing contradicts the resume), unverified (a name
    conflict or an overstated claim), not_found, or pending (nothing could be read).
    """
    discrepancies: List[dict] = []
    found = {p["platform"]: p for p in profiles if p.get("status") == "found"}
    label = {"leetcode": "LeetCode", "hackerrank": "HackerRank", "hackerearth": "HackerEarth",
             "codeforces": "Codeforces", "codechef": "CodeChef"}

    for p in found.values():
        p["name_conflict"] = name_conflicts(p.get("name"), resume_name)
        if p["name_conflict"]:
            msg = f"Name on {label[p['platform']]} ({p['name']}) differs from the resume"
            p.setdefault("issues", []).append(msg)
            discrepancies.append({"field": "name", "source": p["platform"], "resumeValue": resume_name,
                                  "actualValue": p["name"], "severity": "major", "description": msg})

    for claim in claims or []:
        if claim.get("platform") in found:
            p = found[claim["platform"]]
            msg = _check_claim(claim, p)
            if msg:
                p.setdefault("issues", []).append(msg)
                discrepancies.append({"field": f"coding_{claim['kind']}", "source": p["platform"],
                                      "resumeValue": claim.get("text"), "actualValue": msg, "severity": "major",
                                      "description": msg})
        elif claim.get("platform") is None and claim["kind"] == "problems" and found:
            counts = [p.get("problems_solved") for p in found.values()]
            # Only when every found profile reports a count, so the total is complete
            if all(c is not None for c in counts) and sum(counts) < claim["value"] * PROBLEMS_RATIO:
                msg = f"Resume claims {claim['value']} problems solved; listed profiles show {sum(counts)} in total"
                discrepancies.append({"field": "coding_problems", "source": "coding_profiles",
                                      "resumeValue": claim.get("text"), "actualValue": msg,
                                      "severity": "major", "description": msg})

    # A listed profile that doesn't exist is worth a look (often a typo); one we
    # couldn't reach is not
    for p in profiles:
        if p.get("status") == "not_found":
            msg = f"{label.get(p['platform'], p['platform'])} profile '{p.get('handle')}' listed on the resume doesn't exist (check for a typo)"
            discrepancies.append({"field": "coding_profile", "source": p["platform"], "resumeValue": p.get("handle"),
                                  "actualValue": "not found", "severity": "minor", "description": msg})

    if found:
        # Missing profiles alone don't overturn a found, consistent one
        major = [d for d in discrepancies if d["severity"] != "minor"]
        return ("unverified" if major else "verified"), discrepancies
    if any(p.get("status") == "not_found" for p in profiles):
        return "not_found", discrepancies
    return "pending", discrepancies


def summary_line(profiles: List[dict]) -> str:
    """One line per profile for the fact checker's candidate context."""
    parts = []
    for p in profiles or []:
        if p.get("status") != "found":
            continue
        stats = [f"{k.replace('_', ' ')} {p[k]}" for k in ("rating", "max_rating", "title", "stars", "problems_solved", "contests")
                 if p.get(k) is not None]
        if p.get("name"):
            stats.insert(0, f"name {p['name']}")
        issues = p.get("issues") or []
        stats.append("mismatches: " + " / ".join(issues) if issues else "no mismatch with the resume")
        parts.append(f"{p['platform']} {p['handle']}: " + ", ".join(stats))
    return "; ".join(parts) or "None"
