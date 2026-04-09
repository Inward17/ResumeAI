"""
Scoring Engine — Section 6.5

Computes a priority score for each undecided signal.
Signals above the threshold are added to `actions`;
signals below are added to `skip`.
The LLM planner is called only when scores cluster tightly
around the threshold (difference < AMBIGUITY_BAND).
"""

from typing import Dict, List, Tuple

from app.models.agent_models import AgentContext, VerificationPlan


# ── Constants (Section 6.5) ─────────────────────────────────────────────
IMPORTANCE: Dict[str, float] = {
    "github":     0.9,
    "linkedin":   0.7,
    "web_search": 0.5,
}

SCORE_THRESHOLD = 0.3
AMBIGUITY_BAND  = 0.1


# ── Score computation ───────────────────────────────────────────────────
def score_signals(
    undecided: List[str],
    context: AgentContext,
) -> Dict[str, float]:
    """
    Priority formula per signal:

        priority = importance(signal) × (1 - confidence) × freshness_factor

    Where:
        importance  – static weight per signal type
        confidence  – from SignalFreshness.confidence, range 0.0-1.0
        freshness_factor – 1.0 if not fresh, 0.4 if fresh but below
                           confidence threshold
    """
    scores: Dict[str, float] = {}
    freshness_map = {f.signal: f for f in context.freshness}

    for signal in undecided:
        f  = freshness_map[signal]
        ff = 1.0 if not f.is_fresh else 0.4
        scores[signal] = IMPORTANCE.get(signal, 0.5) * (1 - f.confidence) * ff

    return scores


# ── Apply scores to plan ────────────────────────────────────────────────
def apply_scores(
    scores: Dict[str, float],
    partial_plan: VerificationPlan,
) -> Tuple[VerificationPlan, List[str]]:
    """
    Classify each scored signal:
        score >= threshold + band  → actions
        score <= threshold - band  → skip
        otherwise                  → needs_llm (ambiguous)

    Returns
    -------
    (updated_plan, needs_llm)
    """
    needs_llm: List[str] = []

    for signal, score in scores.items():
        if score >= SCORE_THRESHOLD + AMBIGUITY_BAND:
            partial_plan.actions.append(signal)
            partial_plan.reasoning[signal] = f"score={score:.2f}_above_threshold"
        elif score <= SCORE_THRESHOLD - AMBIGUITY_BAND:
            partial_plan.skip.append(signal)
            partial_plan.reasoning[signal] = f"score={score:.2f}_below_threshold"
        else:
            needs_llm.append(signal)

    return partial_plan, needs_llm
