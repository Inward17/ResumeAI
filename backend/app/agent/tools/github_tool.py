"""
GitHub Tool Wrapper — Section 6.8

Thin async adapter that extracts the GitHub URL from AgentContext,
calls the existing github_services_v2.verify_github, and normalises
the output into a ToolResult.
"""

import time
import logging

from app.models.agent_models import AgentContext, ToolResult
from app.services.github_services_v2 import verify_github

logger = logging.getLogger(__name__)


async def run(context: AgentContext) -> ToolResult:
    start = time.monotonic()
    personal_info = context.verification_data.get("personal_info", {})
    github_url = personal_info.get("github") or context.verification_data.get("githubUrl")
    print(f"[AGENT-GH] github_url={github_url}, personal_info.github={personal_info.get('github')}, top-level githubUrl={context.verification_data.get('githubUrl')}")

    if not github_url:
        print(f"[AGENT-GH] SKIPPED — no github URL found in verification_data")
        return ToolResult(
            tool="github", status="skipped", data=None,
            reason="no_github_url", duration_ms=0,
        )

    try:
        # Extract username from URL (e.g. "https://github.com/johndoe" → "johndoe")
        username = github_url.rstrip("/").split("/")[-1]

        # Build a minimal parsed_resume dict for verify_github
        parsed_resume = {
            "github_username": username,
        }
        # Attach projects from verification_data if available
        candidate_info = context.verification_data.get("personal_info", {})
        if context.verification_data.get("projects"):
            parsed_resume["projects"] = context.verification_data["projects"]

        print(f"[AGENT-GH] Calling verify_github for username={username}")
        result = await verify_github(
            candidate_id=context.candidate_id,
            parsed_resume=parsed_resume,
        )

        # Convert result to a serialisable dict
        result_data = result.to_mongo_dict() if hasattr(result, "to_mongo_dict") else result

        elapsed = int((time.monotonic() - start) * 1000)
        score = result_data.get('score100', result_data.get('score', 0)) if isinstance(result_data, dict) else 0
        print(f"[AGENT-GH] COMPLETED in {elapsed}ms — success={result_data.get('success') if isinstance(result_data, dict) else '?'}, score={score}")
        return ToolResult(
            tool="github",
            status="completed",
            data=result_data,
            reason=None,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        print(f"[AGENT-GH] EXCEPTION after {elapsed}ms: {e}")
        logger.error("github_tool failed: %s", e)
        return ToolResult(
            tool="github",
            status="error",
            data=None,
            reason=str(e),
            duration_ms=elapsed,
        )
