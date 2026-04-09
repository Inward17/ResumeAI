"""
test_agent_vs_legacy.py — Section 10

Parity test exactly as specified in the architecture document.
Asserts:
    - No dropped signals (agent must not drop a signal legacy verified)
    - Score delta under 0.05
    - Tier non-regression (agent tier >= legacy tier - 1)
"""

import pytest


# ---------------------------------------------------------------------------
# Tier ordering
# ---------------------------------------------------------------------------
TIER_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1}


# ---------------------------------------------------------------------------
# The parity assertion function (directly from Section 10)
# ---------------------------------------------------------------------------
def assert_parity(legacy_result: dict, agent_result: dict):
    """
    Verify that the agent result does not regress compared to legacy.

    This does NOT assert strict equality — the agent legitimately skips
    checks that legacy always runs.  The correct assertion is: for every
    signal that legacy verified and produced a non-null result, the agent
    must also produce a non-null result of acceptable quality.
    """
    for signal in ["github", "linkedin", "web_search"]:
        legacy_data = legacy_result.get(f"{signal}Data")
        agent_data = agent_result.get(f"{signal}Data")

        if legacy_data is None:
            continue  # legacy couldn't verify either; agent skip is fine

        # Agent must not drop a signal that legacy successfully verified
        assert agent_data is not None, f"Agent dropped verified signal: {signal}"

        # Score delta must be within acceptable threshold
        legacy_score = legacy_data.get("confidence_score", 0)
        agent_score = agent_data.get("confidence_score", 0)
        assert abs(legacy_score - agent_score) < 0.05, \
            f"Score divergence on {signal}: legacy={legacy_score} agent={agent_score}"

    # Tier must not regress
    legacy_tier = legacy_result.get("matchScore", {}).get("tier", "D")
    agent_tier = agent_result.get("matchScore", {}).get("tier", "D")
    assert TIER_ORDER[agent_tier] >= TIER_ORDER[legacy_tier] - 1, \
        f"Tier regressed: legacy={legacy_tier} agent={agent_tier}"


# ===========================================================================
# Tests
# ===========================================================================
class TestParity:

    def test_identical_results_pass(self):
        """Both produce the same output → parity passes."""
        result = {
            "githubData":    {"confidence_score": 0.85},
            "linkedinData":  {"confidence_score": 0.90},
            "web_searchData": {"confidence_score": 0.75},
            "matchScore":    {"tier": "A"},
        }
        assert_parity(result, result)  # should not raise

    def test_agent_skips_unverified_signal_ok(self):
        """Legacy has None for a signal → agent can also skip it."""
        legacy = {
            "githubData":    {"confidence_score": 0.85},
            "linkedinData":  None,
            "web_searchData": {"confidence_score": 0.75},
            "matchScore":    {"tier": "B"},
        }
        agent = {
            "githubData":    {"confidence_score": 0.85},
            "linkedinData":  None,
            "web_searchData": {"confidence_score": 0.75},
            "matchScore":    {"tier": "B"},
        }
        assert_parity(legacy, agent)

    def test_agent_drops_verified_signal_fails(self):
        """Agent drops a signal legacy verified → assertion error."""
        legacy = {
            "githubData":    {"confidence_score": 0.85},
            "linkedinData":  {"confidence_score": 0.90},
            "matchScore":    {"tier": "B"},
        }
        agent = {
            "githubData":    {"confidence_score": 0.85},
            "linkedinData":  None,  # DROPPED!
            "matchScore":    {"tier": "B"},
        }
        with pytest.raises(AssertionError, match="Agent dropped verified signal: linkedin"):
            assert_parity(legacy, agent)

    def test_score_divergence_fails(self):
        """Score delta > 0.05 → assertion error."""
        legacy = {
            "githubData": {"confidence_score": 0.90},
            "matchScore": {"tier": "A"},
        }
        agent = {
            "githubData": {"confidence_score": 0.80},  # delta = 0.10 > 0.05
            "matchScore": {"tier": "A"},
        }
        with pytest.raises(AssertionError, match="Score divergence"):
            assert_parity(legacy, agent)

    def test_score_within_threshold_passes(self):
        """Score delta < 0.05 → passes."""
        legacy = {
            "githubData": {"confidence_score": 0.90},
            "matchScore": {"tier": "A"},
        }
        agent = {
            "githubData": {"confidence_score": 0.88},  # delta = 0.02 < 0.05
            "matchScore": {"tier": "A"},
        }
        assert_parity(legacy, agent)

    def test_tier_regression_fails(self):
        """Agent tier drops by 2+ → assertion error."""
        legacy = {"matchScore": {"tier": "A"}}
        agent = {"matchScore": {"tier": "C"}}  # A(4) → C(2) = drop of 2
        with pytest.raises(AssertionError, match="Tier regressed"):
            assert_parity(legacy, agent)

    def test_tier_one_step_drop_ok(self):
        """Agent tier drops by 1 → acceptable (within tolerance)."""
        legacy = {"matchScore": {"tier": "A"}}
        agent = {"matchScore": {"tier": "B"}}  # A(4) → B(3) = drop of 1
        assert_parity(legacy, agent)  # should not raise

    def test_tier_improvement_ok(self):
        """Agent tier improves → always fine."""
        legacy = {"matchScore": {"tier": "C"}}
        agent = {"matchScore": {"tier": "A"}}
        assert_parity(legacy, agent)
