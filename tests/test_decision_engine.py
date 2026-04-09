"""
test_decision_engine.py — Section 15

Covers all rule engine cases and scoring engine boundary conditions.
"""

import pytest
from datetime import datetime, timedelta

from app.models.agent_models import SignalFreshness, AgentContext, VerificationPlan
from app.agent.decision.rule_engine import apply_rules
from app.agent.decision.scoring_engine import score_signals, apply_scores, SCORE_THRESHOLD, AMBIGUITY_BAND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_context(freshness_list, verification_data=None, job=None):
    return AgentContext(
        candidate_id="test-cand-1",
        job_id="test-job-1",
        verification_data=verification_data or {},
        freshness=freshness_list,
        job=job or {"job_title": "Software Engineer", "required_skills": ["Python"]},
        evaluation={},
        history=[],
    )


def _fresh_signal(signal, confidence, last_verified=None, is_fresh=True):
    return SignalFreshness(
        signal=signal,
        last_verified=last_verified or datetime.utcnow(),
        is_fresh=is_fresh,
        confidence=confidence,
    )


# ===========================================================================
# Rule Engine Tests
# ===========================================================================
class TestRuleEngine:
    """All four rule cases: never_verified, fresh_high_confidence, no_url, undecided."""

    def test_never_verified_goes_to_actions(self):
        """Rule 1: signal with last_verified=None must be in actions."""
        f = SignalFreshness(signal="github", last_verified=None, is_fresh=False, confidence=0.0)
        ctx = _make_context([f])
        plan, undecided = apply_rules(ctx)

        assert "github" in plan.actions
        assert "github" not in undecided
        assert plan.reasoning["github"] == "never_verified"

    def test_fresh_high_confidence_skipped(self):
        """Rule 2: fresh + confidence >= 0.85 must be skipped."""
        f = _fresh_signal("linkedin", confidence=0.90, is_fresh=True)
        ctx = _make_context([f])
        plan, undecided = apply_rules(ctx)

        assert "linkedin" in plan.skip
        assert "linkedin" not in undecided
        assert plan.reasoning["linkedin"] == "fresh_high_confidence"

    def test_fresh_low_confidence_is_undecided(self):
        """Rule 2 boundary: fresh but confidence < 0.85 → undecided."""
        f = _fresh_signal("github", confidence=0.50, is_fresh=True)
        ctx = _make_context([f], verification_data={"githubUrl": "https://github.com/test"})
        plan, undecided = apply_rules(ctx)

        assert "github" not in plan.actions
        assert "github" not in plan.skip
        assert "github" in undecided

    def test_no_source_url_skipped(self):
        """Rule 3: GitHub/LinkedIn with no URL must be skipped."""
        f = _fresh_signal("github", confidence=0.50, is_fresh=False)
        ctx = _make_context([f], verification_data={})  # no githubUrl
        plan, undecided = apply_rules(ctx)

        assert "github" in plan.skip
        assert plan.reasoning["github"] == "no_source_url"

    def test_web_search_no_url_rule_not_applied(self):
        """web_search has no URL rule — stale + low confidence → undecided."""
        f = _fresh_signal("web_search", confidence=0.50, is_fresh=False)
        ctx = _make_context([f])
        plan, undecided = apply_rules(ctx)

        assert "web_search" in undecided

    def test_plan_source_is_rule(self):
        f = SignalFreshness(signal="github", last_verified=None, is_fresh=False, confidence=0.0)
        ctx = _make_context([f])
        plan, _ = apply_rules(ctx)
        assert plan.source == "rule"

    def test_multiple_signals_classified_independently(self):
        """Each signal evaluated independently."""
        signals = [
            SignalFreshness(signal="github", last_verified=None, is_fresh=False, confidence=0.0),
            _fresh_signal("linkedin", confidence=0.95, is_fresh=True),
            _fresh_signal("web_search", confidence=0.30, is_fresh=False),
        ]
        ctx = _make_context(signals)
        plan, undecided = apply_rules(ctx)

        assert "github" in plan.actions        # never_verified
        assert "linkedin" in plan.skip         # fresh+high
        assert "web_search" in undecided       # no rule matched


# ===========================================================================
# Scoring Engine Tests
# ===========================================================================
class TestScoringEngine:

    def test_score_high_above_threshold(self):
        """Confidence 0.0, not fresh → max priority → actions."""
        f = _fresh_signal("github", confidence=0.0, is_fresh=False)
        ctx = _make_context([f])

        scores = score_signals(["github"], ctx)
        assert scores["github"] == pytest.approx(0.9, abs=0.01)  # 0.9 * 1.0 * 1.0

        plan = VerificationPlan(actions=[], skip=[], reasoning={}, source="score")
        plan, needs_llm = apply_scores(scores, plan)
        assert "github" in plan.actions
        assert "github" not in needs_llm

    def test_score_low_below_threshold(self):
        """Confidence 1.0 → priority 0.0 → skip."""
        f = _fresh_signal("web_search", confidence=1.0, is_fresh=False)
        ctx = _make_context([f])

        scores = score_signals(["web_search"], ctx)
        assert scores["web_search"] == pytest.approx(0.0, abs=0.01)

        plan = VerificationPlan(actions=[], skip=[], reasoning={}, source="score")
        plan, needs_llm = apply_scores(scores, plan)
        assert "web_search" in plan.skip

    def test_ambiguity_band_needs_llm(self):
        """Score within ±AMBIGUITY_BAND of threshold → needs_llm."""
        # importance(linkedin) = 0.7, confidence to put score in band:
        # 0.7 * (1 - c) * 1.0 ≈ 0.3   →   c ≈ 0.571
        f = _fresh_signal("linkedin", confidence=0.571, is_fresh=False)
        ctx = _make_context([f])

        scores = score_signals(["linkedin"], ctx)
        # Score ≈ 0.7 * 0.429 ≈ 0.30 — right on the threshold

        plan = VerificationPlan(actions=[], skip=[], reasoning={}, source="score")
        plan, needs_llm = apply_scores(scores, plan)
        assert "linkedin" in needs_llm

    def test_fresh_signal_gets_dampened(self):
        """Fresh signals get freshness_factor=0.4, lowering priority."""
        f = _fresh_signal("github", confidence=0.0, is_fresh=True)
        ctx = _make_context([f])

        scores = score_signals(["github"], ctx)
        assert scores["github"] == pytest.approx(0.36, abs=0.01)  # 0.9 * 1.0 * 0.4

    def test_confidence_one_kills_score(self):
        """Confidence = 1.0 means (1-confidence) = 0 → score = 0."""
        f = _fresh_signal("github", confidence=1.0, is_fresh=False)
        ctx = _make_context([f])
        scores = score_signals(["github"], ctx)
        assert scores["github"] == 0.0
