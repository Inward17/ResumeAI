"""
GitHub Routes - API entry point for GitHub analysis (Phase-1 + Phase-2)
"""
import os
import re
from typing import Dict, Optional, List
from ..services.github_client import GitHubClient
from ..services.repo_analyzer import RepoAnalyzer
from ..services.readme_analyzer import ReadmeAnalyzer
from ..services.score_engine import ScoreEngine
from ..persistence.github_writer import GitHubWriter

# Phase-2 imports (optional - only if dependencies installed)
try:
    from ..ml.pipelines.project_repo_matching import ProjectRepoMatching
    from ..services.deep_repo_analyzer import DeepRepoAnalyzer
    from ..persistence.clone_verdict_writer import CloneVerdictWriter
    from ..utils.repo_filter_utils import apply_quality_filters, get_top_repos
    from ..ml.config.ml_config import (
        ENABLE_PROJECT_MATCHING,
        DEEP_ANALYZE_MATCHED_REPOS_ONLY,
        MAX_DEEP_ANALYZED_REPOS
    )
    PHASE_2_AVAILABLE = True
except ImportError:
    PHASE_2_AVAILABLE = False
    ENABLE_PROJECT_MATCHING = False
    DEEP_ANALYZE_MATCHED_REPOS_ONLY = False


class GitHubAnalysisService:
    """
    Main service orchestrating GitHub ownership analysis
    Supports both Phase-1 (basic) and Phase-2 (deep analysis with AI)
    """
    
    def __init__(self, github_token: Optional[str] = None, db_client=None):
        """
        Initialize the analysis service
        
        Args:
            github_token: GitHub personal access token (if None, reads from GITHUB_TOKEN env var)
            db_client: Database client for persistence
        """
        # Automatically get token from environment if not provided
        if github_token is None:
            github_token = os.getenv("GITHUB_TOKEN")
        
        # Phase-1 components (always available)
        self.github_client = GitHubClient(github_token)
        self.repo_analyzer = RepoAnalyzer(self.github_client)
        self.readme_analyzer = ReadmeAnalyzer(self.github_client)
        self.score_engine = ScoreEngine()
        self.writer = GitHubWriter(db_client)
        
        # Phase-2 components (only if dependencies installed)
        if PHASE_2_AVAILABLE:
            self.project_matcher = ProjectRepoMatching()
            self.deep_analyzer = DeepRepoAnalyzer(self.github_client)
            self.clone_writer = CloneVerdictWriter(db_client)
        else:
            self.project_matcher = None
            self.deep_analyzer = None
            self.clone_writer = None
    
    @staticmethod
    def extract_username_from_url(github_url: str) -> str:
        """
        Extract GitHub username from a GitHub URL or return username as-is
        
        Supports formats:
        - https://github.com/username
        - https://github.com/username/
        - github.com/username
        - username (returns as-is)
        
        Args:
            github_url: GitHub URL or username
            
        Returns:
            Extracted username
            
        Raises:
            ValueError: If URL format is invalid
        """
        # If it doesn't contain github.com, assume it's already a username
        if 'github.com' not in github_url.lower():
            return github_url.strip()
        
        # Extract username from various GitHub URL formats
        patterns = [
            r'github\.com/([^/\s]+)',  # https://github.com/username or github.com/username
            r'github\.com/([^/\s]+)/',  # https://github.com/username/
        ]
        
        for pattern in patterns:
            match = re.search(pattern, github_url, re.IGNORECASE)
            if match:
                username = match.group(1)
                # Filter out common GitHub paths that aren't usernames
                if username.lower() not in ['explore', 'topics', 'trending', 'collections', 'events', 'marketplace', 'pricing', 'nonprofit', 'customer-stories', 'security', 'features', 'enterprise']:
                    return username
        
        raise ValueError(f"Could not extract username from GitHub URL: {github_url}")
    
    def analyze_github_profile(
        self, 
        github_input: str, 
        user_id: Optional[str] = None,
        resume_projects: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Complete GitHub profile analysis pipeline (Phase-1 + Phase-2)
        
        Args:
            github_input: GitHub URL (https://github.com/username) or username directly
            user_id: Optional user ID for persistence
            resume_projects: Optional list of resume projects for matching (Phase-2)
                            Format: [{"name": "...", "description": "...", "technologies": [...]}]
            
        Returns:
            Complete analysis results including score, red flags, and deep analysis
        """
        try:
            # Extract username from URL or use as-is if it's already a username
            username = self.extract_username_from_url(github_input)
            
            # ========== PHASE-1: BASIC ANALYSIS ==========
            
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
            
            # ========== PHASE-2: DEEP ANALYSIS (OPTIONAL) ==========
            
            deep_analysis_results = None
            matched_projects = []
            
            if (PHASE_2_AVAILABLE and 
                resume_projects and 
                ENABLE_PROJECT_MATCHING and 
                self.project_matcher and 
                self.deep_analyzer):
                
                # Match resume projects to repositories
                matched_projects = self.project_matcher.match_projects_to_repos(
                    projects=resume_projects,
                    repositories=readme_analysis["enhancedRepositories"]
                )
                
                # Deep analyze matched repos only
                if matched_projects and DEEP_ANALYZE_MATCHED_REPOS_ONLY:
                    # Pre-filter: remove trivial/low-quality repos before expensive deep analysis
                    # Extract repository data from matched projects
                    matched_repo_data = [
                        m.get("repository", m) for m in matched_projects
                    ]
                    
                    # Apply quality filters (remove trivial, low-commit, no-README repos)
                    filtered_repos = apply_quality_filters(matched_repo_data)
                    
                    # Get top N repos by commit count
                    repos_to_analyze = get_top_repos(
                        filtered_repos, 
                        limit=MAX_DEEP_ANALYZED_REPOS,
                        sort_by="commit_count"
                    )
                    
                    deep_analysis_results = self.deep_analyzer.deep_analyze_matched_repos(
                        matched_repos=repos_to_analyze,
                        all_repo_data=readme_analysis["enhancedRepositories"]
                    )
                    
                    # Apply clone penalties to score
                    total_clone_penalty = sum(
                        r.get("clone_penalty", 0) 
                        for r in deep_analysis_results
                    )
                    
                    # Update score with clone penalties
                    score_result["score"] = max(
                        0, 
                        score_result["score"] - total_clone_penalty
                    )
                    
                    # Add deep red flags
                    for deep_result in deep_analysis_results:
                        score_result["redFlags"].extend(
                            deep_result.get("deep_red_flags", [])
                        )
                    
                    # Persist Phase-2 deep analysis (if user_id provided)
                    if user_id and self.clone_writer:
                        self.clone_writer.write_deep_analysis(
                            user_id=user_id,
                            username=username,
                            deep_results=deep_analysis_results,
                            clone_penalty=total_clone_penalty  # ✅ CORRECT: Use total_clone_penalty, NOT score_result["components"]["penalty"]
                        )
            
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
            result = {
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
            
            # Add Phase-2 results if available
            if matched_projects or deep_analysis_results:
                result["phase2"] = {
                    "enabled": True,
                    "matched_projects": matched_projects,
                    "deep_analysis": deep_analysis_results
                }
            
            return result
            
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
    
    def is_phase2_enabled(self) -> bool:
        """
        Check if Phase-2 (deep analysis) is available
        
        Returns:
            True if Phase-2 dependencies are installed
        """
        return PHASE_2_AVAILABLE


# Example FastAPI integration:
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/github", tags=["github"])

class AnalyzeRequest(BaseModel):
    github_url: str  # Can be URL like "https://github.com/octocat" or username "octocat"
    user_id: Optional[str] = None
    resume_projects: Optional[List[Dict]] = None  # Phase-2: for project matching

# Service automatically gets token from GITHUB_TOKEN environment variable
github_service = GitHubAnalysisService(db_client=get_database_client())

@router.post("/analyze")
async def analyze_github(request: AnalyzeRequest):
    result = github_service.analyze_github_profile(
        github_input=request.github_url,
        user_id=request.user_id,
        resume_projects=request.resume_projects  # Phase-2
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("/rate-limit")
async def get_rate_limit():
    return github_service.get_rate_limit_status()

@router.get("/phase2-status")
async def phase2_status():
    return {"phase2_enabled": github_service.is_phase2_enabled()}
"""