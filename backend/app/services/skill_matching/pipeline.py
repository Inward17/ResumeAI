"""
Unified Skill Scoring Pipeline
================================
Public entry point for the skill_matching package.

    from app.services.skill_matching.pipeline import run_unified_skill_scoring

    result = await run_unified_skill_scoring(
        required_skills=["Python", "GCP", "Kubernetes"],
        parsed=parsed_resume_dict,
        github_v2_data=github_v2_data_dict,  # optional
    )

    # result shape:
    {
        "skill_scores": [
            {
                "skill":     "Kubernetes",
                "canonical": "kubernetes",
                "score":     7.1,        # 0–10
                "found":     True,
                "evidence": {
                    "github":     0.82,
                    "experience": 0.61,
                    "projects":   0.74,
                    "skills":     0.45,
                }
            },
            ...
        ],
        "jd_match_score": 7.4,   # 0–10, avg of all skill scores
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .section_embedder import embed_sections, extract_section_texts
from .evidence_scorer import score_all_skills

logger = logging.getLogger(__name__)


async def run_unified_skill_scoring(
    required_skills: List[str],
    parsed: Dict[str, Any],
    preferred_skills: Optional[List[str]] = None,
    github_v2_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the full unified skill-evidence scoring pipeline.

    Replaces the previous three-pipeline system:
        - compute_skill_matches()   (keyword/fuzzy per-section)
        - calculate_jd_match()      (document-level embedding)
        - ensure_github_projects_embedding()

    Steps:
        1. Extract text corpora from each resume section + GitHub data
        2. Embed all sections concurrently  (one vector per section)
        3. For each required skill:
             a. Normalise alias  (GCP → google cloud platform)
             b. Build skill phrase  ("candidate experienced with ...")
             c. Embed skill phrase
             d. Cosine-similarity against all section embeddings
             e. Apply evidence-weighted score + max-bonus
        4. Aggregate: jd_match_score = mean(all skill scores)

    Args:
        required_skills:  List of required skill strings from the job posting.
        preferred_skills: Optional preferred skills. Accepted for backward
                          compatibility with older callers and merged into the
                          scoring list in-order without duplicates.
        parsed:           Parsed resume dict (from parser.py output).
        github_v2_data:   github_v2_data field from verification_data.githubData
                          (optional — pipeline degrades gracefully without it).

    Returns:
        {
            "skill_scores":   List[Dict],  # per-skill results
            "jd_match_score": float,       # 0–10
        }

    This function is failure-safe: any internal exception returns zeroed
    results so the application creation flow is never interrupted.
    """
    _empty = {"skill_scores": [], "jd_match_score": 0.0}

    preferred_skills = preferred_skills or []
    all_skills = list(dict.fromkeys([
        skill for skill in [*(required_skills or []), *preferred_skills] if skill
    ]))

    if not all_skills:
        return _empty

    try:
        # ── Step 1: extract text ────────────────────────────────────────────
        section_texts = extract_section_texts(parsed, github_v2_data)

        logger.debug(
            "skill_matching: section lengths — skills=%d  exp=%d  proj=%d  github=%d",
            len(section_texts.get("skills", "")),
            len(section_texts.get("experience", "")),
            len(section_texts.get("projects", "")),
            len(section_texts.get("github", "")),
        )

        # ── Step 2: embed sections concurrently ────────────────────────────
        section_embeddings = await embed_sections(section_texts)

        if not section_embeddings:
            logger.warning(
                "skill_matching: no section embeddings available for scoring"
            )
            return _empty

        # ── Step 3: score each skill concurrently ──────────────────────────
        skill_scores = await score_all_skills(all_skills, section_embeddings)

        # ── Step 4: aggregate ───────────────────────────────────────────────
        if skill_scores:
            jd_match_score = round(
                sum(s["score"] for s in skill_scores) / len(skill_scores), 2
            )
        else:
            jd_match_score = 0.0

        logger.info(
            "skill_matching: scored %d skills → jd_match_score=%.2f",
            len(skill_scores),
            jd_match_score,
        )

        return {
            "skill_scores":   skill_scores,
            "jd_match_score": jd_match_score,
        }

    except Exception as exc:
        logger.error(
            "skill_matching: pipeline failed for %d skills: %s",
            len(all_skills),
            exc,
            exc_info=True,
        )
        return _empty
