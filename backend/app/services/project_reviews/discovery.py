"""Find the candidate's deployed projects and where they were mentioned. No network.

Sources, in order: links in the resume text and PDF link targets (with the resume
line or project entry that mentions them), project links from a portfolio website,
Behance or Dribbble (#30), and GitHub repository homepages.

Every URL must pass the portfolio website validator (public host, no IPs or
internal names, no credentials or ports, http(s) only). Code hosts, social and job
sites, shorteners and files are dropped; app-store links are kept as "not
reviewable". Candidate URLs are only ever fetched through Firecrawl (SSRF rule).
"""
import hashlib
import re
from typing import Iterable, List, Optional
from urllib.parse import parse_qs, urlparse

from app.services.portfolios.links import _BARE_DOMAIN, _SITE_WORDS, _URL_TOKEN, _host_in, public_url, website_url

APP_STORES = ("play.google.com", "apps.apple.com", "itunes.apple.com", "apps.microsoft.com",
              "chromewebstore.google.com", "chrome.google.com", "addons.mozilla.org", "microsoftedge.microsoft.com")
# Bare domains (no "https://") count when the host is a common deploy host or the line says it's a live link
DEPLOY_HOSTS = ("vercel.app", "netlify.app", "github.io", "herokuapp.com", "onrender.com", "pages.dev", "web.app",
                "firebaseapp.com", "streamlit.app", "fly.dev", "railway.app", "surge.sh", "glitch.me", "gitlab.io",
                "azurewebsites.net", "appspot.com", "deno.dev", "replit.app", "up.railway.app")
_APP_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,149}")
_LIVE_WORDS = re.compile(r"\b(live|demo|deployed|hosted|link|url|website|site|visit|app)\b", re.I)
_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
_PRESENT = re.compile(r"\b(present|current|ongoing|now)\b", re.I)

SOURCE_LABEL = {"resume": "Resume", "website": "Portfolio website", "behance": "Behance", "dribbble": "Dribbble",
                "github": "GitHub"}


def _clip(text, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def normalize(url: str) -> str:
    """Dedupe key: host without www, path without trailing slash."""
    p = urlparse(url)
    host = p.hostname[4:] if p.hostname.startswith("www.") else p.hostname
    return host + (p.path.rstrip("/") or "") + (f"?{p.query}" if p.query else "")


def project_id(url: str) -> str:
    return hashlib.sha1(normalize(url).encode()).hexdigest()[:12]


def classify(url) -> Optional[dict]:
    """{url, reviewable[, note]} for a deployed-project link, or None to drop it."""
    clean = public_url(url)
    if not clean:
        return None
    host = urlparse(clean).hostname
    if _host_in(host, APP_STORES):
        # Keep the app id (Play Store ?id=...) so the link still names the app
        app_id = parse_qs(urlparse(url.strip()).query).get("id", [""])[0]
        if _APP_ID.fullmatch(app_id):
            clean += "?id=" + app_id
        return {"url": clean, "reviewable": False,
                "note": "App store listing: not visited (only websites are reviewed)"}
    site = website_url(clean)
    return {"url": site, "reviewable": True} if site else None


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _year(*texts) -> Optional[int]:
    """Latest year in the texts; "present" counts as the newest."""
    joined = " ".join(t for t in texts if isinstance(t, str))
    if _PRESENT.search(joined):
        return 9999
    years = [int(y) for y in _YEAR.findall(joined)]
    return max(years) if years else None


def _entry(link: dict, name: str, source: str, mention: str, tech=(), dates=None) -> dict:
    return {**link, "id": project_id(link["url"]), "name": _clip(name, 80) or urlparse(link["url"]).hostname,
            "source": source, "source_label": SOURCE_LABEL[source], "mention": _clip(mention),
            "tech": [t for t in tech if isinstance(t, str)][:12], "year": _year(dates, mention)}


def _projects(parsed: dict) -> List[dict]:
    return [p for p in (parsed or {}).get("projects") or [] if isinstance(p, dict) and (p.get("name") or "").strip()]


_HEADING = re.compile(r"^\s*[A-Z][A-Z &/]{2,40}:?\s*$")


def _named_in(line: str, projects: List[dict]) -> Optional[dict]:
    line = _key(line)
    return next((p for p in projects if len(_key(p["name"])) >= 3 and _key(p["name"]) in line), None)


def _project_for(url: str, lines: List[str], i: Optional[int], projects: List[dict], lookback: bool) -> Optional[dict]:
    """The resume project a link belongs to: named on its line, containing it, named in the URL, or
    (lookback) named a few lines above within the same section."""
    host = urlparse(url).hostname
    if i is not None and _named_in(lines[i], projects):
        return _named_in(lines[i], projects)
    hit = next((p for p in projects if host in (p.get("details") or "").lower()), None)
    if hit:
        return hit
    url_key = _key(host + urlparse(url).path)
    hit = next((p for p in projects if len(_key(p["name"])) >= 4 and _key(p["name"]) in url_key), None)
    if hit or i is None or not lookback:
        return hit
    for j in range(i - 1, max(-1, i - 5), -1):
        if _HEADING.match(lines[j]):
            return None
        hit = _named_in(lines[j], projects)
        if hit:
            return hit
    return None


def _line_tokens(line: str):
    yield from _URL_TOKEN.findall(line)
    rest = _URL_TOKEN.sub(" ", line)
    for token in _BARE_DOMAIN.findall(rest):
        host = (urlparse("https://" + token).hostname or "")
        if _host_in(host, DEPLOY_HOSTS) or _LIVE_WORDS.search(rest):
            yield token


def from_resume(text: str, uris: Iterable[str], parsed: dict, portfolio_site: Optional[str] = None) -> List[dict]:
    """Project links in the resume text and PDF link targets, with the line or project that mentions them.

    An unattributed link that is the candidate's own portfolio site (or sits on a
    "portfolio/website" line) is their personal site, not a project, and is left out.
    """
    projects = _projects(parsed)
    experience = [e for e in (parsed or {}).get("experience") or [] if isinstance(e, str)]
    lines = (text or "").splitlines()
    site_key = normalize(portfolio_site) if portfolio_site else None
    found = []

    def add(raw, i):
        link = classify(raw)
        if not link:
            return
        line = lines[i] if i is not None else ""
        host = urlparse(link["url"]).hostname
        job = next((e for e in experience if host in e.lower()), None)
        project = _project_for(link["url"], lines, i, projects, lookback=not job)
        if not project and (normalize(link["url"]) == site_key or _SITE_WORDS.search(line)):
            return
        if project:
            found.append(_entry(link, project["name"], "resume", project.get("details") or project["name"],
                                project.get("technologies") or [], project.get("duration")))
            return
        mention = job or line or "Link in the resume PDF"
        found.append(_entry(link, host, "resume", mention))

    for i, line in enumerate(lines):
        for token in _line_tokens(line):
            add(token, i)
    for uri in uris or []:
        if isinstance(uri, str):
            add(uri, None)
    return dedupe(found)


def from_portfolios(entries) -> List[dict]:
    """Project links read from a portfolio website, Behance or Dribbble (#30 verification data)."""
    found = []
    for p in entries or []:
        if not isinstance(p, dict) or p.get("status") != "found" or p.get("platform") not in ("website", "behance", "dribbble"):
            continue
        site_key = normalize(p["handle"]) if p.get("platform") == "website" and public_url(p.get("handle")) else None
        for pr in p.get("projects") or []:
            link = classify(pr.get("url")) if isinstance(pr, dict) else None
            if not link or normalize(link["url"]) == site_key:
                continue
            mention = f"'{pr.get('title')}'" + (f": {pr['description']}" if pr.get("description") else "")
            found.append(_entry(link, pr.get("title") or "", p["platform"], mention, pr.get("tools") or [], pr.get("dates")))
    return found


def from_github(github_data) -> List[dict]:
    """Homepages set on the candidate's own GitHub repositories."""
    v2 = (github_data or {}).get("github_v2_data") or {}
    matched = {m.get("repoName"): m.get("projectName")
               for m in ((v2.get("resumeVerification") or {}).get("matches") or []) if isinstance(m, dict)}
    found = []
    for repo in v2.get("homepages") or []:
        link = classify(repo.get("url")) if isinstance(repo, dict) else None
        if not link:
            continue
        name = repo.get("repo") or ""
        mention = f"Homepage of GitHub repo {name}" + (f": {repo['description']}" if repo.get("description") else "")
        if matched.get(name):
            mention += f" (matches resume project '{matched[name]}')"
        found.append(_entry(link, matched.get(name) or name, "github", mention,
                            [t for t in [repo.get("language"), *(repo.get("topics") or [])] if t], repo.get("pushed_at")))
    return found


def dedupe(projects: Iterable[dict]) -> List[dict]:
    seen, out = set(), []
    for p in projects:
        key = normalize(p["url"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def all_projects(candidate: Optional[dict], verification: Optional[dict]) -> List[dict]:
    """Resume links (stored at parse time), then portfolio projects and GitHub homepages (from verification)."""
    verification = verification or {}
    return dedupe([*((candidate or {}).get("project_links") or []),
                   *from_portfolios(verification.get("portfoliosData")),
                   *from_github(verification.get("githubData"))])


# ── Selection ──────────────────────────────────────────────────────

def _skill_key(skill: str) -> str:
    s = re.sub(r"[^a-z0-9+#]", "", skill.lower())
    return s[:-2] if s.endswith("js") and len(s) > 4 else s


def _overlap(project: dict, skills: List[str]) -> int:
    words = re.findall(r"[a-z0-9+#.]+", " ".join([project.get("name") or "", project.get("mention") or "",
                                                    *(project.get("tech") or [])]).lower())
    keys = {_skill_key(w) for w in words} | {_skill_key(w.replace(".", "")) for w in words}
    text = _key(" ".join(words))
    hits = 0
    for skill in skills:
        k = _skill_key(skill)
        if k and (k in keys or (len(k) >= 5 and k in text)):
            hits += 1
    return hits


def select(projects: List[dict], job: Optional[dict], limit: int) -> List[dict]:
    """Reviewable projects ranked by job-skill overlap (required counts double), then recency."""
    job = job or {}
    required = [s for s in job.get("required_skills") or [] if isinstance(s, str)]
    preferred = [s for s in job.get("preferred_skills") or [] if isinstance(s, str)]
    reviewable = [(i, p) for i, p in enumerate(projects) if p.get("reviewable")]
    ranked = sorted(reviewable, key=lambda ip: (-(2 * _overlap(ip[1], required) + _overlap(ip[1], preferred)),
                                                 -(ip[1].get("year") or 0), ip[0]))
    return [p for _, p in ranked[:max(limit, 0)]]
