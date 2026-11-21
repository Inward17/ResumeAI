"""Find competitive-programming profile handles in resume text and PDF links.

Only the handle is kept. Request URLs are rebuilt from a validated handle,
so nothing taken from the resume is ever fetched as-is.
"""
import re
from typing import Dict, Iterable, Optional
from urllib.parse import quote, urlparse

PLATFORMS = ("leetcode", "hackerrank", "hackerearth", "codeforces", "codechef")

_HOSTS = {
    "leetcode.com": "leetcode",
    "hackerrank.com": "hackerrank",
    "hackerearth.com": "hackerearth",
    "codeforces.com": "codeforces",
    "codechef.com": "codechef",
}

# Strict per-platform handle rules (start with a letter, digit or underscore,
# so "." and ".." can never be a handle)
HANDLE_RE = {
    "leetcode": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,39}"),
    "hackerrank": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,39}"),
    "hackerearth": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,49}"),
    "codeforces": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{2,23}"),
    "codechef": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,29}"),
}

# First path segments that are site pages, not users (for the bare /<handle> forms)
_RESERVED = {
    "leetcode": {"problems", "problemset", "discuss", "contest", "explore", "studyplan", "assessment",
                 "interview", "store", "subscribe", "accounts", "company", "list", "tag", "tags",
                 "submissions", "profile", "support", "jobs", "notes", "playground", "articles",
                 "premium", "progress", "u", "api", "graphql", "favicon.ico", "privacy", "terms"},
    "hackerrank": {"challenges", "domains", "contests", "dashboard", "interview", "skills-verification",
                   "certificates", "certificate", "jobs", "auth", "login", "signup", "products", "work",
                   "blog", "leaderboard", "settings", "rest", "tracks", "about-us", "privacy",
                   "terms-of-service", "community", "apply", "resources"},
}

_URL_TOKEN = re.compile(
    r"(?<![A-Za-z0-9.@-])(?:https?://)?(?:www\.)?(?:leetcode|hackerrank|hackerearth|codeforces|codechef)\.com[^\s<>\"')\]]*",
    re.IGNORECASE,
)

PROFILE_URLS = {
    "leetcode": "https://leetcode.com/u/{}/",
    "hackerrank": "https://www.hackerrank.com/profile/{}",
    "hackerearth": "https://www.hackerearth.com/@{}/",
    "codeforces": "https://codeforces.com/profile/{}",
    "codechef": "https://www.codechef.com/users/{}",
}


def valid_handle(platform: str, handle: Optional[str]) -> bool:
    rule = HANDLE_RE.get(platform)
    return bool(rule and isinstance(handle, str) and rule.fullmatch(handle))


def profile_url(platform: str, handle: str) -> str:
    """Public profile page for a validated handle."""
    if not valid_handle(platform, handle):
        raise ValueError("invalid handle")
    return PROFILE_URLS[platform].format(quote(handle, safe=""))


def parse_profile_url(url: str) -> Optional[tuple]:
    """(platform, handle) for a profile URL on one of the five sites, else None."""
    url = (url or "").strip().rstrip(".,;:!")
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme.lower() not in ("http", "https") or parsed.username or parsed.password or parsed.port:
            return None
    except ValueError:
        return None
    platform = _HOSTS.get(host[4:] if host.startswith("www.") else host)
    if not platform:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    handle = None
    if platform == "leetcode":
        if len(parts) >= 2 and parts[0] == "u":
            handle = parts[1]
        elif len(parts) == 1 and parts[0].lower() not in _RESERVED["leetcode"]:
            handle = parts[0]
    elif platform == "hackerrank":
        if len(parts) >= 2 and parts[0] == "profile":
            handle = parts[1]
        elif len(parts) == 1 and parts[0].lower() not in _RESERVED["hackerrank"]:
            handle = parts[0]
    elif platform == "hackerearth":
        if parts and parts[0].startswith("@"):
            handle = parts[0][1:]
    elif platform == "codeforces":
        if len(parts) >= 2 and parts[0] == "profile":
            handle = parts[1]
    elif platform == "codechef":
        if len(parts) >= 2 and parts[0] == "users":
            handle = parts[1]
    return (platform, handle) if valid_handle(platform, handle) else None


def extract_coding_profiles(sources: Iterable[str]) -> Dict[str, str]:
    """{platform: handle} from resume text and link targets; the first valid one per platform wins."""
    found: Dict[str, str] = {}
    for source in sources:
        if not isinstance(source, str):
            continue
        for token in _URL_TOKEN.findall(source):
            hit = parse_profile_url(token)
            if hit and hit[0] not in found:
                found[hit[0]] = hit[1]
    return found
