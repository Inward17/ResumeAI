"""Visit a deployed project through Firecrawl: landing page (markdown, links, screenshot) plus a few
internal pages (markdown only).

Our server never requests a candidate URL itself (SSRF). The only direct download
is the screenshot, and only from Firecrawl's own storage host.

Firecrawl cost per project: 1 credit per page, so 1 + up to (PROJECT_REVIEW_MAX_PAGES - 1);
3 by default. The landing page may use Firecrawl's enhanced proxy (more credits) when
the site blocks the basic one.
"""
import asyncio
import base64
import io
import logging
import os
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.services.portfolios.fetchers import NotConfigured, _firecrawl_settings
from app.services.portfolios.links import _FILE_EXT, public_url

logger = logging.getLogger(__name__)

LANDING_CHARS = 8000
PAGE_CHARS = 4000

# Hosted screenshots come from Firecrawl's bucket; anything else is refused
SCREENSHOT_HOSTS = {"storage.googleapis.com": "/firecrawl-scrape-media/", "service.firecrawl.dev": "/storage/"}
SCREENSHOT_MAX_BYTES = 8 * 1024 * 1024
THUMB_WIDTH = 960
THUMB_MAX_BYTES = 150 * 1024


def max_pages() -> int:
    return max(1, int(os.getenv("PROJECT_REVIEW_MAX_PAGES", "3")))


def configured() -> bool:
    try:
        _firecrawl_settings()
        return True
    except NotConfigured:
        return False


# ── Page states ────────────────────────────────────────────────────

_PLACEHOLDER = re.compile(
    r"coming soon|under construction|domain (is )?for sale|buy this domain|this domain (may be|is) for sale|"
    r"parked (free|domain)|domain parking|welcome to nginx|apache2 (ubuntu|debian) default page|it works!|"
    r"edit <code>src/app|edit src/app\.(js|jsx|tsx)|get started by editing|"
    r"deployment_not_found|deployment not found|there isn't a github pages site here|no such app|"
    r"site not found|this site can.t be reached|application error|page not found.{0,40}broken link|"
    r"hello,? world!?\s*$|index of /", re.I)


def page_state(status_code, markdown: str, title: str = "") -> tuple:
    """(state, note): live, down, blocked, empty or placeholder."""
    text = (markdown or "").strip()
    if isinstance(status_code, int):
        if status_code in (401, 403, 407, 429, 451):
            return "blocked", f"The site refused the visit (HTTP {status_code}); it may need a login or block bots"
        if status_code >= 400:
            return "down", f"The site answered HTTP {status_code}"
    # Only a short page counts as a placeholder: a real site may say "coming soon" somewhere
    if len(text) < 600 and _PLACEHOLDER.search(f"{title}\n{text}"):
        return "placeholder", "The page is a placeholder (parked domain, default template or 'coming soon')"
    if len(re.sub(r"\W", "", text)) < 40:
        return "empty", "The page has almost no content (it may render only in a browser app or be blank)"
    return "live", None


# ── Firecrawl ──────────────────────────────────────────────────────

async def scrape(client: httpx.AsyncClient, url: str, landing: bool) -> dict:
    """One Firecrawl scrape. Raises NotConfigured, or RuntimeError with a short reason."""
    key, api_url, timeout = _firecrawl_settings()
    formats = ["markdown", "links", {"type": "screenshot", "fullPage": False}] if landing else ["markdown"]
    body = {"url": url, "formats": formats, "onlyMainContent": False, "blockAds": True,
            "timeout": max(int(timeout * 1000) - 5000, 10000), "proxy": "auto" if landing else "basic"}
    try:
        resp = await client.post(f"{api_url}/v2/scrape", json=body, headers={"Authorization": f"Bearer {key}"},
                                 timeout=httpx.Timeout(timeout, connect=10.0))
    except httpx.TimeoutException:
        raise RuntimeError("timeout")
    if resp.status_code == 402:
        raise RuntimeError("Firecrawl credits are used up")
    if resp.status_code == 429:
        raise RuntimeError("Firecrawl rate limit reached")
    if resp.status_code >= 400:
        # Firecrawl answers an error when the site itself can't be loaded (DNS, TLS, refused)
        raise RuntimeError("site_unreachable")
    data = (resp.json() or {}).get("data") or {}
    meta = data.get("metadata") or {}
    return {"markdown": data.get("markdown") or "", "links": data.get("links") or [],
            "screenshot": data.get("screenshot"), "status_code": meta.get("statusCode"),
            "title": str(meta.get("title") or "")[:200], "url": public_url(meta.get("url") or meta.get("sourceURL")) or url}


_SKIP_PATH = re.compile(r"login|log-in|signin|sign-in|signup|sign-up|register|auth|account|logout|password|"
                        r"privacy|terms|legal|cookie|gdpr|imprint|impressum|disclaimer|cart|checkout|wp-admin|"
                        r"feed|rss|sitemap|cdn-cgi|tag/|category/", re.I)
_GOOD_PATH = re.compile(r"feature|product|about|pricing|plans|docs|documentation|guide|demo|how-it-works|tour|"
                        r"overview|solution|services|projects|work|showcase|app|dashboard|explore|blog", re.I)


def _same_site(a: str, b: str) -> bool:
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(urlparse(a).hostname or "") == strip(urlparse(b).hostname or "")


def pick_links(landing_url: str, links: List[str], limit: int) -> List[str]:
    """Up to `limit` same-site pages most likely to show the product (features, about, docs, demo…)."""
    seen = {urlparse(landing_url).path.rstrip("/") or "/"}
    scored = []
    for raw in links or []:
        if not isinstance(raw, str):
            continue
        url = public_url(urljoin(landing_url, raw.strip()))
        if not url or not _same_site(url, landing_url):
            continue
        path = urlparse(url).path.rstrip("/") or "/"
        if path in seen or _SKIP_PATH.search(path) or _FILE_EXT.search(path):
            continue
        seen.add(path)
        scored.append((0 if _GOOD_PATH.search(path) else 1, path.count("/"), len(path), url))
    return [s[-1] for s in sorted(scored)[:max(limit, 0)]]


# ── Screenshot ─────────────────────────────────────────────────────

def screenshot_url_ok(url) -> bool:
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    prefix = SCREENSHOT_HOSTS.get((p.hostname or "").lower())
    return p.scheme == "https" and p.port is None and not p.username and prefix is not None and p.path.startswith(prefix)


def compress(raw: bytes) -> Optional[str]:
    """Base64 JPEG at most THUMB_WIDTH wide and THUMB_MAX_BYTES big, or None if it isn't a usable image."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            if img.width > THUMB_WIDTH:
                img = img.resize((THUMB_WIDTH, max(1, round(img.height * THUMB_WIDTH / img.width))))
            img = img.crop((0, 0, img.width, min(img.height, round(img.width * 1.25))))
            for quality in (70, 55, 40):
                out = io.BytesIO()
                img.save(out, "JPEG", quality=quality, optimize=True)
                if out.tell() <= THUMB_MAX_BYTES:
                    return base64.b64encode(out.getvalue()).decode()
    except Exception as e:
        logger.info("Screenshot not usable: %s", type(e).__name__)
    return None


async def fetch_screenshot(client: httpx.AsyncClient, url) -> tuple:
    """(base64 jpeg or None, note). Downloads only from Firecrawl's screenshot host, without redirects."""
    if not url:
        return None, "No screenshot was returned"
    if not screenshot_url_ok(url):
        return None, "Screenshot skipped: not on Firecrawl's storage host"
    try:
        async with client.stream("GET", url, timeout=httpx.Timeout(20.0, connect=5.0), follow_redirects=False) as r:
            if r.status_code != 200:
                return None, "Screenshot could not be downloaded"
            raw = b""
            async for chunk in r.aiter_bytes():
                raw += chunk
                if len(raw) > SCREENSHOT_MAX_BYTES:
                    return None, "Screenshot too large"
    except httpx.HTTPError:
        return None, "Screenshot could not be downloaded"
    data = await asyncio.to_thread(compress, raw)
    return (data, None) if data else (None, "Screenshot was not a readable image")


# ── One project ────────────────────────────────────────────────────

async def visit(url: str, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Visit one project. Never raises.

    Returns {site_status, site_note, pages: [{url, title, status_code, text}], screenshot, screenshot_note}.
    """
    out = {"site_status": "error", "site_note": None, "pages": [], "screenshot": None, "screenshot_note": None}
    own = client is None
    client = client or httpx.AsyncClient(follow_redirects=False)
    try:
        try:
            landing = await scrape(client, url, landing=True)
        except NotConfigured as e:
            out.update(site_status="not_configured", site_note=str(e))
            return out
        except RuntimeError as e:
            reason = str(e)
            if reason in ("site_unreachable", "timeout"):
                out.update(site_status="down", site_note="The site could not be loaded (no answer, DNS or TLS error)"
                           if reason == "site_unreachable" else "The site did not load in time")
            else:
                out["site_note"] = reason
            return out
        except Exception as e:
            logger.warning("Project visit failed: %s", type(e).__name__)
            out["site_note"] = "Could not visit the site"
            return out

        state, note = page_state(landing["status_code"], landing["markdown"], landing["title"])
        out.update(site_status=state, site_note=note)
        out["pages"].append({"url": landing["url"], "title": landing["title"], "status_code": landing["status_code"],
                             "text": landing["markdown"][:LANDING_CHARS]})
        out["screenshot"], out["screenshot_note"] = await fetch_screenshot(client, landing["screenshot"])
        if state != "live":
            return out

        for link in pick_links(landing["url"], landing["links"], max_pages() - 1):
            try:
                page = await scrape(client, link, landing=False)
            except Exception:
                out["pages"].append({"url": link, "title": "", "status_code": None, "text": "", "failed": True})
                continue
            out["pages"].append({"url": page["url"], "title": page["title"], "status_code": page["status_code"],
                                 "text": page["markdown"][:PAGE_CHARS]})
        return out
    finally:
        if own:
            await client.aclose()
