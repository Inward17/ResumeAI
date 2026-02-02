"""
Repository Analyzer - Extract EASY signals from repos
Handles fork detection, commit analysis, and OSS contributions
"""
from typing import Dict, List, Optional
from .github_client import GitHubClient
from app.utils.constants import (
    MIN_COMMITS_PER_REPO,
    MIN_OSS_COMMITS,
    OSS_ALLOWLIST,
    TRIVIAL_REPO_PATTERNS
)
from app.utils.text_utils import is_trivial_repo_name
from app.utils.date_utils import analyze_commit_spread, get_most_recent_commit_date


class RepoAnalyzer:
    """Analyzes repositories for ownership signals"""
    
    def __init__(self, github_client: GitHubClient):
        self.client = github_client
    
    def analyze_repos(self, username: str, repos: List[Dict]) -> Dict:
        """
        Analyze all repos for a user
        
        Args:
            username: GitHub username
            repos: List of repository objects from GitHub API
            
        Returns:
            Analysis results with signals and enriched data
        """
        total_repos = len(repos)
        original_repos = 0
        forked_repos = 0
        total_commits = 0
        repos_with_low_commits = 0
        repos_with_dump_pattern = 0
        trivial_repos_count = 0
        oss_contributions = 0
        
        enriched_repos = []
        all_commit_dates = []
        
        for repo in repos:
            repo_data = self._analyze_single_repo(username, repo)
            enriched_repos.append(repo_data)
            
            # Aggregate statistics
            if repo_data["is_original"]:
                original_repos += 1
            else:
                forked_repos += 1
            
            commit_count = repo_data["commit_count"]
            total_commits += commit_count
            
            if commit_count < MIN_COMMITS_PER_REPO:
                repos_with_low_commits += 1
            
            if repo_data["has_dump_pattern"]:
                repos_with_dump_pattern += 1
            
            if repo_data["is_trivial"]:
                trivial_repos_count += 1
            
            if repo_data["is_oss_contribution"]:
                oss_contributions += 1
            
            # Collect commit dates for global analysis
            all_commit_dates.extend(repo_data["commit_dates"])
        
        # Overall commit spread analysis
        overall_spread = analyze_commit_spread(all_commit_dates)
        most_recent_commit = get_most_recent_commit_date(all_commit_dates)
        
        return {
            "repositoryStats": {
                "total": total_repos,
                "original": original_repos,
                "forked": forked_repos,
                "original_ratio": original_repos / total_repos if total_repos > 0 else 0.0,
            },
            "commitStats": {
                "total": total_commits,
                "average_per_repo": total_commits / total_repos if total_repos > 0 else 0.0,
                "repos_with_low_commits": repos_with_low_commits,
                "lastCommitDate": most_recent_commit,
            },
            "commitSpread": overall_spread,
            "ossContributions": oss_contributions,
            "trivialRepos": trivial_repos_count,
            "reposDumpPattern": repos_with_dump_pattern,
            "enrichedRepositories": enriched_repos,
        }
    
    def _analyze_single_repo(self, username: str, repo: Dict) -> Dict:
        """
        Analyze a single repository
        
        Args:
            username: GitHub username
            repo: Repository object from GitHub API
            
        Returns:
            Enriched repository data
        """
        repo_name = repo["name"]
        owner = repo["owner"]["login"]
        is_fork = repo.get("fork", False)
        
        # Fetch commits by user
        commits = self.client.get_repo_commits(owner, repo_name, username)
        commit_count = len(commits)
        
        # Extract commit dates
        commit_dates = [c["commit"]["author"]["date"] for c in commits if "commit" in c]
        
        # Analyze commit spread
        spread_analysis = analyze_commit_spread(commit_dates)
        has_dump_pattern = spread_analysis["is_dump_pattern"]
        
        # Determine if this is an OSS contribution
        is_oss_contribution = self._is_oss_contribution(repo, commit_count)
        
        # Check if fork should be treated as original
        is_original = not is_fork or is_oss_contribution or commit_count >= MIN_OSS_COMMITS
        
        # Check if repo name is trivial
        is_trivial = is_trivial_repo_name(repo_name, TRIVIAL_REPO_PATTERNS)
        
        # Get languages
        languages = self.client.get_repo_languages(owner, repo_name)
        
        return {
            "name": repo_name,
            "full_name": repo["full_name"],
            "owner": owner,
            "is_fork": is_fork,
            "is_original": is_original,
            "is_oss_contribution": is_oss_contribution,
            "commit_count": commit_count,
            "commit_dates": commit_dates,
            "has_dump_pattern": has_dump_pattern,
            "is_trivial": is_trivial,
            "languages": languages,
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "created_at": repo.get("created_at", ""),
            "updated_at": repo.get("updated_at", ""),
            "description": repo.get("description", ""),
        }
    
    def _is_oss_contribution(self, repo: Dict, commit_count: int) -> bool:
        """
        Determine if a forked repo is an OSS contribution
        
        Args:
            repo: Repository object
            commit_count: Number of commits by user
            
        Returns:
            True if this is a meaningful OSS contribution
        """
        if not repo.get("fork", False):
            return False
        
        # Check if parent repo is from known OSS organization
        full_name = repo.get("full_name", "").lower()
        
        for org in OSS_ALLOWLIST:
            if full_name.startswith(f"{org}/"):
                # Require meaningful contribution (commits)
                return commit_count >= MIN_OSS_COMMITS
        
        return False