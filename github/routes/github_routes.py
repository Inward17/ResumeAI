"""
GitHub Routes - API entry point for GitHub analysis
"""
from typing import Dict, Optional
from ..services.github_client import GitHubClient
from ..services.repo_analyzer import RepoAnalyzer
from ..services.readme_analyzer import ReadmeAnalyzer
from ..services.score_engine import ScoreEngine
from ..persistence.github_writer import GitHubWriter


class GitHubAnalysisService:
    """
    Main service orchestrating GitHub ownership analysis
    This would be integrated into your API framework (FastAPI, Flask, etc.)
    """
    
    def __init__(self, github_token: Optional[str] = None, db_client=None):
        """
        Initialize the analysis service
        
        Args:
            github_token: GitHub personal access token
            db_client: Database client for persistence
        """
        self.github_client = GitHubClient(github_token)
        self.repo_analyzer = RepoAnalyzer(self.github_client)
        self.readme_analyzer = ReadmeAnalyzer(self.github_client)
        self.score_engine = ScoreEngine()
        self.writer = GitHubWriter(db_client)
    
    def analyze_github_profile(self, username: str, user_id: Optional[str] = None) -> Dict:
        """
        Complete GitHub profile analysis pipeline
        
        Args:
            username: GitHub username to analyze
            user_id: Optional user ID for persistence
            
        Returns:
            Complete analysis results including score, red flags, and enriched data
        """
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
            
            # Step 2: Analyze repositories (EASY signals)
            repo_analysis = self.repo_analyzer.analyze_repos(username, repos)
            
            # Step 3: Analyze READMEs and language matching
            readme_analysis = self.readme_analyzer.analyze_readmes(
                repo_analysis["enrichedRepositories"]
            )
            
            # Step 4: Compute score and identify red flags
            score_result = self.score_engine.compute_score(repo_analysis, readme_analysis)
            
            # Step 5: Persist to database (if user_id provided)
            github_data = None
            if user_id:
                github_data = self.writer.write_github_data(
                    user_id=user_id,
                    username=username,
                    score_result=score_result,
                    repo_analysis=repo_analysis,
                    readme_analysis=readme_analysis
                )
            
            # Return complete results
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
            # User not found
            return {
                "success": False,
                "error": str(e),
                "score": 0,
                "redFlags": ["User not found"],
            }
        
        except Exception as e:
            # Other errors
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "score": 0,
                "redFlags": ["Analysis error"],
            }
    
    def get_rate_limit_status(self) -> Dict:
        """
        Check GitHub API rate limit status
        
        Returns:
            Rate limit information
        """
        return self.github_client.check_rate_limit()


# Example FastAPI integration:
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/github", tags=["github"])

class AnalyzeRequest(BaseModel):
    username: str
    user_id: Optional[str] = None

github_service = GitHubAnalysisService(
    github_token=os.getenv("GITHUB_TOKEN"),
    db_client=get_database_client()
)

@router.post("/analyze")
async def analyze_github(request: AnalyzeRequest):
    result = github_service.analyze_github_profile(
        username=request.username,
        user_id=request.user_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("/rate-limit")
async def get_rate_limit():
    return github_service.get_rate_limit_status()
"""