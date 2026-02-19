from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.linkedinScraper import scrape_linkedin_profiles


router = APIRouter(prefix="/scrape-linkedin", tags=["linkedin"])


class LinkedInRequest(BaseModel):
    profileUrls: list[str]


@router.post("")
async def scrape_linkedin(req: LinkedInRequest):
    """Scrape LinkedIn profiles"""
    try:
        result = await scrape_linkedin_profiles(req.profileUrls)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))