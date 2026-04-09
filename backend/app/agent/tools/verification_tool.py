"""
Verification Tool Wrapper — Section 6.8

Thin async adapter that calls the existing unified_verification
service with candidate_id and job_id from AgentContext,
and normalises the output into a ToolResult.
"""

import time
import logging

from app.models.agent_models import AgentContext, ToolResult
from app.services.unified_verification import unified_verification_service

logger = logging.getLogger(__name__)


async def run(context: AgentContext) -> ToolResult:
    start = time.monotonic()

    try:
        # Extract inputs the unified service expects
        github_url = context.verification_data.get("githubUrl")
        linkedin_url = context.verification_data.get("linkedinUrl")

        github_username = None
        if github_url:
            github_username = github_url.rstrip("/").split("/")[-1]

        # Build profile_data for web search verification
        profile_data = context.verification_data.get("personal_info")

        # Retrieve parsed_resume from verification_data if available
        parsed_resume = context.verification_data.get("parsed") or context.verification_data

        result = await unified_verification_service.run_unified_verification(
            candidate_id=context.candidate_id,
            github_username=github_username,
            linkedin_url=linkedin_url,
            profile_data=profile_data,
            parsed_resume=parsed_resume,
        )

        # Convert Pydantic model to dict for ToolResult.data
        result_data = result.dict() if hasattr(result, "dict") else result

        elapsed = int((time.monotonic() - start) * 1000)
        return ToolResult(
            tool="verification",
            status="completed",
            data=result_data,
            reason=None,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("verification_tool failed: %s", e)
        return ToolResult(
            tool="verification",
            status="error",
            data=None,
            reason=str(e),
            duration_ms=elapsed,
        )
