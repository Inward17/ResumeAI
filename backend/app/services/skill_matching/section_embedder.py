"""
Section Embedder
================
Extracts plain-text corpora from each resume section and the GitHub
verification result, then embeds them concurrently.

Each section becomes a single dense vector suitable for cosine-similarity
comparison against a skill embedding.

Usage:
    texts = extract_section_texts(parsed_resume, github_v2_data)
    embeddings = await embed_sections(texts)   # Dict[str, List[float]]
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def _skills_text(parsed: Dict[str, Any]) -> str:
    raw = parsed.get("skills", "") or ""
    if isinstance(raw, list):
        return ", ".join(str(s) for s in raw if s)
    return str(raw)


def _experience_text(parsed: Dict[str, Any]) -> str:
    entries = parsed.get("experience", []) or []
    if not isinstance(entries, list):
        return str(entries)
    parts: List[str] = []
    for e in entries:
        if isinstance(e, str):
            parts.append(e)
        elif isinstance(e, dict):
            parts.append(
                " ".join(filter(None, [
                    e.get("title", ""),
                    e.get("company", ""),
                    e.get("description", ""),
                ]))
            )
    return " ".join(parts)


def _projects_text(parsed: Dict[str, Any]) -> str:
    entries = parsed.get("projects", []) or []
    if not isinstance(entries, list):
        return str(entries)
    parts: List[str] = []
    for p in entries:
        if isinstance(p, str):
            parts.append(p)
        elif isinstance(p, dict):
            techs = " ".join(p.get("technologies", []) or [])
            parts.append(
                " ".join(filter(None, [
                    p.get("name", ""),
                    p.get("description", ""),
                    techs,
                ]))
            )
    return " ".join(parts)


def _github_text(github_v2_data: Optional[Dict[str, Any]]) -> str:
    """
    Build GitHub evidence text from the stored verification result.

    Sources (in priority order):
      1. resumeVerification.matches  → repo names matched to resume projects
      2. cloneAnalysis.repoDetails   → repo names from deep analysis
      3. repositoryStats             → aggregate originality signal

    Note: raw repo topics / languages are NOT in github_v2_data because
    GitHubVerificationResult.to_mongo_dict() intentionally excludes raw data
    to keep the DB document small.  We use the available structured fields.
    """
    if not github_v2_data or not isinstance(github_v2_data, dict):
        return ""

    parts: List[str] = []

    # 1. Matched repos (highest-value: confirmed to exist in candidate's account)
    rv = github_v2_data.get("resumeVerification") or {}
    for m in rv.get("matches") or []:
        if isinstance(m, dict):
            for key in ("repoName", "projectName"):
                val = m.get(key, "")
                if val:
                    parts.append(val.replace("-", " ").replace("_", " "))

    # 2. Repos from clone / README analysis
    ca = github_v2_data.get("cloneAnalysis") or {}
    for detail in ca.get("repoDetails") or []:
        if isinstance(detail, dict) and not detail.get("skipped"):
            repo = detail.get("repo", "")
            if repo:
                parts.append(repo.replace("-", " ").replace("_", " "))

    # 3. Stats signal — adds "N original repositories" phrase for semantic weight
    rs = github_v2_data.get("repositoryStats") or {}
    total = rs.get("total", 0)
    original = rs.get("original", 0)
    if total > 0:
        parts.append(f"{original} original software repositories")

    return " ".join(p for p in parts if p)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def extract_section_texts(
    parsed: Dict[str, Any],
    github_v2_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Return a mapping of section name → plain text corpus.

    Sections:
        skills      — from parsed["skills"]
        experience  — from parsed["experience"]
        projects    — from parsed["projects"]
        github      — from github_v2_data (may be empty string)
    """
    return {
        "skills":     _skills_text(parsed),
        "experience": _experience_text(parsed),
        "projects":   _projects_text(parsed),
        "github":     _github_text(github_v2_data),
    }


async def embed_sections(
    section_texts: Dict[str, str],
) -> Dict[str, List[float]]:
    """
    Embed all non-empty sections concurrently.

    Returns a dict of section name → embedding vector.
    Sections with empty text are silently omitted from the result.
    Embedding failures for individual sections are logged but do not
    raise — the caller continues with whatever sections succeeded.
    """
    from app.services.embedding_service import generate_embedding

    non_empty = {k: v for k, v in section_texts.items() if v and v.strip()}
    if not non_empty:
        return {}

    async def _embed_one(key: str, text: str):
        try:
            emb = await asyncio.to_thread(generate_embedding, text)
            return key, emb
        except Exception as exc:
            logger.warning("section_embedder: failed to embed '%s': %s", key, exc)
            return key, None

    results = await asyncio.gather(*[_embed_one(k, v) for k, v in non_empty.items()])
    return {k: emb for k, emb in results if emb is not None}
