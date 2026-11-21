"""Find portfolio and community profiles in resume text and PDF links.

Behance, Dribbble, Kaggle and Stack Overflow keep only a validated handle (or
numeric user id); request URLs are rebuilt from it. A personal website keeps a
normalised URL that passed public_url(): it is only ever fetched through
Firecrawl, never by our server (SSRF, see SECURITY.md).
"""
import ipaddress
import re
from typing import Dict, Iterable, Optional
from urllib.parse import quote, urlparse

from app.services.coding_profiles.handles import _HOSTS as CODING_HOSTS

PLATFORMS = ("behance", "dribbble", "kaggle", "stackoverflow", "website")

_HOSTS = {
    "behance.net": "behance",
    "dribbble.com": "dribbble",
    "kaggle.com": "kaggle",
    "stackoverflow.com": "stackoverflow",
}

HANDLE_RE = {
    "behance": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,39}"),
    "dribbble": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,39}"),
    "kaggle": re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,39}"),
    "stackoverflow": re.compile(r"[1-9][0-9]{0,9}"),
}

# First path segments that are site pages, not people
_RESERVED = {
    "behance": {"gallery", "galleries", "search", "joblist", "hire", "assets", "onboarding", "about", "blog",
                "live", "for_you", "signup", "login", "pro", "moodboards", "collection", "jobs", "dev",
                "privacy", "misc", "v2", "adobe", "featured", "creative-fields", "portfolio", "freelance"},
    "dribbble": {"shots", "designers", "jobs", "signup", "session", "search", "tags", "stories", "learn", "pro",
                 "hiring", "about", "following", "popular", "colors", "place", "freelance-jobs", "resources",
                 "terms", "privacy", "advertise", "marketplace", "teams", "uploads", "for-designers", "account",
                 "projects", "services", "contact", "guidelines"},
    "kaggle": {"competitions", "c", "datasets", "d", "code", "models", "m", "discussions", "discussion", "learn",
               "docs", "search", "account", "settings", "organizations", "benchmarks", "host", "contact", "terms",
               "privacy", "static", "api", "rankings", "progression", "general", "work", "me", "kernels",
               "about", "careers", "community", "notebooks", "signin", "signup", "getting-started", "t"},
}

PROFILE_URLS = {
    "behance": "https://www.behance.net/{}",
    "dribbble": "https://dribbble.com/{}",
    "kaggle": "https://www.kaggle.com/{}",
    "stackoverflow": "https://stackoverflow.com/users/{}",
}

# Hosts that are not a personal website: social, jobs, code, file sharing, other
# handled profiles, mail, link shorteners and link-in-bio pages. Subdomains count.
_NOT_PERSONAL = {
    *CODING_HOSTS, *_HOSTS, "stackexchange.com", "github.com", "gitlab.com", "bitbucket.org", "linkedin.com",
    "twitter.com", "x.com", "facebook.com", "fb.com", "instagram.com", "threads.net", "youtube.com", "youtu.be",
    "tiktok.com", "medium.com", "reddit.com", "quora.com", "discord.com", "discord.gg", "t.me", "wa.me",
    "whatsapp.com", "google.com", "goo.gl", "g.co", "dropbox.com", "onedrive.live.com", "1drv.ms", "box.com",
    "notion.so", "notion.site", "naukri.com", "indeed.com", "glassdoor.com", "monster.com", "wellfound.com",
    "angel.co", "internshala.com", "unstop.com", "coursera.org", "udemy.com", "edx.org", "credly.com",
    "credential.net", "accredible.com", "nptel.ac.in", "swayam.gov.in", "codepen.io", "codesandbox.io",
    "replit.com", "npmjs.com", "pypi.org", "huggingface.co", "wikipedia.org", "gmail.com", "outlook.com",
    "yahoo.com", "hotmail.com", "apple.com", "microsoft.com", "play.google.com", "figma.com", "canva.com",
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "lnkd.in",
    "shorturl.at", "rb.gy", "tiny.cc", "bl.ink", "short.io", "linktr.ee", "beacons.ai", "bio.link",
    "linkin.bio", "msha.ke", "about.me", "calendly.com", "forms.gle", "typeform.com", "geeksforgeeks.org",
    "socket.io", "topcoder.com", "atcoder.jp", "spoj.com", "interviewbit.com", "codingninjas.com", "naukri.com",
}
_FILE_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|odt|rtf|txt|csv|zip|rar|7z|gz|tar|png|jpe?g|gif|svg|webp|mp4|mov|"
                       r"avi|mp3|wav|exe|msi|apk|dmg|iso)$", re.I)
_BLOCKED_SUFFIX = (".local", ".localhost", ".internal", ".intranet", ".lan", ".home", ".corp", ".private",
                   ".test", ".example", ".invalid", ".arpa", ".onion")
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAX_URL_LENGTH = 300


def public_url(url: Optional[str], https_only: bool = False) -> Optional[str]:
    """Normalised scheme://host/path for a public web address, else None.

    Rejects other schemes, credentials, ports, IP literals, single-label and
    internal names, and non-ASCII hosts. Query and fragment are dropped.
    """
    if not isinstance(url, str):
        return None
    url = url.strip().rstrip(".,;:!)")
    if not url or len(url) > MAX_URL_LENGTH or any(c.isspace() for c in url):
        return None
    if "://" not in url:
        url = "https://" + url
    try:
        p = urlparse(url)
        port = p.port
    except ValueError:
        return None
    if p.scheme.lower() not in (("https",) if https_only else ("http", "https")):
        return None
    if p.username or p.password or "@" in p.netloc or port is not None:
        return None
    host = (p.hostname or "").rstrip(".").lower()
    if not host or not host.isascii() or len(host) > 253:
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    labels = host.split(".")
    tld = labels[-1]
    if len(labels) < 2 or not all(_LABEL.fullmatch(l) for l in labels) or not (tld.isalpha() or tld.startswith("xn--")):
        return None
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIX):
        return None
    path = quote(p.path or "/", safe="/-._~%")
    return f"{p.scheme.lower()}://{host}{path}"


def _host_in(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def website_url(url: Optional[str]) -> Optional[str]:
    """A URL that looks like a personal site: public, not a known platform, shortener or file."""
    clean = public_url(url)
    if not clean:
        return None
    p = urlparse(clean)
    if _host_in(p.hostname, _NOT_PERSONAL) or _FILE_EXT.search(p.path):
        return None
    return clean


def valid_handle(platform: str, handle: Optional[str]) -> bool:
    rule = HANDLE_RE.get(platform)
    return bool(rule and isinstance(handle, str) and rule.fullmatch(handle))


def profile_url(platform: str, handle: str) -> str:
    """Public page for a validated handle, or the re-validated website URL."""
    if platform == "website":
        url = website_url(handle)
        if not url:
            raise ValueError("invalid website")
        return url
    if not valid_handle(platform, handle):
        raise ValueError("invalid handle")
    return PROFILE_URLS[platform].format(quote(handle, safe=""))


def parse_profile_url(url: str) -> Optional[tuple]:
    """(platform, handle) for a Behance, Dribbble, Kaggle or Stack Overflow profile URL."""
    clean = public_url(url)
    if not clean:
        return None
    p = urlparse(clean)
    host = p.hostname[4:] if p.hostname.startswith("www.") else p.hostname
    platform = _HOSTS.get(host)
    if not platform:
        return None
    parts = [s for s in p.path.split("/") if s]
    handle = None
    if platform == "stackoverflow":
        if len(parts) >= 2 and parts[0] in ("users", "u"):
            handle = parts[1]
    elif parts and parts[0].lower() not in _RESERVED[platform]:
        handle = parts[0]
    return (platform, handle) if valid_handle(platform, handle) else None



_URL_TOKEN = re.compile(r"(?<![\w.@/-])(?:https?://|www\.)[^\s<>\"'\])]+", re.I)
_KNOWN_BARE = re.compile(r"(?<![\w.@/-])(?:behance\.net|dribbble\.com|kaggle\.com|stackoverflow\.com)/[^\s<>\"'\])]+", re.I)
# A bare domain ("adalovelace.dev") only counts where a website may be named (a
# labelled line or the header), and only with a common top-level domain, so
# "Node.js" or "B.Tech" never read as sites
_BARE_TLDS = ("com|org|io|dev|me|co|in|ai|app|design|art|xyz|site|page|studio|online|pro|info|us|uk|ca|"
              "de|eu|au|portfolio|blog|website|space|live|gg|codes|works|ink|one|fyi|sh")
_BARE_DOMAIN = re.compile(rf"(?<![\w.@/-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:{_BARE_TLDS})(?![\w.-])(?:/[^\s<>\"'\])]*)?", re.I)

# The personal website is the URL the resume labels as one, the one in the
# header/contact block, or one whose host carries the candidate's name. A
# project's deployed link ("deployed at", "live demo", a Projects section) is not.
_SITE_LABEL = re.compile(r"\b(portfolio|website|web\s?site|personal\s+(?:site|page)|blog|home\s?page)\b", re.I)
_PROJECT_LINK = re.compile(r"\b(deployed\s+(?:at|on|to)|live\s+(?:demo|at|on|site|link|version|url)|demo\s*:|"
                           r"demo\s+(?:at|link|url)|hosted\s+(?:at|on)|try\s+it)\b", re.I)
_HEADING = re.compile(
    r"(?:[a-z]+\s+){0,2}(summary|profile|objective|about(?: me)?|experience|employment|work history|education|"
    r"skills|projects?|certifications?|achievements|awards|publications|contact|interests|languages|activities|"
    r"volunteering|leadership|internships?|courses|coursework|hobbies|references|links)"
    r"(?:\s*(?:&|and|/)\s*[a-z ]{1,25})?")
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{7,}\d")
HEADER_LINES = 8


def _heading(line: str) -> Optional[str]:
    """The section name when the line is a heading ("PROJECTS", "Work Experience:"), else None."""
    text = re.sub(r"^[\s#*•\-]+|[\s:]+$", "", line).lower()
    return text if len(text) <= 40 and _HEADING.fullmatch(text) else None


def _host_has_name(url: str, name: Optional[str]) -> bool:
    """nikhilrao.dev or nikhil-rao.github.io for Nikhil Rao: two name parts, or one long part as a whole label."""
    tokens = {t for t in re.findall(r"[a-z]+", (name or "").lower()) if len(t) >= 2}
    if not tokens:
        return False
    host = urlparse(url).hostname or ""
    labels = host.split(".")
    compact = host.replace("-", "")
    return sum(t in compact for t in tokens) >= 2 or any(len(t) >= 4 and t in labels for t in tokens)


def _website_lines(text: str):
    """(line, may_name_site, header) for each line, with project lines marked as never naming the site."""
    lines = text.splitlines()
    first_heading = next((i for i, l in enumerate(lines) if _heading(l)), len(lines))
    header = lines[:min(first_heading, HEADER_LINES)]
    has_contact = any(_CONTACT.search(l) for l in header)
    section = None
    for i, line in enumerate(lines):
        heading = _heading(line)
        if heading:
            section = heading
            continue
        in_projects = section is not None and "project" in section
        in_header = has_contact and i < len(header)
        yield line, not in_projects and not _PROJECT_LINK.search(line), in_header


def extract_portfolios(sources: Iterable[str], name: Optional[str] = None) -> Dict[str, str]:
    """{platform: handle} plus "website": url; the first valid one of each wins (one website per candidate).

    sources: the resume text, then PDF link targets. A link target alone has no
    label or position, so it counts as the website only when its host carries
    the candidate's name; a labelled or header URL is found in the text.
    """
    found: Dict[str, str] = {}
    for source in sources:
        if not isinstance(source, str):
            continue
        if not any(c.isspace() for c in source.strip()):
            lines = [(source.strip(), True, False)]  # a bare link target: needs the name in its host
        else:
            lines = _website_lines(source)
        for line, may_name_site, header in lines:
            urls = _URL_TOKEN.findall(line)
            for token in urls + _KNOWN_BARE.findall(line):
                hit = parse_profile_url(token)
                if hit:
                    found.setdefault(hit[0], hit[1])
            if "website" in found or not may_name_site:
                continue
            labelled = header or bool(_SITE_LABEL.search(line))
            candidates = urls + (_BARE_DOMAIN.findall(_URL_TOKEN.sub(" ", line)) if labelled else [])
            for token in candidates:
                site = website_url(token)
                if site and (labelled or _host_has_name(site, name)):
                    found["website"] = site
                    break
    return found
