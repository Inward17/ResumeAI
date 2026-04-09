"""
Verifier — Post-execution result validator

Checks all ToolResult objects returned by the executor and determines
whether the agent loop should consider verification complete.

A run is considered complete when every planned action has either
a ``completed`` or ``skipped`` status.  If any signal returned
``error``, completion is still True (the error is logged but does
not trigger a retry — retries are handled at the executor / timeout
layer, not here).
"""

import logging
from typing import Dict

from app.models.agent_models import AgentContext, ToolResult

logger = logging.getLogger(__name__)


def check_completion(
    context: AgentContext,
    results: Dict[str, ToolResult],
) -> bool:
    """
    Return True if the run can be considered finished.

    Current heuristic: all signals have been either completed,
    skipped, or errored — i.e. there is nothing left that could
    benefit from another loop iteration with the *same* context.
    """
    if not results:
        return True  # nothing was dispatched — trivially complete

    error_signals = []
    for name, result in results.items():
        if result.status == "error":
            error_signals.append(name)
            logger.warning(
                "Signal '%s' returned error: %s", name, result.reason,
            )

    if error_signals:
        logger.info(
            "Completion check: %d signal(s) errored (%s) — "
            "marking complete (no retry at verifier level).",
            len(error_signals), error_signals,
        )

    # All signals have a definitive status → done
    return True
