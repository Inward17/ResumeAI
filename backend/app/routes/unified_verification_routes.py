"""
Unified Verification Routes - API endpoints for running unified verification
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.unified_verification import unified_verification_service


router = APIRouter(prefix="/verification", tags=["unified-verification"])


class UnifiedVerificationRequest(BaseModel):
    """Request model for unified verification"""
    candidate_id: str
    github_username: Optional[str] = None
    linkedin_url: Optional[str] = None
    profile_data: Optional[dict] = None


class VerificationStatusRequest(BaseModel):
    """Request to check verification status"""
    candidate_id: str


@router.post("/verify-candidate")
async def verify_candidate(request: UnifiedVerificationRequest):
    """
    Run unified verification for a candidate (sync - waits for completion)
    
    - **candidate_id**: Unique candidate identifier (links to candidates collection)
    - **github_username**: GitHub username to verify (optional)
    - **linkedin_url**: LinkedIn profile URL to scrape (optional)
    - **profile_data**: Parsed profile data for web verification (optional)
    
    Returns the complete verification data including all sources.
    """
    if not request.candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")
    
    if not any([request.github_username, request.linkedin_url, request.profile_data]):
        raise HTTPException(
            status_code=400, 
            detail="At least one verification source is required (github_username, linkedin_url, or profile_data)"
        )
    
    try:
        result = await unified_verification_service.run_unified_verification(
            candidate_id=request.candidate_id,
            github_username=request.github_username,
            linkedin_url=request.linkedin_url,
            profile_data=request.profile_data
        )
        
        return {
            "status": "success",
            "candidateId": result.candidateId,
            "verificationStatus": result.verificationStatus.model_dump(),
            "matchScore": result.matchScore.model_dump() if result.matchScore else None,
            "githubData": result.githubData.model_dump() if result.githubData else None,
            "linkedinData": result.linkedinData.model_dump() if result.linkedinData else None,
            "webSearchData": result.webSearchData.model_dump() if result.webSearchData else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/verify-candidate-async")
async def verify_candidate_async(
    request: UnifiedVerificationRequest,
    background_tasks: BackgroundTasks
):
    """
    Start unified verification as a background task (returns immediately)
    
    - **candidate_id**: Unique candidate identifier
    - Other fields same as /verify-candidate
    
    Returns task status immediately. Poll /verification-status to check completion.
    """
    if not request.candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")
    
    if not any([request.github_username, request.linkedin_url, request.profile_data]):
        raise HTTPException(
            status_code=400, 
            detail="At least one verification source is required"
        )
    
    # Queue background verification
    background_tasks.add_task(
        _run_verification_background,
        request.candidate_id,
        request.github_username,
        request.linkedin_url,
        request.profile_data
    )
    
    return {
        "status": "queued",
        "candidateId": request.candidate_id,
        "message": "Verification started. Poll /verification-status to check progress."
    }


async def _run_verification_background(
    candidate_id: str,
    github_username: Optional[str],
    linkedin_url: Optional[str],
    profile_data: Optional[dict]
):
    """Background task wrapper for verification"""
    try:
        await unified_verification_service.run_unified_verification(
            candidate_id=candidate_id,
            github_username=github_username,
            linkedin_url=linkedin_url,
            profile_data=profile_data
        )
    except Exception as e:
        print(f"Background verification failed for {candidate_id}: {e}")


@router.post("/verification-status")
async def get_verification_status(request: VerificationStatusRequest):
    """
    Check verification status for a candidate
    
    - **candidate_id**: Unique candidate identifier
    
    Returns verification status and data if available.
    """
    from app.database import db
    
    result = await db.verification_data.find_one(
        {"candidateId": request.candidate_id}
    )
    
    if not result:
        return {
            "status": "not_found",
            "candidateId": request.candidate_id,
            "message": "No verification data found"
        }
    
    # Remove MongoDB _id from response
    result.pop("_id", None)
    
    return {
        "status": "found",
        "data": result
    }


@router.get("/verification-status/{candidate_id}")
async def get_verification_status_get(candidate_id: str):
    """GET endpoint for verification status (for easy testing)"""
    from app.database import db
    
    result = await db.verification_data.find_one(
        {"candidateId": candidate_id}
    )
    
    if not result:
        return {
            "status": "not_found",
            "candidateId": candidate_id,
            "message": "No verification data found"
        }
    
    result.pop("_id", None)
    
    return {
        "status": "found",
        "data": result
    }
