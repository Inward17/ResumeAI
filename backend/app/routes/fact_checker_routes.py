"""
Fact Checker Routes — API endpoint for AI-powered claim verification.
Used by the FactCheckerBot frontend component during live interviews.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthUser, get_current_user, require_candidate_access
from app.org import ensure_org
from app.services.quota import rate_limit, use_quota
from pydantic import BaseModel

from app.services.fact_checker_service import AIServiceUnavailable, fact_check

router = APIRouter(prefix="/fact-checker", tags=["fact-checker"])


class FactCheckRequest(BaseModel):
    """Request body for the fact-check endpoint."""
    message: str
    candidate_name: str = "the candidate"


@router.post("/{candidate_id}", dependencies=[Depends(require_candidate_access)])
async def check_fact(candidate_id: str, body: FactCheckRequest, user: AuthUser = Depends(get_current_user)):
    """
    Run the AI Fact Checker for a candidate.

    The service classifies the interviewer's prompt into one of 4 conditions
    and returns a verification response:
      1. general_qa — Follow-up questions / general discussion.
      2. verify_tech — Tech stack claim verification.
      3. verify_project — Project existence verification.
      4. verify_authenticity — Project ownership / originality check.
    """
    rate_limit(user.uid, "ai")
    await use_quota(await ensure_org(user), "ai_call")
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    try:
        result = await fact_check(
            candidate_id=candidate_id,
            user_message=body.message.strip(),
            candidate_name=body.candidate_name,
        )
    except AIServiceUnavailable:
        raise HTTPException(503, "The AI service is down, so the fact checker can't answer right now. Try again later.")

    return {
        "status": "success",
        "response": result["response"],
        "condition": result["condition"],
        "extracted_query": result["extracted_query"],
    }
