"""
Enterprise GitHub Verification — LLM Escalation Provider
Strictly limited use: only when 0.75 ≤ codeSimilarity < 0.90.

Guard rails:
  - Hard timeout of LLM_TIMEOUT_SECONDS (15s)
  - Temperature = 0.0 (deterministic)
  - Input truncated at LLM_MAX_INPUT_CHARS (4000)
  - If LLM fails → return None (pipeline continues without it)
  - Primary: Gemini;  Fallback: Groq

Output:
  {"verdict": str, "reasoning": str, "confidence": float}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from ..config import (
    CODE_SIMILARITY_SUSPICIOUS,
    CODE_SIMILARITY_COPIED,
    LLM_MAX_INPUT_CHARS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Prompt template
# ═══════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are a code plagiarism expert. Analyse the two repositories and determine whether the candidate's code is original.

Return ONLY valid JSON with exactly these fields:
{
  "verdict": "ORIGINAL" | "SUSPICIOUS" | "COPIED",
  "reasoning": "< 3 sentence explanation >",
  "confidence": <float 0–1>
}

Do not include any other text."""

_USER_TEMPLATE = """Candidate repository: {candidate_repo}
{candidate_summary}

Most similar external repository: {reference_repo}
{reference_summary}

Code similarity score: {similarity}
Key overlapping function names: {functions}

Analyse and return JSON."""


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

async def escalate_to_llm(
    candidate_repo: str,
    candidate_summary: str,
    reference_repo: str,
    reference_summary: str,
    similarity: float,
    key_functions: str,
) -> Optional[Dict[str, Any]]:
    """
    Call LLM for code similarity ruling.

    Only used when ``CODE_SIMILARITY_SUSPICIOUS ≤ similarity < CODE_SIMILARITY_COPIED``.
    Returns structured dict ``{"verdict", "reasoning", "confidence"}`` or ``None``.

    Hard timeout: LLM_TIMEOUT_SECONDS.
    If LLM fails for any reason → returns None (pipeline continues).
    """
    # Guard: only escalate within the band
    if similarity < CODE_SIMILARITY_SUSPICIOUS or similarity >= CODE_SIMILARITY_COPIED:
        return None

    # Truncate inputs
    candidate_summary = candidate_summary[:LLM_MAX_INPUT_CHARS]
    reference_summary = reference_summary[:LLM_MAX_INPUT_CHARS]

    user_message = _USER_TEMPLATE.format(
        candidate_repo=candidate_repo,
        candidate_summary=candidate_summary,
        reference_repo=reference_repo,
        reference_summary=reference_summary,
        similarity=round(similarity, 4),
        functions=key_functions,
    )

    try:
        result = await asyncio.wait_for(
            _call_llm(user_message),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("LLM escalation timed out after %ds", LLM_TIMEOUT_SECONDS)
        return None
    except Exception as exc:
        logger.warning("LLM escalation failed: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════════
# Internal: provider logic (Gemini primary → Groq fallback)
# ═══════════════════════════════════════════════════════════════════

async def _call_llm(user_message: str) -> Optional[Dict[str, Any]]:
    """Try Gemini first, then Groq.  Return parsed JSON dict or None."""

    # ── Try Gemini ──
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        result = await _call_gemini(gemini_key, user_message)
        if result is not None:
            return result

    # ── Fallback: Groq ──
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        result = await _call_groq(groq_key, user_message)
        if result is not None:
            return result

    logger.warning("No LLM provider available — escalation skipped")
    return None


async def _call_gemini(api_key: str, user_message: str) -> Optional[Dict[str, Any]]:
    """Call Gemini via REST (httpx)."""
    import httpx

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": _SYSTEM_PROMPT + "\n\n" + user_message}]}
        ],
        "generationConfig": {
            "temperature": LLM_TEMPERATURE,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json=payload,
                params={"key": api_key},
            )
        if resp.status_code != 200:
            logger.warning("Gemini HTTP %d", resp.status_code)
            return None

        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return _parse_json(text)
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        return None


async def _call_groq(api_key: str, user_message: str) -> Optional[Dict[str, Any]]:
    """Call Groq via REST (httpx)."""
    import httpx

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": LLM_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code != 200:
            logger.warning("Groq HTTP %d", resp.status_code)
            return None

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_json(text)
    except Exception as exc:
        logger.warning("Groq call failed: %s", exc)
        return None


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Parse LLM output into structured dict.  Lenient."""
    try:
        # Strip markdown fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "verdict" in parsed:
            return {
                "verdict": str(parsed.get("verdict", "ORIGINAL")),
                "reasoning": str(parsed.get("reasoning", "")),
                "confidence": float(parsed.get("confidence", 0.5)),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    return None
