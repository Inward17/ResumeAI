"""
Enterprise GitHub Verification — Async GitHub API Client
All GitHub API interactions go through this module.
Uses httpx.AsyncClient, async semaphore, retry with backoff,
and a file-based search result cache.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from .config import (
    GITHUB_API_BASE_URL,
    GITHUB_TOKEN,
    MAX_CONCURRENT_GITHUB_CALLS,
    REQUEST_TIMEOUT_SECONDS,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    MAX_EXTERNAL_REPOS,
    SEARCH_CACHE_DIR,
    SEARCH_CACHE_TTL_HOURS,
)

logger = logging.getLogger(__name__)

# Module-level semaphore — shared across all client instances in the process
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-create a process-wide semaphore (must be called inside a running loop)."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_GITHUB_CALLS)
    return _semaphore


class GitHubClient:
    """
    Async GitHub API v3 client.

    * Uses ``httpx.AsyncClient`` — never blocks the event loop.
    * Concurrency capped by a shared ``asyncio.Semaphore``.
    * Retries with exponential backoff on transient errors.
    * File-based cache for GitHub Search API results.
    """

    def __init__(self, token: Optional[str] = None) -> None:
        # Re-read from env at instantiation — more robust than config import-time value
        self._token = token or os.getenv("GITHUB_TOKEN", "") or GITHUB_TOKEN
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ResumeAI-Verifier/2.0",
        }
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE_URL,
            headers=headers,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            follow_redirects=True,
        )
        # Track 403 — when hit, skip deep analysis
        self.rate_limited = False
        # Ensure search cache dir exists
        os.makedirs(SEARCH_CACHE_DIR, exist_ok=True)

    # ──────────────────────────────────────────────────────────────
    # Internal: guarded request with retry + semaphore
    # ──────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[httpx.Response]:
        """
        Execute a rate-limited, retried HTTP request.

        Returns ``None`` on permanent failure.
        Sets ``self.rate_limited = True`` on 403.
        """
        sem = _get_semaphore()
        last_exc: Optional[Exception] = None

        for attempt in range(RETRY_ATTEMPTS):
            try:
                async with sem:
                    resp = await self._client.request(method, path, params=params)

                if resp.status_code == 200:
                    return resp

                if resp.status_code == 403:
                    logger.warning("GitHub 403 — rate limited. Deep analysis will be skipped.")
                    self.rate_limited = True
                    return None

                if resp.status_code == 404:
                    return None

                # Transient (5xx, 429): retry
                if resp.status_code >= 500 or resp.status_code == 429:
                    wait = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                    logger.info("GitHub %s on %s — retrying in %.1fs", resp.status_code, path, wait)
                    await asyncio.sleep(wait)
                    continue

                # Other client errors: don't retry
                return None

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                wait = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                logger.info("GitHub request error on %s — %s — retrying in %.1fs", path, exc, wait)
                await asyncio.sleep(wait)

        logger.error("GitHub request permanently failed for %s after %d attempts: %s",
                      path, RETRY_ATTEMPTS, last_exc)
        return None

    # ──────────────────────────────────────────────────────────────
    # Public API methods
    # ──────────────────────────────────────────────────────────────

    async def get_user_repos(self, username: str) -> List[Dict[str, Any]]:
        """Fetch all public repositories for *username* (paginated)."""
        all_repos: List[Dict[str, Any]] = []
        page = 1

        while True:
            resp = await self._request(
                "GET",
                f"/users/{username}/repos",
                params={"per_page": 100, "page": page, "type": "all"},
            )
            if resp is None:
                break
            batch = resp.json()
            if not batch:
                break
            all_repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1

        return all_repos

    async def get_repo_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch and decode the README for *owner/repo*."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}/readme")
        if resp is None:
            return None
        data = resp.json()
        content = data.get("content", "")
        encoding = data.get("encoding", "")
        if encoding == "base64" and content:
            try:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            except Exception:
                return None
        return content or None

    async def get_repo_commits(
        self,
        owner: str,
        repo: str,
        username: str,
        max_commits: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch commits by *username* in *owner/repo* (single page)."""
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits",
            params={"author": username, "per_page": max_commits},
        )
        if resp is None:
            return []
        return resp.json()

    async def get_repo_tree(
        self,
        owner: str,
        repo: str,
        branch: str = "HEAD",
    ) -> List[Dict[str, Any]]:
        """
        Fetch the recursive file tree for *owner/repo*.
        Uses ``GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1``.
        """
        resp = await self._request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        if resp is None:
            return []
        data = resp.json()
        return data.get("tree", [])

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
    ) -> Optional[str]:
        """Fetch and decode a single file from *owner/repo*."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}/contents/{path}")
        if resp is None:
            return None
        data = resp.json()
        if data.get("type") != "file":
            return None
        content = data.get("content", "")
        encoding = data.get("encoding", "")
        if encoding == "base64" and content:
            try:
                return base64.b64decode(content).decode("utf-8", errors="replace")
            except Exception:
                return None
        return content or None

    async def get_repo_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch full repo metadata (for default branch detection etc.)."""
        resp = await self._request("GET", f"/repos/{owner}/{repo}")
        if resp is None:
            return None
        return resp.json()

    # ──────────────────────────────────────────────────────────────
    # Search API with file-based caching
    # ──────────────────────────────────────────────────────────────

    async def search_similar_repos(
        self,
        query: str,
        limit: int = MAX_EXTERNAL_REPOS,
    ) -> List[Dict[str, Any]]:
        """
        Search GitHub for similar repos.  Results are cached to disk
        at ``SEARCH_CACHE_DIR`` with a TTL of ``SEARCH_CACHE_TTL_HOURS``.

        Returns a lightweight list of dicts with name, owner, full_name,
        description, stars, html_url, topics.
        """
        # ── try cache first ──
        cached = self._load_search_cache(query)
        if cached is not None:
            return cached[:limit]

        # ── API call ──
        resp = await self._request(
            "GET",
            "/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
        )
        if resp is None:
            return []

        items = resp.json().get("items", [])
        results: List[Dict[str, Any]] = []
        for item in items:
            results.append({
                "name": item["name"],
                "owner": item["owner"]["login"],
                "full_name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "html_url": item.get("html_url", ""),
                "topics": item.get("topics", []),
            })

        # ── persist to cache ──
        self._save_search_cache(query, results)
        return results

    # ──────────────────────────────────────────────────────────────
    # Search cache helpers
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _search_cache_key(query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    def _search_cache_path(self, query: str) -> str:
        return os.path.join(SEARCH_CACHE_DIR, f"{self._search_cache_key(query)}.json")

    def _load_search_cache(self, query: str) -> Optional[List[Dict[str, Any]]]:
        path = self._search_cache_path(query)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time > timedelta(hours=SEARCH_CACHE_TTL_HOURS):
                os.remove(path)
                return None
            return data["results"]
        except Exception:
            return None

    def _save_search_cache(self, query: str, results: List[Dict[str, Any]]) -> None:
        path = self._search_cache_path(query)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(
                    {"timestamp": datetime.now().isoformat(), "query": query, "results": results},
                    fh,
                    indent=2,
                )
        except Exception:
            pass  # cache write failure is non-fatal

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
