"""
GitHub API Client - Raw API calls only
Handles authentication, rate limiting, and error handling
"""
import requests
from typing import Dict, List, Optional
from datetime import datetime
from ..utils.constants import MAX_BRANCHES_TO_ANALYZE


class GitHubClient:
    """Clean wrapper for GitHub API v3"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client
        
        Args:
            token: GitHub personal access token (optional but recommended)
        """
        self.token = token
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            })
        else:
            self.session.headers.update({
                "Accept": "application/vnd.github.v3+json"
            })
    
    def get_user_repos(self, username: str) -> List[Dict]:
        """
        Fetch all repositories for a user
        
        Args:
            username: GitHub username
            
        Returns:
            List of repository objects
        """
        repos = []
        page = 1
        per_page = 100
        
        while True:
            url = f"{self.BASE_URL}/users/{username}/repos"
            params = {
                "per_page": per_page,
                "page": page,
                "type": "owner"  # Only repos owned by user
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 404:
                raise ValueError(f"User '{username}' not found")
            elif response.status_code == 403:
                raise Exception("Rate limit exceeded. Please provide a GitHub token.")
            elif response.status_code != 200:
                raise Exception(f"GitHub API error: {response.status_code}")
            
            data = response.json()
            
            if not data:
                break
                
            repos.extend(data)
            
            if len(data) < per_page:
                break
                
            page += 1
        
        return repos
    
    def get_repo_languages(self, owner: str, repo_name: str) -> Dict[str, int]:
        """
        Get language breakdown for a repository
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary mapping language -> bytes of code
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/languages"
        response = self.session.get(url)
        
        if response.status_code != 200:
            return {}
        
        return response.json()
    
    def get_repo_readme(self, owner: str, repo_name: str) -> Optional[str]:
        """
        Fetch README content for a repository
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            README text content or None if not found
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/readme"
        response = self.session.get(url)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        # README comes base64 encoded
        import base64
        content = base64.b64decode(data.get("content", "")).decode("utf-8", errors="ignore")
        
        return content
    
    def get_repo_commits(self, owner: str, repo_name: str, username: str, max_commits: int = 100) -> List[Dict]:
        """
        Fetch recent commits for a repository filtered by author
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            username: GitHub username to filter commits
            max_commits: Maximum number of commits to fetch
            
        Returns:
            List of commit objects
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/commits"
        params = {
            "author": username,
            "per_page": min(max_commits, 100)
        }
        
        response = self.session.get(url, params=params)
        
        if response.status_code != 200:
            return []
        
        return response.json()
    
    def get_repo_branches(self, owner: str, repo_name: str) -> List[Dict]:
        """
        Fetch branches for a repository
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/branches"
        response = self.session.get(url)
        
        if response.status_code != 200:
            return []
            
        return response.json()

    def get_repo_commits(self, owner: str, repo_name: str, username: str, max_commits: int = 100, all_branches: bool = False) -> List[Dict]:
        """
        Fetch recent commits for a repository filtered by author
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            username: GitHub username to filter commits
            max_commits: Maximum number of commits to fetch
            all_branches: If True, fetch commits from all branches (up to configured limit)
            
        Returns:
            List of commit objects
        """
        if not all_branches:
            # Phase-1 behavior (main branch only)
            return self._fetch_commits_single_branch(owner, repo_name, username, max_commits)
        
        # Phase-2 behavior (multi-branch)
        branches = self.get_repo_branches(owner, repo_name)
        
        # Limit branches to avoid rate limits
        target_branches = [b['name'] for b in branches[:MAX_BRANCHES_TO_ANALYZE]]
        
        if not target_branches:
            # Fallback to default behavior if no branches found
            return self._fetch_commits_single_branch(owner, repo_name, username, max_commits)
            
        all_commits = {}
        
        for branch in target_branches:
            branch_commits = self._fetch_commits_single_branch(
                owner, repo_name, username, max_commits, sha=branch
            )
            
            for commit in branch_commits:
                sha = commit.get("sha")
                if sha and sha not in all_commits:
                    all_commits[sha] = commit
        
        # Convert back to list and sort by date (newest first)
        unique_commits = list(all_commits.values())
        unique_commits.sort(
            key=lambda x: x.get("commit", {}).get("author", {}).get("date", ""), 
            reverse=True
        )
        
        return unique_commits[:max_commits]

    def _fetch_commits_single_branch(self, owner: str, repo_name: str, username: str, max_commits: int, sha: str = None) -> List[Dict]:
        """Helper to fetch commits from a specific branch/sha"""
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}/commits"
        params = {
            "author": username,
            "per_page": min(max_commits, 100)
        }
        
        if sha:
            params["sha"] = sha
        
        response = self.session.get(url, params=params)
        
        if response.status_code != 200:
            return []
        
        return response.json()
    
    def check_rate_limit(self) -> Dict:
        """
        Check current rate limit status
        
        Returns:
            Rate limit information
        """
        url = f"{self.BASE_URL}/rate_limit"
        response = self.session.get(url)
        
        if response.status_code == 200:
            return response.json()
        
        return {}