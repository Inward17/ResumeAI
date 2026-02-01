from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Union
from app.services.verifier import verify_profile


router = APIRouter(prefix="/verify-profile-data", tags=["verification"])


class VerificationRequest(BaseModel):
    data: Union[dict, list[dict]]


@router.post("")
async def verify_profile_data(req: VerificationRequest):
    """Verify LinkedIn profile data"""
    try:
        profiles = req.data if isinstance(req.data, list) else [req.data]
        results = []
        for profile in profiles:
            result = await verify_profile(profile)
            results.append(result)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))