"""
Enterprise GitHub Verification — Signal Fusion Scoring
Dynamic weight redistribution + final score computation.

Formulas:
  score = Σ(weight_i * signal_i)  for available signals
  Weights are redistributed proportionally if any signal is unavailable.
  score100 = round(score * 100, 2)
  score40  = round(score100 * 0.4)

Confidence:
  std_dev(available signals)
    < 0.15 → HIGH
    0.15–0.30 → MEDIUM
    > 0.30 → LOW
    < 3 signals → LOW always

Explainability:
  Rule-based red flags — NOT LLM generated.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from ..config import (
    CONFIDENCE_HIGH_MAX_STD,
    CONFIDENCE_MEDIUM_MAX_STD,
    MIN_SIGNALS_FOR_CONFIDENCE,
    RED_FLAG_RULES,
    SIGNAL_WEIGHTS,
)
from ..models import AuthenticityResult, SignalScores

logger = logging.getLogger(__name__)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


# ═══════════════════════════════════════════════════════════════════
# Dynamic weight redistribution
# ═══════════════════════════════════════════════════════════════════

def _redistribute_weights(
    available: Dict[str, float],
) -> Dict[str, float]:
    """
    Given a dict of signal_name → value for AVAILABLE signals,
    return a dict of signal_name → adjusted_weight that sums to 1.0.

    Missing signals have their weight redistributed proportionally
    among the remaining signals.
    """
    present_names = set(available.keys())
    present_weights = {k: v for k, v in SIGNAL_WEIGHTS.items() if k in present_names}

    total_present = sum(present_weights.values())
    if total_present == 0:
        # All signals missing — equal weight fallback
        n = len(present_names) or 1
        return {k: 1.0 / n for k in present_names}

    # Scale up so they sum to 1.0
    return {k: v / total_present for k, v in present_weights.items()}


# ═══════════════════════════════════════════════════════════════════
# Confidence
# ═══════════════════════════════════════════════════════════════════

def compute_confidence(values: List[float]) -> str:
    """
    std_dev of available signals →
      < 0.15  → HIGH
      ≤ 0.30  → MEDIUM
      > 0.30  → LOW
      < 3 signals → LOW
    """
    if len(values) < MIN_SIGNALS_FOR_CONFIDENCE:
        return "LOW"

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)

    if std_dev < CONFIDENCE_HIGH_MAX_STD:
        return "HIGH"
    if std_dev <= CONFIDENCE_MEDIUM_MAX_STD:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════
# Red flags (rule-based, deterministic)
# ═══════════════════════════════════════════════════════════════════

def generate_red_flags(
    raw_signals: Dict[str, float],
) -> List[str]:
    """
    Evaluate RED_FLAG_RULES against the raw signal dict.
    Each rule that fires produces a human-readable message.
    """
    flags: List[str] = []

    for rule_name, rule in RED_FLAG_RULES.items():
        signal_key = rule["signal"]
        threshold = rule["threshold"]
        direction = rule["direction"]
        message = rule["message"]

        value = raw_signals.get(signal_key)
        if value is None:
            continue

        if direction == "below" and value < threshold:
            flags.append(message)
        elif direction == "above" and value > threshold:
            flags.append(message)

    return flags


# ═══════════════════════════════════════════════════════════════════
# Public API — fuse all signals
# ═══════════════════════════════════════════════════════════════════

def fuse_signals(
    signals: SignalScores,
    raw_signals: Optional[Dict[str, float]] = None,
) -> Tuple[AuthenticityResult, List[str]]:
    """
    Compute final score, confidence, clone risk, and red flags.

    Args:
        signals:     populated SignalScores (None-fields = unavailable)
        raw_signals: optional dict with extra raw values for red-flag evaluation
                     (e.g. ``burstRisk``, ``messageQuality``, ``originalRatio``)

    Returns:
        (AuthenticityResult, red_flags_list)
    """
    # Collect available signals
    available: Dict[str, float] = {}
    for name in SIGNAL_WEIGHTS:
        value = getattr(signals, name, None)
        if value is not None:
            available[name] = _clamp(value)

    if not available:
        return (
            AuthenticityResult(
                probability=0.0,
                score100=0.0,
                score40=0,
                cloneRiskProbability=0.0,
                confidenceLevel="LOW",
            ),
            ["No verification signals available"],
        )

    # Dynamic weight redistribution
    weights = _redistribute_weights(available)

    # Weighted sum
    score = sum(weights[k] * available[k] for k in available)
    score = _clamp(score)

    score100 = round(score * 100, 2)
    score40 = round(score100 * 0.4)

    # Confidence
    values = list(available.values())
    confidence = compute_confidence(values)

    # Clone risk = max of code and readme similarity (inverse of originality)
    code_orig = available.get("CodeOriginality", 1.0)
    readme_orig = available.get("ReadmeOriginality", 1.0)
    clone_risk = max(1.0 - code_orig, 1.0 - readme_orig)
    clone_risk = _clamp(clone_risk)

    # Red flags
    combined_raw = dict(raw_signals or {})
    # Also inject the signal values for rules that reference them
    combined_raw.setdefault("ResumeConsistency", available.get("ResumeConsistency", 1.0))
    combined_raw.setdefault("codeSimilarityMax", 1.0 - code_orig)
    combined_raw.setdefault("readmeSimilarityMax", 1.0 - readme_orig)

    red_flags = generate_red_flags(combined_raw)

    auth = AuthenticityResult(
        probability=round(score, 4),
        score100=score100,
        score40=score40,
        cloneRiskProbability=round(clone_risk, 4),
        confidenceLevel=confidence,
    )
    return auth, red_flags
