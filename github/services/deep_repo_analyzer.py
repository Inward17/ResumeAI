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
from ..utils.branch_utils import analyze_branch_strategy


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
            # Get branches
            branches = self.client.get_repo_branches(owner, repo_name)
            
            # Get commits (all branches)
            commits = self.client.get_repo_commits(
                owner, repo_name, username, all_branches=True
            )
            
            commit_dates = [
                c["commit"]["author"]["date"] 
                for c in commits if "commit" in c
            ]
            
            spread = analyze_commit_spread(commit_dates)
            
            # Analyze branch strategy
            # Create simple branch_commits structure for strategy analysis
            branch_commits = {}
            for branch in branches[:10]:  # Limit to 10 branches
                branch_name = branch["name"]
                # Get commits for this specific branch
                branch_specific_commits = self.client.get_repo_commits(
                    owner, repo_name, username, 
                    all_branches=False  # Single branch
                )
                branch_commits[branch_name] = branch_specific_commits
            
            strategy = analyze_branch_strategy(branch_commits) if branch_commits else {
                "strategy": "single_branch",
                "num_branches": len(branches)
            }
            
            result["commit_stats"] = {
                "total_commits": len(commits),
                "unique_days": spread["unique_days"],
                "is_dump_pattern": spread["is_dump_pattern"],
                "date_range_days": spread.get("date_range_days", 0)
            }
            
            result["branch_stats"] = {
                "total_branches": len(branches),
                "strategy": strategy.get("strategy", "unknown"),
                "has_develop": strategy.get("has_develop", False),
                "has_feature_branches": strategy.get("has_feature_branches", False)
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

    def deep_analyze_matched_repos(
        self,
        matched_repos: List[Dict],
        all_repo_data: List[Dict] = None
    ) -> List[Dict]:
        """
        Analyze matched repos and return results with clone_penalty and deep_red_flags.
        This is the method called by github_routes.py and github_routes_phase2.py.
        
        Args:
            matched_repos: List of matched project-repo pairs from ProjectRepoMatching
            all_repo_data: Optional full repo data for README lookup
            
        Returns:
            List of deep analysis results, each containing clone_penalty and deep_red_flags
        """
        # Extract repo info from matched projects
        repos_to_analyze = []
        for match in matched_repos:
            repo_info = match.get("repository", match)
            # Try to find full repo data for README
            readme = None
            if all_repo_data:
                for repo_data in all_repo_data:
                    if repo_data.get("name") == repo_info.get("name"):
                        readme = repo_data.get("readme")
                        break
            
            repos_to_analyze.append({
                "owner": repo_info.get("owner", repo_info.get("full_name", "/").split("/")[0]),
                "name": repo_info.get("name"),
                "readme": readme
            })
        
        # Run deep analysis
        # We need a username; extract from owner of first repo
        username = repos_to_analyze[0]["owner"] if repos_to_analyze else ""
        deep_results = self.analyze_repos_deep(repos_to_analyze, username)
        
        # Enrich each result with clone_penalty and deep_red_flags
        from ..ml.inference.similarity_engine import SimilarityEngine
        engine = SimilarityEngine()
        
        for result in deep_results:
            clone_detection = result.get("clone_detection", {})
            similarity = clone_detection.get("similarity", 0.0)
            result["clone_penalty"] = engine.get_penalty(similarity)
            result["deep_red_flags"] = result.get("red_flags", [])
        
        return deep_results