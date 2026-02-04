"""
Deep Repo Analyzer - Phase-2 Deep Analysis for Matched Repos
Combines branch-aware commits, clone detection, and enhanced signals
"""
from typing import Dict, List, Optional
from .github_client import GitHubClient
from .popular_repo_fetcher import PopularRepoFetcher
from ..ml.pipelines.readme_clone_detection import ReadmeCloneDetection
from ..ml.config.ml_config import (
    ENABLE_README_CLONE_DETECTION,
    ENABLE_BRANCH_AWARE_COMMITS,
    MAX_DEEP_ANALYSIS_REPOS
)
from ..utils.date_utils import analyze_commit_spread
from ..utils.branch_utils import aggregate_branch_commits, analyze_branch_strategy


class DeepRepoAnalyzer:
    """Deep analysis for matched repositories"""
    
    def __init__(self, github_client: GitHubClient):
        """Initialize deep analyzer"""
        self.client = github_client
        self.popular_fetcher = PopularRepoFetcher(github_client)
        self.clone_detector = ReadmeCloneDetection()
    
    def analyze_repo_deep(
        self, 
        owner: str, 
        repo_name: str, 
        username: str,
        readme_text: Optional[str] = None
    ) -> Dict:
        """
        Perform deep analysis on a single repository
        
        Returns clone detection and branch stats
        """
        result = {
            "repo_name": repo_name,
            "owner": owner,
            "commit_stats": {},
            "clone_detection": {},
            "red_flags": []
        }
        
        # 1. Branch-aware commit analysis
        if ENABLE_BRANCH_AWARE_COMMITS:
            commits = self.client.get_repo_commits(
                owner, repo_name, username, all_branches=True
            )
            
            # Assuming client returns flat list for all_branches=True currently
            # To leverage branch_utils properly, we would need per-branch commits.
            # For now, we simulate the structure to use the utility:
            
            # Group commits by branch (simulated or real if client supported it)
            # Since get_repo_commits returns a flat list of unique commits when all_branches=True,
            # we can analyze the spread directly but we'll use the strategy analyzer for metadata
            
            commit_dates = [
                c["commit"]["author"]["date"] 
                for c in commits if "commit" in c
            ]
            
            spread = analyze_commit_spread(commit_dates)
            
            result["commit_stats"] = {
                "total_commits": len(commits),
                "unique_days": spread["unique_days"],
                "is_dump_pattern": spread["is_dump_pattern"],
                "date_range_days": spread.get("date_range_days", 0),
                "branch_strategy": "single_branch" # Placeholder until client supports granular branch fetching
            }
        
        # 2. README clone detection
        if ENABLE_README_CLONE_DETECTION:
            if readme_text is None:
                readme_text = self.client.get_repo_readme(owner, repo_name)
            
            if readme_text and len(readme_text) >= 100:
                popular_repos = self.popular_fetcher.fetch_similar_repos(repo_name)
                clone_result = self.clone_detector.detect_clone(
                    readme_text, popular_repos
                )
                
                result["clone_detection"] = clone_result
                result["red_flags"].extend(clone_result.get("red_flags", []))
            else:
                result["clone_detection"] = {
                    "similarity": 0.0,
                    "verdict": "UNKNOWN",
                    "matched_repo": None,
                    "red_flags": []
                }
        
        return result
    
    def analyze_repos_deep(
        self, repos: List[Dict], username: str, limit: int = None
    ) -> List[Dict]:
        """Perform deep analysis on multiple repositories"""
        if limit is None:
            limit = MAX_DEEP_ANALYSIS_REPOS
        
        results = []
        
        for repo in repos[:limit]:
            owner = repo.get("owner")
            repo_name = repo.get("name")
            readme = repo.get("readme")
            
            try:
                deep_result = self.analyze_repo_deep(
                    owner, repo_name, username, readme_text=readme
                )
                results.append(deep_result)
            except Exception as e:
                results.append({
                    "repo_name": repo_name,
                    "error": str(e),
                    "red_flags": ["Deep analysis failed"]
                })
        
        return results
    
    def get_clone_penalty(self, deep_results: List[Dict]) -> int:
        """Calculate total penalty from clone detection"""
        from ..ml.inference.similarity_engine import SimilarityEngine
        
        engine = SimilarityEngine()
        total_penalty = 0
        
        for result in deep_results:
            clone_detection = result.get("clone_detection", {})
            similarity = clone_detection.get("similarity", 0.0)
            penalty = engine.get_penalty(similarity)
            total_penalty += penalty
        
        return total_penalty