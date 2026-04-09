"""
Executor — Section 6.7

Dispatches all planned tool calls concurrently via asyncio.gather
with return_exceptions=True to isolate per-tool failures.
A timeout on LinkedIn does not cancel a concurrent GitHub call.

The executor is generic — it never contains knowledge of what any
tool does.  Adding a new tool requires only adding an entry to
TOOL_REGISTRY in agent_config.py; the executor needs no changes.
"""

import asyncio
import logging
from typing import Dict

from app.models.agent_models import AgentContext, VerificationPlan, ToolResult
from app.agent.config.agent_config import TOOL_REGISTRY, TOOL_TIMEOUT_SEC

logger = logging.getLogger(__name__)


async def execute_plan(
    plan: VerificationPlan,
    context: AgentContext,
) -> Dict[str, ToolResult]:
    """
    Run every action in the plan concurrently, capture individual
    failures as ToolResult(status='error'), and log every skipped
    signal from the plan.

    Returns
    -------
    dict[str, ToolResult]
        One entry per signal name (both executed and skipped).
    """
    # ── Build the async task map (only for known tools) ─────────────
    tasks: Dict[str, asyncio.Task] = {}
    for name in plan.actions:
        if name in TOOL_REGISTRY:
            tasks[name] = asyncio.ensure_future(
                asyncio.wait_for(
                    TOOL_REGISTRY[name](context),
                    timeout=TOOL_TIMEOUT_SEC,
                )
            )
        else:
            logger.warning("Skipping unknown tool in plan: %s", name)

    output: Dict[str, ToolResult] = {}

    if tasks:
        # ── Dispatch concurrently, isolate failures ─────────────────
        results_raw = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        for name, res in zip(tasks.keys(), results_raw):
            if isinstance(res, asyncio.TimeoutError):
                logger.error("Tool %s timed out after %ds", name, TOOL_TIMEOUT_SEC)
                output[name] = ToolResult(
                    tool        = name,
                    status      = "error",
                    data        = None,
                    reason      = f"timeout_after_{TOOL_TIMEOUT_SEC}s",
                    duration_ms = TOOL_TIMEOUT_SEC * 1000,
                )
            elif isinstance(res, Exception):
                logger.error("Tool %s failed: %s", name, res)
                output[name] = ToolResult(
                    tool        = name,
                    status      = "error",
                    data        = None,
                    reason      = str(res),
                    duration_ms = 0,
                )
            else:
                output[name] = res

    # ── Log skipped signals from the plan ───────────────────────────
    for name in plan.skip:
        output[name] = ToolResult(
            tool        = name,
            status      = "skipped",
            data        = None,
            reason      = plan.reasoning.get(name, "skipped_by_plan"),
            duration_ms = 0,
        )

    return output
