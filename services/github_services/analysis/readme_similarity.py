"""
Enterprise GitHub Verification — README Similarity Pipeline
For each selected repo:
  1. Fetch candidate README
  2. Search 10 similar external repos
  3. Fetch their READMEs
  4. Embed all with BGE-large
  5. Compute cosine, record max
  6. Threshold → COPIED / SUSPICIOUS / ORIGINAL
  7. ReadmeOriginality = 1 - readmeSimilarityMax
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import (
    MAX_EXTERNAL_REPOS,
    README_SIMILARITY_COPIED,
    README_SIMILARITY_SUSPICIOUS,
)
from ..github_client import GitHubClient

logger = logging.getLogger(__name__)


async def analyse_readme_similarity(
    repos: List[Dict[str, Any]],
    client: GitHubClient,
) -> Dict[str, Any]:
    """
    Run README similarity pipeline across *repos* (max 3).

    Returns::

        {
            "readmeSimilarityMax": float,
            "readmeVerdict": str,
            "readmeMatchedRepo": str | None,
            "readmeOriginality": float,
            "repoDetails": [...]
        }
    """
    from ..matching.project_matcher import _embed_texts_bge

    overall_max_sim: float = 0.0
    overall_matched: Optional[str] = None
    repo_details: List[Dict[str, Any]] = []

    for repo in repos:
        owner = repo.get("owner", {})
        owner_login = owner.get("login", owner) if isinstance(owner, dict) else str(owner)
        repo_name = repo.get("name", "")

        # 1. Fetch candidate README
        readme = await client.get_repo_readme(owner_login, repo_name)
        if not readme or len(readme) < 100:
            repo_details.append({
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": "README missing or too short",
            })
            continue

        # 2. Search similar external repos
        search_query = repo_name
        if repo.get("description"):
            search_query += " " + repo["description"][:80]
        ext_repos = await client.search_similar_repos(search_query, limit=MAX_EXTERNAL_REPOS)
        # Exclude candidate's own repo
        ext_repos = [r for r in ext_repos if r.get("full_name", "") != repo.get("full_name", "")]

        if not ext_repos:
            repo_details.append({
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": "No external repos found for comparison",
            })
            continue

        # 3. Fetch external READMEs in parallel
        ext_readmes: List[Tuple[Dict, Optional[str]]] = []

        async def _fetch_readme(r: Dict[str, Any]):
            text = await client.get_repo_readme(r["owner"], r["name"])
            return r, text

        tasks = [_fetch_readme(r) for r in ext_repos]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_refs: List[Tuple[Dict, str]] = []
        for res in results:
            if isinstance(res, Exception):
                continue
            r, text = res
            if text and len(text) >= 100:
                valid_refs.append((r, text))

        if not valid_refs:
            repo_details.append({
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": "No valid external READMEs found",
            })
            continue

        # 4. Embed candidate + external READMEs
        try:
            all_texts = [readme] + [t for _, t in valid_refs]
            embeddings = await _embed_texts_bge(all_texts)

            candidate_emb = embeddings[0]
            ref_embs = embeddings[1:]

            # 5. Cosine similarity (dot product of L2-normalised)
            sims = ref_embs @ candidate_emb
            max_idx = int(np.argmax(sims))
            max_sim = float(max(0.0, min(1.0, sims[max_idx])))

            matched_ref = valid_refs[max_idx][0]
            matched_name = matched_ref.get("full_name", "")

        except Exception as exc:
            logger.warning("README embedding failed for %s: %s", repo_name, exc)
            repo_details.append({
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": f"Embedding error: {exc}",
            })
            continue

        # 6. Verdict
        verdict = _verdict(max_sim)

        repo_details.append({
            "repo": repo_name,
            "similarity": round(max_sim, 4),
            "verdict": verdict,
            "matchedRepo": matched_name,
            "skipped": False,
        })

        if max_sim > overall_max_sim:
            overall_max_sim = max_sim
            overall_matched = matched_name

    # 7. Aggregate
    originality = max(0.0, min(1.0, 1.0 - overall_max_sim))

    return {
        "readmeSimilarityMax": round(overall_max_sim, 4),
        "readmeVerdict": _verdict(overall_max_sim),
        "readmeMatchedRepo": overall_matched,
        "readmeOriginality": round(originality, 4),
        "repoDetails": repo_details,
    }


def _verdict(sim: float) -> str:
    if sim >= README_SIMILARITY_COPIED:
        return "COPIED"
    if sim >= README_SIMILARITY_SUSPICIOUS:
        return "SUSPICIOUS"
    return "ORIGINAL"
