"""
Rule Engine — Section 6.4

Handles all deterministic decisions before scoring or LLM are invoked.
Returns a partial VerificationPlan (signals already decided) and a
list of signals still requiring a decision ('undecided').
"""

from typing import List, Tuple

from app.models.agent_models import AgentContext, VerificationPlan


# Map signal names to the URL field expected in verification_data
_URL_FIELDS = {
    "github":   "githubUrl",
    "linkedin": "linkedinUrl",
}


def apply_rules(context: AgentContext) -> Tuple[VerificationPlan, List[str]]:
    """
    Walk through every signal in the context's freshness list and
    apply deterministic rules.  Signals that no rule matches are
    collected into the `undecided` list for downstream scoring.

    Returns
    -------
    (partial_plan, undecided)
        partial_plan  – VerificationPlan with actions/skip already decided
        undecided     – signal names that need scoring / LLM resolution
    """
    actions:   List[str] = []
    skip:      List[str] = []
    reasoning: dict      = {}
    undecided: List[str] = []

    for f in context.freshness:
        signal = f.signal

        # ── Rule 1: signal has never been verified → must verify ─────
        if f.last_verified is None:
            actions.append(signal)
            reasoning[signal] = "never_verified"
            continue

        # ── Rule 2: fresh AND high confidence → skip ─────────────────
        if f.is_fresh and f.confidence >= 0.85:
            skip.append(signal)
            reasoning[signal] = "fresh_high_confidence"
            continue

        # ── Rule 3: source URL is missing → skip (cannot re-verify) ──
        url_field = _URL_FIELDS.get(signal)
        if url_field:
            # Check both top-level keys and nested personal_info keys
            personal_info = context.verification_data.get("personal_info", {})
            _PI_FIELDS = {"github": "github", "linkedin": "linkedin"}
            has_url = (
                context.verification_data.get(url_field)
                or personal_info.get(_PI_FIELDS.get(signal, ""))
                or context.verification_data.get("github_username" if signal == "github" else "linkedin_url", None)
            )
            if not has_url:
                skip.append(signal)
                reasoning[signal] = "no_source_url"
                continue

        # ── No rule matched → pass to scoring engine ─────────────────
        undecided.append(signal)

    partial_plan = VerificationPlan(
        actions   = actions,
        skip      = skip,
        reasoning = reasoning,
        source    = "rule",
    )

    return partial_plan, undecided
