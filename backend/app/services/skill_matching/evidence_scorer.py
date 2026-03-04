"""
Evidence Scorer
===============
Core per-skill scoring logic.

For each required skill, we:
  1. Normalise to canonical form  (GCP → google cloud platform)
  2. Build a skill-phrase embedding  ("candidate experienced with <skill>")
  3. Compute cosine similarity against every resume section embedding
  4. Apply evidence-weighted scoring with a max-evidence bonus

Score formula (industry-standard, as recommended):
    weighted_sum = Σ(section_weight_i × similarity_i)
    max_bonus    = max(similarity_i) × MAX_BONUS_WEIGHT
    raw          = weighted_sum + max_bonus      # theoretical max = 1.25
    score        = clamp(raw / 1.25, 0, 1) × 10 # → 0–10

The max-bonus prevents a strong single signal (e.g. 0.90 GitHub similarity)
from being diluted by zero values in weaker sections.

Evidence weights reflect evidential reliability:
    github      → 0.35   (proved via actual code — hardest to fake)
    experience  → 0.30   (professional context)
    projects    → 0.25   (personal/academic context)
    skills      → 0.10   (self-declared — weakest, most gameable)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from .normalizer import normalize_skill

logger = logging.getLogger(__name__)

# ── Evidence weights ─────────────────────────────────────────────────────────
SECTION_WEIGHTS: Dict[str, float] = {
    "github":     0.35,
    "experience": 0.30,
    "projects":   0.25,
    "skills":     0.10,
}

# Bonus for the single strongest evidence signal (prevents dilution)
MAX_BONUS_WEIGHT: float = 0.25

# Theoretical maximum of weighted_sum + max_bonus (all sections = 1.0)
_SCORE_MAX: float = sum(SECTION_WEIGHTS.values()) + MAX_BONUS_WEIGHT  # = 1.25

# Minimum score to consider the skill "found"
_FOUND_THRESHOLD: float = 3.0


def _skill_phrase(canonical: str) -> str:
    """
    Build an enriched query phrase for a skill.

    Embedding a natural-language phrase captures semantic context better than
    embedding the bare skill token. E.g.:
        "kubernetes" → "candidate with hands-on experience using kubernetes"
    This improves cosine similarity with phrases like "deployed clusters on GKE"
    (which doesn't mention "kubernetes" literally).
    """
    return f"candidate with hands-on experience using {canonical} in production"


async def score_skill(
    skill: str,
    section_embeddings: Dict[str, List[float]],
) -> Dict[str, Any]:
    """
    Compute the evidence-weighted score (0–10) for a single *skill*.

    Args:
        skill:              Raw skill name from the job description.
        section_embeddings: Pre-computed embeddings keyed by section name.

    Returns:
        {
            "skill":      str,   # original job-requirement string
            "canonical":  str,   # normalised form used for embedding
            "score":      float, # 0–10
            "found":      bool,  # score >= _FOUND_THRESHOLD
            "evidence":   {section: similarity, ...}
        }
    """
    from app.services.embedding_service import generate_embedding, cosine_similarity

    canonical = normalize_skill(skill)
    phrase = _skill_phrase(canonical)

    try:
        skill_emb = await asyncio.to_thread(generate_embedding, phrase)
    except Exception as exc:
        logger.warning("evidence_scorer: failed to embed skill '%s': %s", skill, exc)
        return {
            "skill": skill,
            "canonical": canonical,
            "score": 0.0,
            "found": False,
            "evidence": {},
        }

    # ── Compute per-section similarities ────────────────────────────────────
    section_sims: Dict[str, float] = {}
    for section, emb in section_embeddings.items():
        if emb:
            sim = cosine_similarity(skill_emb, emb)
            section_sims[section] = round(max(0.0, float(sim)), 4)

    if not section_sims:
        return {
            "skill": skill,
            "canonical": canonical,
            "score": 0.0,
            "found": False,
            "evidence": {},
        }

    # ── Weighted sum ─────────────────────────────────────────────────────────
    weighted_sum = sum(
        SECTION_WEIGHTS.get(sec, 0.0) * sim
        for sec, sim in section_sims.items()
    )

    # ── Max-evidence bonus ───────────────────────────────────────────────────
    max_sim = max(section_sims.values())
    max_bonus = max_sim * MAX_BONUS_WEIGHT

    # ── Normalise to 0–10 ────────────────────────────────────────────────────
    raw = weighted_sum + max_bonus
    score = round(min(raw / _SCORE_MAX, 1.0) * 10, 2)
    found = score >= _FOUND_THRESHOLD

    return {
        "skill":     skill,
        "canonical": canonical,
        "score":     score,
        "found":     found,
        "evidence":  section_sims,
    }


async def score_all_skills(
    required_skills: List[str],
    section_embeddings: Dict[str, List[float]],
) -> List[Dict[str, Any]]:
    """
    Score all required skills concurrently against pre-computed section
    embeddings.  Returns a list in the same order as *required_skills*.
    """
    results = await asyncio.gather(
        *[score_skill(skill, section_embeddings) for skill in required_skills],
        return_exceptions=True,
    )

    output = []
    for skill, result in zip(required_skills, results):
        if isinstance(result, Exception):
            logger.warning(
                "evidence_scorer: score_skill failed for '%s': %s", skill, result
            )
            output.append({
                "skill": skill,
                "canonical": normalize_skill(skill),
                "score": 0.0,
                "found": False,
                "evidence": {},
            })
        else:
            output.append(result)

    return output
