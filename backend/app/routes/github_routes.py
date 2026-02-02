"""
GitHub Routes - FastAPI endpoints for GitHub profile analysis
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.github_services import (
    GitHubClient,
    RepoAnalyzer,
    ReadmeAnalyzer,
    ScoreEngine
)
from app.models.github_writer import GitHubWriter
from app.database import db


router = APIRouter(prefix="/github", tags=["github"])


class AnalyzeRequest(BaseModel):
    """Request model for GitHub analysis"""
    username: str
    user_id: Optional[str] = None


class GitHubAnalysisService:
    """Service orchestrating GitHub ownership analysis"""
    
    def __init__(self, github_token: Optional[str] = None, db_client=None):
        self.github_client = GitHubClient(github_token)
        self.repo_analyzer = RepoAnalyzer(self.github_client)
        self.readme_analyzer = ReadmeAnalyzer(self.github_client)
        self.score_engine = ScoreEngine()
        self.writer = GitHubWriter(db_client)
    
    def analyze_github_profile(self, username: str, user_id: Optional[str] = None) -> dict:
        """Complete GitHub profile analysis pipeline"""
        try:
            # Step 1: Fetch repositories
            repos = self.github_client.get_user_repos(username)
            
            if not repos:
                return {
                    "success": False,
                    "error": f"No repositories found for user '{username}'",
                    "score": 0,
                    "redFlags": ["No repositories found"],
                }
            
            # Step 2: Analyze repositories
            repo_analysis = self.repo_analyzer.analyze_repos(username, repos)
            
            # Step 3: Analyze READMEs
            readme_analysis = self.readme_analyzer.analyze_readmes(
                repo_analysis["enrichedRepositories"]
            )
            
            # Step 4: Compute score
            score_result = self.score_engine.compute_score(repo_analysis, readme_analysis)
            
            # Step 5: Persist (if user_id provided)
            github_data = None
            if user_id:
                github_data = self.writer.write_github_data(
                    user_id=user_id,
                    username=username,
                    score_result=score_result,
                    repo_analysis=repo_analysis,
                    readme_analysis=readme_analysis
                )
            
            return {
                "success": True,
                "username": username,
                "score": score_result["score"],
                "redFlags": score_result["redFlags"],
                "components": score_result["components"],
                "breakdown": score_result["breakdown"],
                "repositoryStats": repo_analysis["repositoryStats"],
                "commitStats": repo_analysis["commitStats"],
                "readmeStats": readme_analysis["readmeStats"],
                "githubData": github_data,
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "score": 0,
                "redFlags": ["User not found"],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "score": 0,
                "redFlags": ["Analysis error"],
            }
    
    def get_rate_limit_status(self) -> dict:
        """Check GitHub API rate limit status"""
        return self.github_client.check_rate_limit()


# Initialize service with token from environment
github_service = GitHubAnalysisService(
    github_token=os.getenv("GITHUB_TOKEN"),
    db_client=db
)


@router.post("/analyze")
async def analyze_github(request: AnalyzeRequest):
    """
    Analyze a GitHub profile for ownership verification
    
    - **username**: GitHub username to analyze
    - **user_id**: Optional user ID for persistence
    """
    result = github_service.analyze_github_profile(
        username=request.username,
        user_id=request.user_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/analyze/{username}")
async def analyze_github_get(username: str):
    """
    Analyze a GitHub profile (GET endpoint for quick testing)
    
    - **username**: GitHub username to analyze
    """
    result = github_service.analyze_github_profile(username=username)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/rate-limit")
async def get_rate_limit():
    """Check GitHub API rate limit status"""
    return github_service.get_rate_limit_status()