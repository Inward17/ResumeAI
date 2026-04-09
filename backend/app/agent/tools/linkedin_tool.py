"""
LinkedIn Tool Wrapper — Section 6.8

Thin async adapter that extracts the LinkedIn URL from AgentContext,
calls the existing linkedinScraper.scrape_linkedin_profiles, and
normalises the output into a ToolResult.
"""

import time
import logging

from app.models.agent_models import AgentContext, ToolResult
from app.services.linkedinScraper import scrape_linkedin_profiles

logger = logging.getLogger(__name__)


async def run(context: AgentContext) -> ToolResult:
    start = time.monotonic()
    personal_info = context.verification_data.get("personal_info", {})
    linkedin_url = personal_info.get("linkedin") or context.verification_data.get("linkedinUrl")

    # Normalise URL: parser may extract partial URLs like "linkedin.com/in/name"
    # Apify scraper requires a fully qualified URL with scheme
    if linkedin_url:
        linkedin_url = linkedin_url.strip()
        if linkedin_url.startswith("in/"):
            linkedin_url = f"https://www.linkedin.com/{linkedin_url}"
        elif linkedin_url.startswith("linkedin.com"):
            linkedin_url = f"https://www.{linkedin_url}"
        elif linkedin_url.startswith("www.linkedin.com"):
            linkedin_url = f"https://{linkedin_url}"
        elif not linkedin_url.startswith("http"):
            # Could be just a username/slug like "john-doe-123"
            linkedin_url = f"https://www.linkedin.com/in/{linkedin_url}"
        # Clean up any trailing slashes for consistency
        linkedin_url = linkedin_url.rstrip("/")

    logger.debug("linkedin_tool: normalized URL = %s", linkedin_url)

    if not linkedin_url:
        return ToolResult(
            tool="linkedin", status="skipped", data=None,
            reason="no_linkedin_url", duration_ms=0,
        )

    try:
        result = await scrape_linkedin_profiles([linkedin_url])

        elapsed = int((time.monotonic() - start) * 1000)

        # Extract the first profile from the result list
        profile_data = None
        if result.get("status") == "success" and result.get("data"):
            profile_data = result["data"][0] if result["data"] else None

        return ToolResult(
            tool="linkedin",
            status="completed",
            data=profile_data,
            reason=None,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.error("linkedin_tool failed: %s", e)
        return ToolResult(
            tool="linkedin",
            status="error",
            data=None,
            reason=str(e),
            duration_ms=elapsed,
        )
