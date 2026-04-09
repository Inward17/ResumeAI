"""
Enterprise GitHub Verification — Project Matcher
3-stage resume→repo matching hierarchy:
  Stage 1: Exact normalised match
  Stage 2: Fuzzy match (token_set_ratio ≥ 85)
  Stage 3: Embedding similarity (BGE-large)
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import (
    FUZZY_MATCH_THRESHOLD,
    EMBEDDING_MATCH_STRONG,
    EMBEDDING_MATCH_MODERATE,
)
from ..models import MatchedProject, ResumeVerificationResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Text normalisation for Stage 1
# ─────────────────────────────────────────────────────────────────

_STRIP_RE = re.compile(r"[-_\s]+")


def _normalise(text: str) -> str:
    """Lowercase, remove hyphens, underscores, spaces."""
    return _STRIP_RE.sub("", text.lower())


# ─────────────────────────────────────────────────────────────────
# Singleton BGE model loader (guaranteed singleton per process)
# ─────────────────────────────────────────────────────────────────

_bge_model = None
_bge_tokenizer = None
_bge_lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None  # created lazily below


def _get_bge_lock() -> asyncio.Lock:
    global _bge_lock
    if _bge_lock is None:
        _bge_lock = asyncio.Lock()
    return _bge_lock


async def _ensure_bge_model():
    """Lazy-load BGE model exactly once. Thread-safe via asyncio.Lock."""
    global _bge_model, _bge_tokenizer
    if _bge_model is not None:
        return

    lock = _get_bge_lock()
    async with lock:
        if _bge_model is not None:  # double-check after acquiring lock
            return

        def _load():
            global _bge_model, _bge_tokenizer
            try:
                # Fast DLL pre-check: import torch core first to detect Windows DLL failure
                # before attempting slow model download/load
                import torch
                _ = torch.zeros(1)  # Force actual DLL initialization
                from transformers import AutoModel, AutoTokenizer
                from ..config import BGE_MODEL, DEVICE, NUM_THREADS

                torch.set_num_threads(NUM_THREADS)
                _bge_tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL)
                _bge_model = AutoModel.from_pretrained(BGE_MODEL)
                _bge_model.to(DEVICE)
                _bge_model.eval()
                logger.info("BGE model loaded: %s", BGE_MODEL)
            except Exception as e:
                logger.error("BGE unavailable (DLL issue). Deep project matching disabled. Error: %s", e)
                _bge_model = "FAILED"

        await asyncio.to_thread(_load)


async def _embed_texts_bge(texts: List[str]) -> np.ndarray:
    """
    Embed a batch of texts with BGE-large.
    Returns L2-normalised embeddings (N × 1024).
    CPU-only.  Offloaded to thread to avoid blocking.
    """
    await _ensure_bge_model()
    
    # Graceful fallback if model failed to load
    if _bge_model == "FAILED":
        return np.zeros((len(texts), 1024))

    def _encode():
        import torch
        from ..config import MAX_SEQUENCE_LENGTH, EMBEDDING_BATCH_SIZE

        all_embeddings = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            encoded = _bge_tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_SEQUENCE_LENGTH,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = _bge_model(**encoded)
            # CLS pooling
            embs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            # L2 normalise
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embs = embs / norms
            all_embeddings.append(embs)
        return np.vstack(all_embeddings) if all_embeddings else np.empty((0, 1024))

    return await asyncio.to_thread(_encode)


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

async def match_projects_to_repos(
    projects: List[Dict[str, Any]],
    repos: List[Dict[str, Any]],
) -> ResumeVerificationResult:
    """
    Match resume projects to GitHub repos using the locked 3-stage hierarchy.

    Args:
        projects: list of dicts with at least ``name`` (+ optional ``description``).
        repos:    list of repo dicts with ``name``, ``description``, ``topics``.

    Returns:
        ``ResumeVerificationResult`` with consistency score and match details.
    """
    claimed = len(projects)
    if claimed == 0:
        # No projects in resume → skip signal entirely (return None, not 0.0)
        # 0.0 would penalise candidates whose resume has no projects section,
        # triggering a false red flag and a -20pt drag on the final score.
        return ResumeVerificationResult(
            projectsClaimed=0,
            projectsMatched=0,
            projectsNotFound=0,
            resumeConsistency=None,
        )

    matches: List[MatchedProject] = []

    for project in projects:
        best = _match_single_project(project, repos)
        if best is None:
            # Try embedding as last resort (async)
            best = await _match_embedding(project, repos)

        if best is not None:
            matches.append(best)

    matched_count = len(matches)
    not_found = claimed - matched_count
    consistency = max(0.0, min(1.0, matched_count / claimed)) if claimed > 0 else 0.0

    return ResumeVerificationResult(
        projectsClaimed=claimed,
        projectsMatched=matched_count,
        projectsNotFound=not_found,
        resumeConsistency=round(consistency, 4),
        matches=matches,
    )


# ─────────────────────────────────────────────────────────────────
# Stage 1 + Stage 2 (synchronous — fast)
# ─────────────────────────────────────────────────────────────────

def _match_single_project(
    project: Dict[str, Any],
    repos: List[Dict[str, Any]],
) -> Optional[MatchedProject]:
    """Try Stage 1 (exact) then Stage 2 (fuzzy).  Returns best match or None."""
    proj_name = project.get("name", "")
    if not proj_name:
        return None
    norm_proj = _normalise(proj_name)

    best: Optional[MatchedProject] = None
    best_sim: float = 0.0

    for repo in repos:
        repo_name = repo.get("name", "")
        norm_repo = _normalise(repo_name)

        # ── Stage 1: exact normalised ──
        if norm_proj and norm_repo and norm_proj == norm_repo:
            return MatchedProject(
                projectName=proj_name,
                repoName=repo_name,
                repoFullName=repo.get("full_name", repo_name),
                similarity=1.0,
                matchStage="EXACT",
                matchStrength="STRONG",
            )

        # ── Stage 2: fuzzy ──
        try:
            from thefuzz import fuzz
            score = fuzz.token_set_ratio(proj_name.lower(), repo_name.lower())
            if score >= FUZZY_MATCH_THRESHOLD and score / 100.0 > best_sim:
                best_sim = score / 100.0
                best = MatchedProject(
                    projectName=proj_name,
                    repoName=repo_name,
                    repoFullName=repo.get("full_name", repo_name),
                    similarity=round(best_sim, 4),
                    matchStage="FUZZY",
                    matchStrength="STRONG" if best_sim >= 0.90 else "MODERATE",
                )
        except ImportError:
            pass  # thefuzz not installed — fall through to embedding

    return best


# ─────────────────────────────────────────────────────────────────
# Stage 3: embedding similarity (async)
# ─────────────────────────────────────────────────────────────────

async def _match_embedding(
    project: Dict[str, Any],
    repos: List[Dict[str, Any]],
) -> Optional[MatchedProject]:
    """Stage 3: embed project (name+desc) vs repo (name+desc+topics)."""
    proj_text = _project_text(project)
    if not proj_text:
        return None

    repo_texts = [_repo_text(r) for r in repos]
    if not repo_texts:
        return None

    try:
        all_texts = [proj_text] + repo_texts
        embeddings = await _embed_texts_bge(all_texts)

        proj_emb = embeddings[0]
        repo_embs = embeddings[1:]

        sims = repo_embs @ proj_emb  # dot product of L2-normalised = cosine
        max_idx = int(np.argmax(sims))
        max_sim = float(sims[max_idx])

        if max_sim >= EMBEDDING_MATCH_MODERATE:
            repo = repos[max_idx]
            strength = "STRONG" if max_sim >= EMBEDDING_MATCH_STRONG else "MODERATE"
            return MatchedProject(
                projectName=project.get("name", ""),
                repoName=repo.get("name", ""),
                repoFullName=repo.get("full_name", repo.get("name", "")),
                similarity=round(max_sim, 4),
                matchStage="EMBEDDING",
                matchStrength=strength,
            )
    except Exception as exc:
        logger.warning("Embedding match failed: %s", exc)

    return None


def _project_text(project: Dict[str, Any]) -> str:
    parts = []
    if project.get("name"):
        parts.append(project["name"])
    if project.get("description"):
        parts.append(project["description"])
    return " ".join(parts).strip()


def _repo_text(repo: Dict[str, Any]) -> str:
    parts = []
    if repo.get("name"):
        parts.append(repo["name"])
    if repo.get("description"):
        parts.append(repo["description"])
    topics = repo.get("topics", [])
    if topics:
        parts.append(" ".join(topics))
    return " ".join(parts).strip()
