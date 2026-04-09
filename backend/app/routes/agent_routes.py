"""
Agent Routes — Section 5.3 + Section 7 (Dual-Run) + Section 10 (Parity)

Three endpoints for the Agent Layer:

    POST /api/v1/agent/verify           — trigger agent-mode verification
    GET  /api/v1/agent/plan/{cid}       — last generated plan (debug)
    GET  /api/v1/agent/status/{cid}     — current agent loop status
"""

import os
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.database import db, agent_runs_col, verification_data_agent_col
from app.agent.core import agent_loop
from app.services.unified_verification import unified_verification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── Feature flags ───────────────────────────────────────────────────────
def _agent_enabled() -> bool:
    return os.environ.get("USE_AGENT_SYSTEM", "false").lower() == "true"


def _dual_run_enabled() -> bool:
    return os.environ.get("DUAL_RUN", "false").lower() == "true"


# ── Request / response models ──────────────────────────────────────────
class VerifyRequest(BaseModel):
    candidate_id: str
    job_id: str


# ── Helper: run legacy pipeline ────────────────────────────────────────
async def _run_legacy(candidate_id: str, job_id: str) -> dict:
    """Run the existing unified verification pipeline (legacy mode)."""
    # Fetch candidate data from MongoDB for the legacy pipeline
    candidate_doc = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate_doc:
        return {"error": "candidate_not_found"}

    # Field names match the actual candidates collection schema (see resume.py _parse_and_store)
    github_username = candidate_doc.get("github_username")      # stored as username, not URL
    linkedin_url    = candidate_doc.get("linkedin_url")         # full URL already stored
    parsed          = candidate_doc.get("parsed", {}) or {}

    # Build LinkedIn-compatible profile_data for web-search verifier
    profile_data = None
    if parsed:
        profile_data = {
            "publicIdentifier": candidate_id,
            "educations":  [{"title": edu} for edu in (parsed.get("education") or [])],
            "experiences": [{"subtitle": exp if isinstance(exp, str)
                              else exp.get("company", "")}
                            for exp in (parsed.get("experience") or [])],
        }

    result = await unified_verification_service.run_unified_verification(
        candidate_id=candidate_id,
        github_username=github_username,
        linkedin_url=linkedin_url,
        profile_data=profile_data,
        parsed_resume=parsed,
    )

    return result.dict() if hasattr(result, "dict") else result



# ── POST /api/v1/agent/verify ──────────────────────────────────────────
@router.post("/verify")
async def agent_verify(req: VerifyRequest):
    """
    Trigger agent-mode verification for a candidate.

    Behaviour depends on feature flags:
        USE_AGENT_SYSTEM=false  → {"status": "disabled"}
        DUAL_RUN=true           → run both, shadow-write agent, serve legacy
        else                    → run agent only
    """
    if not _agent_enabled():
        return {"status": "disabled"}

    # ── Dual-run mode (Section 7 / 10) ──────────────────────────────
    if _dual_run_enabled():
        legacy_task = _run_legacy(req.candidate_id, req.job_id)
        agent_task = agent_loop.run(req.candidate_id, req.job_id)

        legacy_result, agent_result = await asyncio.gather(
            legacy_task, agent_task, return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(legacy_result, Exception):
            logger.exception("Dual-run legacy path failed: %s", legacy_result)
            raise HTTPException(status_code=500, detail=str(legacy_result))

        if isinstance(agent_result, Exception):
            logger.error("Dual-run agent path failed (non-fatal): %s", agent_result)
            agent_result = {"error": str(agent_result)}

        # Shadow-write agent result to verification_data_agent collection
        try:
            await verification_data_agent_col.update_one(
                {"candidate_id": req.candidate_id},
                {"$set": {
                    "candidate_id": req.candidate_id,
                    "job_id": req.job_id,
                    "agent": agent_result,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.error("Failed to shadow-write agent result: %s", e)

        # Serve legacy result to users during dual-run testing
        return {"status": "success", "mode": "dual_run", "data": legacy_result}

    # ── Agent-only mode ─────────────────────────────────────────────
    try:
        summary = await agent_loop.run(req.candidate_id, req.job_id)
        return {"status": "success", "data": summary}
    except Exception as e:
        logger.exception("Agent verify failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── GET /api/v1/agent/plan/{candidate_id} ──────────────────────────────
@router.get("/plan/{candidate_id}")
async def agent_plan(candidate_id: str):
    """
    Returns the last generated verification plan for a candidate
    (for debugging and observability).  Queries the agent_runs
    collection for the most recent document.
    """
    doc = await agent_runs_col.find_one(
        {"candidate_id": candidate_id},
        sort=[("timestamp", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No agent run found for this candidate")

    doc["_id"] = str(doc["_id"])
    return {"status": "success", "data": doc}


# ── GET /api/v1/agent/status/{candidate_id} ────────────────────────────
@router.get("/status/{candidate_id}")
async def agent_status(candidate_id: str):
    """
    Returns current agent loop status and tool results for a candidate.
    Queries the most recent agent_runs document.
    """
    doc = await agent_runs_col.find_one(
        {"candidate_id": candidate_id},
        sort=[("timestamp", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No agent run found for this candidate")

    doc["_id"] = str(doc["_id"])
    return {
        "status": "success",
        "data": {
            "run_id":          doc.get("run_id"),
            "candidate_id":    doc.get("candidate_id"),
            "job_id":          doc.get("job_id"),
            "plan_source":     doc.get("plan_source"),
            "actions_taken":   doc.get("actions_taken", []),
            "signals_skipped": doc.get("signals_skipped", []),
            "run_duration_ms": doc.get("run_duration_ms"),
            "timestamp":       doc.get("timestamp"),
        },
    }
