"""
FastAPI Integration Example
Complete REST API implementation for GitHub Ownership Score
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import os
from dotenv import load_dotenv

from github.routes.github_routes import GitHubAnalysisService

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="GitHub Ownership Score API",
    description="Analyze GitHub profiles and compute ownership scores",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service (singleton)
_github_service = None

def get_github_service() -> GitHubAnalysisService:
    """Dependency injection for GitHub service"""
    global _github_service
    if _github_service is None:
        github_token = os.getenv("GITHUB_TOKEN")
        # db_client = get_database_client()  # Initialize your DB client
        _github_service = GitHubAnalysisService(
            github_token=github_token,
            db_client=None  # Pass DB client here
        )
    return _github_service


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class AnalyzeRequest(BaseModel):
    """Request model for GitHub analysis"""
    username: str = Field(..., description="GitHub username to analyze")
    user_id: Optional[str] = Field(None, description="Optional user ID for persistence")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "octocat",
                "user_id": "user_12345"
            }
        }


class ScoreComponents(BaseModel):
    """Score component breakdown"""
    original_ratio: float
    commit_depth: float
    readme_presence: float
    language_match: float
    oss_bonus: float
    penalty: float


class RepositoryStats(BaseModel):
    """Repository statistics"""
    total: int
    original: int
    forked: int
    original_ratio: float


class CommitStats(BaseModel):
    """Commit statistics"""
    total: int
    average_per_repo: float
    repos_with_low_commits: int
    lastCommitDate: str


class ReadmeStats(BaseModel):
    """README statistics"""
    repos_with_readme: int
    repos_without_readme: int
    readme_presence_ratio: float


class AnalyzeResponse(BaseModel):
    """Response model for GitHub analysis"""
    success: bool
    username: str
    score: float = Field(..., description="Overall ownership score (0-100)")
    redFlags: List[str] = Field(default_factory=list, description="List of red flags")
    components: ScoreComponents
    repositoryStats: RepositoryStats
    commitStats: CommitStats
    readmeStats: ReadmeStats
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "username": "octocat",
                "score": 78.5,
                "redFlags": ["Low commit depth"],
                "components": {
                    "original_ratio": 27.0,
                    "commit_depth": 18.5,
                    "readme_presence": 13.5,
                    "language_match": 15.0,
                    "oss_bonus": 10.0,
                    "penalty": 5.0
                },
                "repositoryStats": {
                    "total": 25,
                    "original": 23,
                    "forked": 2,
                    "original_ratio": 0.92
                },
                "commitStats": {
                    "total": 487,
                    "average_per_repo": 19.5,
                    "repos_with_low_commits": 3,
                    "lastCommitDate": "2024-01-15T10:30:00"
                },
                "readmeStats": {
                    "repos_with_readme": 21,
                    "repos_without_readme": 4,
                    "readme_presence_ratio": 0.84
                }
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class RateLimitResponse(BaseModel):
    """Rate limit information"""
    limit: int
    remaining: int
    reset: int
    reset_formatted: str


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "service": "GitHub Ownership Score API",
        "status": "running",
        "version": "1.0.0"
    }


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    tags=["Analysis"],
    summary="Analyze GitHub Profile",
    description="Analyze a GitHub profile and compute ownership score"
)
async def analyze_profile(
    request: AnalyzeRequest,
    service: GitHubAnalysisService = Depends(get_github_service)
):
    """
    Analyze a GitHub profile and return ownership score.
    
    - **username**: GitHub username to analyze
    - **user_id**: Optional user ID for database persistence
    """
    try:
        result = service.analyze_github_profile(
            username=request.username,
            user_id=request.user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Analysis failed")
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post(
    "/batch-analyze",
    tags=["Analysis"],
    summary="Batch Analyze Multiple Profiles",
    description="Analyze multiple GitHub profiles in a single request"
)
async def batch_analyze(
    usernames: List[str] = Field(..., description="List of GitHub usernames"),
    service: GitHubAnalysisService = Depends(get_github_service)
):
    """
    Analyze multiple GitHub profiles.
    
    - **usernames**: List of GitHub usernames to analyze
    """
    results = []
    
    for username in usernames[:10]:  # Limit to 10 to prevent abuse
        try:
            result = service.analyze_github_profile(username)
            results.append(result)
        except Exception as e:
            results.append({
                "success": False,
                "username": username,
                "error": str(e)
            })
    
    return {
        "total": len(results),
        "results": results
    }


@app.get(
    "/rate-limit",
    response_model=RateLimitResponse,
    tags=["Utility"],
    summary="Check Rate Limit",
    description="Check GitHub API rate limit status"
)
async def get_rate_limit(
    service: GitHubAnalysisService = Depends(get_github_service)
):
    """
    Get current GitHub API rate limit status.
    """
    try:
        rate_limit_data = service.get_rate_limit_status()
        
        if not rate_limit_data:
            raise HTTPException(status_code=503, detail="Unable to fetch rate limit")
        
        core = rate_limit_data.get("resources", {}).get("core", {})
        
        from datetime import datetime
        reset_time = datetime.fromtimestamp(core.get("reset", 0))
        
        return {
            "limit": core.get("limit", 0),
            "remaining": core.get("remaining", 0),
            "reset": core.get("reset", 0),
            "reset_formatted": reset_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Check if the service is running and API is accessible"
)
async def health_check(
    service: GitHubAnalysisService = Depends(get_github_service)
):
    """
    Health check endpoint with GitHub API connectivity test.
    """
    try:
        # Test GitHub API connectivity
        rate_limit = service.get_rate_limit_status()
        github_api_healthy = bool(rate_limit)
        
        return {
            "status": "healthy",
            "github_api": "connected" if github_api_healthy else "disconnected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ============================================
# ERROR HANDLERS
# ============================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return {
        "success": False,
        "error": exc.detail,
        "status_code": exc.status_code
    }


# ============================================
# STARTUP/SHUTDOWN
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 GitHub Ownership Score API starting...")
    print(f"   GitHub token configured: {bool(os.getenv('GITHUB_TOKEN'))}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("👋 GitHub Ownership Score API shutting down...")


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "fastapi_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only
        log_level="info"
    )
