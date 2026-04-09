"""
Session Memory — Section 6.9

Ephemeral per-request state.  Tracks which actions have been taken
this session, accumulates tool results, and provides the ``history``
list injected into AgentContext.

Not persisted between requests — persistence is handled by MongoDB
(the context builder reads MongoDB at the start of every loop iteration).
"""

from typing import Dict, List

from app.models.agent_models import VerificationPlan, ToolResult


class SessionMemory:
    """One instance per agent run (per API request)."""

    def __init__(self, candidate_id: str):
        self.candidate_id: str = candidate_id
        self.action_history: List[str] = []
        self.skipped: List[str] = []
        self.plan_source: str = "rule"          # updated after each plan
        self._results: Dict[str, ToolResult] = {}

    # ── called after each loop iteration ────────────────────────────
    def update(self, plan: VerificationPlan, results: Dict[str, ToolResult]):
        """Merge the latest plan actions and tool results into memory."""
        self.action_history.extend(plan.actions)
        self.skipped.extend(plan.skip)
        self.plan_source = plan.source
        self._results.update(results)

    # ── accessors ───────────────────────────────────────────────────
    def get_all_results(self) -> Dict[str, ToolResult]:
        return self._results

    def get_summary(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "actions_taken": self.action_history,
            "signals_skipped": self.skipped,
            "plan_source": self.plan_source,
            "results": {k: v.dict() for k, v in self._results.items()},
        }
