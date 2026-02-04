"""
Popular Repo Fetcher - Find top GitHub repos by search query
Uses GitHub Search API safely with caching
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .github_client import GitHubClient
from ..ml.config.ml_config import (
    TOP_REPOS_COUNT,
    GITHUB_SEARCH_SORT,
    GITHUB_SEARCH_ORDER,
    POPULAR_REPO_CACHE_TTL_HOURS
)


class PopularRepoFetcher:
    """Fetch top GitHub repos for comparison"""
    
    def __init__(self, github_client: GitHubClient, cache_dir: str = "/tmp/popular_repos_cache"):
        """
        Initialize popular repo fetcher
        
        Args:
            github_client: GitHub API client
            cache_dir: Directory for caching popular repos
        """
        self.client = github_client
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, query: str) -> str:
        """Get cache file path for query"""
        import hashlib
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{query_hash}.json")
    
    def _load_from_cache(self, query: str) -> Optional[List[Dict]]:
        """Load popular repos from cache if not expired"""
        cache_path = self._get_cache_path(query)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
            
            cached_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cached_time > timedelta(hours=POPULAR_REPO_CACHE_TTL_HOURS):
                return None
            
            return cache_data['repos']
        except Exception:
            return None
    
    def _save_to_cache(self, query: str, repos: List[Dict]):
        """Save popular repos to cache"""
        cache_path = self._get_cache_path(query)
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'query': query,
                'repos': repos
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception:
            pass
    
    def fetch_top_repos(self, query: str, limit: int = None) -> List[Dict]:
        """
        Fetch top repositories matching query
        
        Args:
            query: Search query (repo name or keywords)
            limit: Number of repos to fetch
            
        Returns:
            List of repo dicts with name, owner, README, stars
        """
        if limit is None:
            limit = TOP_REPOS_COUNT
        
        # Try cache first
        cached = self._load_from_cache(query)
        if cached is not None:
            return cached[:limit]
        
        # Search GitHub
        url = f"{self.client.BASE_URL}/search/repositories"
        params = {
            "q": query,
            "sort": GITHUB_SEARCH_SORT,
            "order": GITHUB_SEARCH_ORDER,
            "per_page": limit
        }
        
        try:
            response = self.client.session.get(url, params=params)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            items = data.get("items", [])
            
            repos = []
            for item in items:
                owner = item["owner"]["login"]
                repo_name = item["name"]
                stars = item.get("stargazers_count", 0)
                
                # Fetch README
                readme = self.client.get_repo_readme(owner, repo_name)
                
                repos.append({
                    "name": repo_name,
                    "owner": owner,
                    "full_name": item["full_name"],
                    "readme": readme or "",
                    "stars": stars,
                    "url": item["html_url"]
                })
            
            self._save_to_cache(query, repos)
            return repos
            
        except Exception:
            return []
    
    def fetch_similar_repos(self, repo_name: str, readme_keywords: List[str] = None) -> List[Dict]:
        """Fetch repos similar to given repo"""
        query_parts = [repo_name]
        if readme_keywords:
            query_parts.extend(readme_keywords[:3])
        
        query = " ".join(query_parts)
        return self.fetch_top_repos(query)