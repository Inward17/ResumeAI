"""
GitHub Routes - FastAPI endpoints for GitHub profile analysis (V2 – async pipeline)
"""
import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.github_services_v2 import verify_github, GitHubVerificationResult
from app.database import db


router = APIRouter(prefix="/github", tags=["github"])


# ── Request / Response models ────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Request model for GitHub analysis"""
    username: str
    candidate_id: Optional[str] = None
    # Optional resume data — enables project matching + richer analysis
    projects: Optional[List[dict]] = None
    skills: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_github(request: AnalyzeRequest):
    """
    Analyze a GitHub profile using the V2 NLP pipeline.

    **POST body (JSON):**
    ```json
    {
        "username": "octocat",
        "candidate_id": "optional-candidate-id",
        "projects": [
            {
                "name": "My Project",
                "technologies": ["Python", "FastAPI"],
                "description": "A cool web app"
            }
        ],
        "skills": "Python, FastAPI, React"
    }
    ```

    The `projects` and `skills` fields are optional but enable deeper
    resume-to-repo matching and richer analysis.
    """
    # Build the parsed_resume dict expected by verify_github
    parsed_resume = {
        "github_username": request.username,
        "personal_info": {
            "github": f"github.com/{request.username}",
        },
    }
    if request.projects:
        parsed_resume["projects"] = request.projects
    if request.skills:
        parsed_resume["skills"] = request.skills

    candidate_id = request.candidate_id or request.username

    try:
        result: GitHubVerificationResult = await verify_github(
            candidate_id=candidate_id,
            parsed_resume=parsed_resume,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or "GitHub analysis failed",
        )

    return result.to_mongo_dict()


@router.get("/analyze/{username}")
async def analyze_github_get(username: str):
    """
    Quick-test endpoint — analyze a GitHub profile by username (GET).

    No resume data is attached, so project matching will be skipped
    but repo analysis, clone detection, and behavioral analysis still run.
    """
    parsed_resume = {
        "github_username": username,
        "personal_info": {"github": f"github.com/{username}"},
    }

    try:
        result: GitHubVerificationResult = await verify_github(
            candidate_id=username,
            parsed_resume=parsed_resume,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error or "GitHub analysis failed",
        )

    return result.to_mongo_dict()


@router.get("/rate-limit")
async def get_rate_limit():
    """Check GitHub API rate limit status"""
    import httpx

    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.github.com/rate_limit", headers=headers)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"GitHub API error: {resp.status_code}"}