"""
Unified Verification Routes - read a candidate's stored verification result.
Verification itself runs inside the upload pipeline.
"""
from fastapi import APIRouter, Depends
from app.auth import AuthUser, get_current_user, require_candidate_access
from pydantic import BaseModel

router = APIRouter(prefix="/verification", tags=["unified-verification"])


class VerificationStatusRequest(BaseModel):
    """Request to check verification status"""
    candidate_id: str


@router.post("/verification-status")
async def get_verification_status(request: VerificationStatusRequest, user: AuthUser = Depends(get_current_user)):
    """
    Check verification status for a candidate
    
    - **candidate_id**: Unique candidate identifier
    
    Returns verification status and data if available.
    """
    from app.database import db
    
    await require_candidate_access(request.candidate_id, user)
    
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


@router.get("/verification-status/{candidate_id}", dependencies=[Depends(require_candidate_access)])
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
