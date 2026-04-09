"""
LLM Planner — Section 6.6

Called only for signals that remain undecided after the rule engine
and scoring engine.  Receives a minimal context payload (no raw
resume text, no full embeddings — only signal scores and job
requirements) to keep token usage low and latency acceptable.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

from pydantic import ValidationError

from app.models.agent_models import AgentContext, VerificationPlan
from app.agent.config.agent_config import TOOL_REGISTRY, LLM_RETRIES

logger = logging.getLogger(__name__)

# ── Load prompt template once at import time ────────────────────────────
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planning.txt"
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    PLANNING_PROMPT_TEMPLATE = _f.read()


# ── Prompt builder ──────────────────────────────────────────────────────
def build_planning_prompt(
    undecided: List[str],
    scores: Dict[str, float],
    context: AgentContext,
) -> str:
    """
    Fill the planning.txt template with the minimal context the
    LLM needs to decide 'verify' or 'skip' for each undecided signal.
    """
    return PLANNING_PROMPT_TEMPLATE.format(
        undecided_signals = undecided,
        scores            = scores,
        job_title         = context.job.get("job_title", ""),
        required_skills   = context.job.get("required_skills", []),
        preferred_skills  = context.job.get("preferred_skills", []),
        history           = context.history,
    )


# ── Gemini call wrapper ────────────────────────────────────────────────
async def _call_gemini(prompt: str) -> str:
    """
    Call Google Gemini to generate a verification plan.
    Uses the google-genai SDK with the GEMINI_API_KEY from env.
    """
    import google.genai as genai

    api_key = os.environ.get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


# ── Public API ──────────────────────────────────────────────────────────
async def call_planner(
    undecided: List[str],
    scores: Dict[str, float],
    context: AgentContext,
) -> VerificationPlan:
    """
    Build a prompt, call Gemini, validate the response, and return a
    VerificationPlan.  Falls back to 'verify all undecided' on any
    parse or validation error (after retries).
    """
    prompt = build_planning_prompt(undecided, scores, context)
    known_tools = set(TOOL_REGISTRY.keys())

    last_error: Exception | None = None

    for attempt in range(1, LLM_RETRIES + 1):
        try:
            raw = await _call_gemini(prompt)

            # Strip markdown code fences if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)
            plan = VerificationPlan(
                actions   = parsed.get("actions", []),
                skip      = parsed.get("skip", []),
                reasoning = parsed.get("reasoning", {}),
                source    = "llm",
            )

            # Validate: no unknown tool names
            for action in plan.actions:
                if action not in known_tools:
                    raise ValueError(f"Unknown action: {action}")

            logger.info(
                "Planner succeeded on attempt %d: actions=%s skip=%s",
                attempt, plan.actions, plan.skip,
            )
            return plan

        except (json.JSONDecodeError, ValidationError, ValueError, KeyError) as e:
            last_error = e
            logger.warning(
                "Planner attempt %d/%d failed: %s", attempt, LLM_RETRIES, e
            )
        except Exception as e:
            last_error = e
            logger.error(
                "Planner attempt %d/%d unexpected error: %s", attempt, LLM_RETRIES, e
            )

    # ── Fallback: verify all undecided signals ──────────────────────
    logger.error(
        "Planner output invalid after %d retries: %s. "
        "Falling back to verify all undecided.",
        LLM_RETRIES, last_error,
    )
    return VerificationPlan(
        actions   = list(undecided),
        skip      = [],
        reasoning = {"fallback": str(last_error)},
        source    = "llm_fallback",
    )
