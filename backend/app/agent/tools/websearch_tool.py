"""
Web Search Tool Wrapper — Section 6.8

Thin async adapter that extracts company and institution entities
from the candidate's experience and education in AgentContext,
calls the existing search.py / verifier.py, and normalises the
output into a ToolResult.
"""

import time
import logging

from app.models.agent_models import AgentContext, ToolResult
from app.services.verifier import verify_profile

logger = logging.getLogger(__name__)


async def run(context: AgentContext) -> ToolResult:
    start = time.monotonic()

    # Build a profile_data dict from verification_data for the verifier
    personal_info = context.verification_data.get("personal_info", {})

    # Extract entities from education and experience
    educations = context.verification_data.get("education", []) or []
    experiences = context.verification_data.get("experience", []) or []

    # Also check nested structures that the scraper format uses
    if not educations:
        educations = personal_info.get("education", []) or []
    if not experiences:
        experiences = personal_info.get("experience", []) or []

    # Normalise: parser returns plain strings; verifier.py expects dicts with
    # 'title'/'subtitle' keys. Convert strings to dicts gracefully.
    def _to_dict_list(items):
        result = []
        for item in items:
            if isinstance(item, str) and item.strip():
                result.append({"title": item.strip()})
            elif isinstance(item, dict):
                result.append(item)
        return result

    edu_dicts = _to_dict_list(educations)
    exp_dicts = _to_dict_list(experiences)

    if not edu_dicts and not exp_dicts:
        return ToolResult(
            tool="web_search", status="skipped", data=None,
            reason="no_entities_to_verify", duration_ms=0,
        )

    try:
        # Build the profile data dict expected by verify_profile / extract_entities()
        # verifier.extract_entities() expects keys: "educations" and "experiences"
        profile_data = {
            "educations": edu_dicts,
            "experiences": exp_dicts,
        }

        result = await verify_profile(profile_data)

        elapsed = int((time.monotonic() - start) * 1000)
        return ToolResult(
            tool="web_search",
            status="completed",
            data=result,
            reason=None,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("websearch_tool failed: %s", e)
        return ToolResult(
            tool="web_search",
            status="error",
            data=None,
            reason=str(e),
            duration_ms=elapsed,
        )
