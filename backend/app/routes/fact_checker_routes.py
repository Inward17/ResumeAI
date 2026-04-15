"""
Fact Checker Routes — API endpoint for AI-powered claim verification.
Used by the FactCheckerBot frontend component during live interviews.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.fact_checker_service import fact_check

router = APIRouter(prefix="/fact-checker", tags=["fact-checker"])


class FactCheckRequest(BaseModel):
    """Request body for the fact-check endpoint."""
    message: str
    candidate_name: str = "the candidate"


@router.post("/{candidate_id}")
async def check_fact(candidate_id: str, body: FactCheckRequest):
    """
    Run the AI Fact Checker for a candidate.

    The service classifies the interviewer's prompt into one of 4 conditions
    and returns a verification response:
      1. general_qa — Follow-up questions / general discussion.
      2. verify_tech — Tech stack claim verification.
      3. verify_project — Project existence verification.
      4. verify_authenticity — Project ownership / originality check.
    """
    if not body.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    result = await fact_check(
        candidate_id=candidate_id,
        user_message=body.message.strip(),
        candidate_name=body.candidate_name,
    )

    return {
        "status": "success",
        "response": result["response"],
        "condition": result["condition"],
        "extracted_query": result["extracted_query"],
    }
