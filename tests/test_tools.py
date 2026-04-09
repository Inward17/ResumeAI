"""
test_tools.py — Section 15

Tests ToolResult.status for the no_url/no_entity case and success case
for each tool wrapper.  All service calls are mocked.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.agent_models import AgentContext, ToolResult, SignalFreshness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_context(verification_data=None):
    return AgentContext(
        candidate_id="test-cand-1",
        job_id="test-job-1",
        verification_data=verification_data or {},
        freshness=[],
        job={"job_title": "SWE", "required_skills": ["Python"]},
        evaluation={},
        history=[],
    )


# ===========================================================================
# GitHub Tool
# ===========================================================================
class TestGitHubTool:

    @pytest.mark.asyncio
    async def test_no_url_skipped(self):
        from app.agent.tools.github_tool import run
        result = await run(_make_context({}))
        assert result.status == "skipped"
        assert result.reason == "no_github_url"
        assert result.duration_ms == 0

    @pytest.mark.asyncio
    async def test_success_returns_completed(self):
        from app.agent.tools.github_tool import run

        mock_result = MagicMock()
        mock_result.to_mongo_dict.return_value = {"score": 85, "success": True}

        ctx = _make_context({"githubUrl": "https://github.com/testuser"})

        with patch("app.agent.tools.github_tool.verify_github", new_callable=AsyncMock, return_value=mock_result):
            result = await run(ctx)

        assert result.status == "completed"
        assert result.data == {"score": 85, "success": True}
        assert result.duration_ms > 0


# ===========================================================================
# LinkedIn Tool
# ===========================================================================
class TestLinkedInTool:

    @pytest.mark.asyncio
    async def test_no_url_skipped(self):
        from app.agent.tools.linkedin_tool import run
        result = await run(_make_context({}))
        assert result.status == "skipped"
        assert result.reason == "no_linkedin_url"
        assert result.duration_ms == 0

    @pytest.mark.asyncio
    async def test_success_returns_completed(self):
        from app.agent.tools.linkedin_tool import run

        profile = {"firstName": "Jane", "lastName": "Doe"}
        mock_response = {"status": "success", "data": [profile]}

        ctx = _make_context({"linkedinUrl": "https://linkedin.com/in/janedoe"})

        with patch("app.agent.tools.linkedin_tool.scrape_linkedin_profiles",
                    new_callable=AsyncMock, return_value=mock_response):
            result = await run(ctx)

        assert result.status == "completed"
        assert result.data == profile
        assert result.duration_ms > 0


# ===========================================================================
# Web Search Tool
# ===========================================================================
class TestWebSearchTool:

    @pytest.mark.asyncio
    async def test_no_entities_skipped(self):
        from app.agent.tools.websearch_tool import run
        result = await run(_make_context({}))
        assert result.status == "skipped"
        assert result.reason == "no_entities_to_verify"

    @pytest.mark.asyncio
    async def test_success_returns_completed(self):
        from app.agent.tools.websearch_tool import run

        ctx = _make_context({
            "educations": [{"institution": "IIT Delhi"}],
            "experiences": [{"company": "Google"}],
        })
        mock_verification = {"university": {"average_score": 85}, "company": {"average_score": 90}}

        with patch("app.agent.tools.websearch_tool.verify_profile",
                    new_callable=AsyncMock, return_value=mock_verification):
            result = await run(ctx)

        assert result.status == "completed"
        assert result.data == mock_verification
        assert result.duration_ms > 0


# ===========================================================================
# Verification Tool
# ===========================================================================
class TestVerificationTool:

    @pytest.mark.asyncio
    async def test_success_returns_completed(self):
        from app.agent.tools.verification_tool import run

        mock_result = MagicMock()
        mock_result.dict.return_value = {"candidateId": "test", "matchScore": {}}

        ctx = _make_context({
            "githubUrl": "https://github.com/testuser",
            "linkedinUrl": "https://linkedin.com/in/test",
        })

        with patch("app.agent.tools.verification_tool.unified_verification_service") as mock_svc:
            mock_svc.run_unified_verification = AsyncMock(return_value=mock_result)
            result = await run(ctx)

        assert result.status == "completed"
        assert result.data == {"candidateId": "test", "matchScore": {}}
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        from app.agent.tools.verification_tool import run

        ctx = _make_context({})

        with patch("app.agent.tools.verification_tool.unified_verification_service") as mock_svc:
            mock_svc.run_unified_verification = AsyncMock(side_effect=RuntimeError("DB down"))
            result = await run(ctx)

        assert result.status == "error"
        assert "DB down" in result.reason
