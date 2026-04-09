"""
test_executor.py — Section 15

Covers concurrent dispatch, exception isolation, skipped signal logging.
All tool wrappers are mocked.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.models.agent_models import AgentContext, VerificationPlan, ToolResult, SignalFreshness
from app.agent.core.executor import execute_plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_context():
    return AgentContext(
        candidate_id="test-cand-1",
        job_id="test-job-1",
        verification_data={},
        freshness=[],
        job={"job_title": "SWE", "required_skills": ["Python"]},
        evaluation={},
        history=[],
    )


def _ok_result(name):
    return ToolResult(tool=name, status="completed", data={"ok": True}, reason=None, duration_ms=100)


async def _succeed(context):
    return _ok_result("github")


async def _fail(context):
    raise RuntimeError("Boom!")


async def _timeout(context):
    await asyncio.sleep(999)  # Will be cancelled by wait_for


# ===========================================================================
# Tests
# ===========================================================================
class TestExecutor:

    @pytest.mark.asyncio
    async def test_concurrent_dispatch_all_succeed(self):
        """All tools return successfully."""
        mock_registry = {
            "github": AsyncMock(return_value=_ok_result("github")),
            "linkedin": AsyncMock(return_value=_ok_result("linkedin")),
        }
        plan = VerificationPlan(
            actions=["github", "linkedin"], skip=[], reasoning={}, source="rule",
        )

        with patch("app.agent.core.executor.TOOL_REGISTRY", mock_registry):
            results = await execute_plan(plan, _make_context())

        assert results["github"].status == "completed"
        assert results["linkedin"].status == "completed"

    @pytest.mark.asyncio
    async def test_exception_isolation(self):
        """One tool raising does NOT cancel the other."""
        mock_registry = {
            "github": AsyncMock(side_effect=RuntimeError("Boom!")),
            "linkedin": AsyncMock(return_value=_ok_result("linkedin")),
        }
        plan = VerificationPlan(
            actions=["github", "linkedin"], skip=[], reasoning={}, source="rule",
        )

        with patch("app.agent.core.executor.TOOL_REGISTRY", mock_registry):
            results = await execute_plan(plan, _make_context())

        assert results["github"].status == "error"
        assert "Boom!" in results["github"].reason
        assert results["linkedin"].status == "completed"

    @pytest.mark.asyncio
    async def test_skipped_signals_logged(self):
        """Skipped signals appear in output with status='skipped'."""
        plan = VerificationPlan(
            actions=[], skip=["linkedin"], reasoning={"linkedin": "fresh_high_confidence"}, source="rule",
        )

        with patch("app.agent.core.executor.TOOL_REGISTRY", {}):
            results = await execute_plan(plan, _make_context())

        assert results["linkedin"].status == "skipped"
        assert results["linkedin"].reason == "fresh_high_confidence"

    @pytest.mark.asyncio
    async def test_unknown_tool_in_actions_ignored(self):
        """A tool name not in TOOL_REGISTRY is silently skipped."""
        plan = VerificationPlan(
            actions=["unknown_tool"], skip=[], reasoning={}, source="rule",
        )

        with patch("app.agent.core.executor.TOOL_REGISTRY", {}):
            results = await execute_plan(plan, _make_context())

        assert "unknown_tool" not in results

    @pytest.mark.asyncio
    async def test_timeout_produces_error_result(self):
        """A tool that exceeds TOOL_TIMEOUT_SEC returns status='error'."""

        async def slow_tool(ctx):
            await asyncio.sleep(999)

        mock_registry = {"github": slow_tool}
        plan = VerificationPlan(
            actions=["github"], skip=[], reasoning={}, source="rule",
        )

        with patch("app.agent.core.executor.TOOL_REGISTRY", mock_registry), \
             patch("app.agent.core.executor.TOOL_TIMEOUT_SEC", 0.1):
            results = await execute_plan(plan, _make_context())

        assert results["github"].status == "error"
        assert "timeout" in results["github"].reason

    @pytest.mark.asyncio
    async def test_empty_plan_returns_empty(self):
        """Plan with no actions and no skips returns empty dict."""
        plan = VerificationPlan(actions=[], skip=[], reasoning={}, source="rule")

        with patch("app.agent.core.executor.TOOL_REGISTRY", {}):
            results = await execute_plan(plan, _make_context())

        assert results == {}
