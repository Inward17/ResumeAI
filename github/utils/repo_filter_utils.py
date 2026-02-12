"""
Repo Filter Utilities
Helper functions for filtering repositories based on various criteria
"""
from typing import List, Dict


def filter_by_commit_count(repos: List[Dict], min_commits: int = 5) -> List[Dict]:
    """
    Filter repositories by minimum commit count
    
    Args:
        repos: List of repository dictionaries
        min_commits: Minimum commits required
        
    Returns:
        Filtered list of repositories
    """
    return [
        repo for repo in repos 
        if repo.get("commit_count", 0) >= min_commits
    ]


def filter_original_only(repos: List[Dict]) -> List[Dict]:
    """
    Filter to only original (non-forked) repositories
    
    Args:
        repos: List of repository dictionaries
        
    Returns:
        List of original repositories
    """
    return [
        repo for repo in repos
        if repo.get("is_original", True)
    ]


def filter_with_readme(repos: List[Dict]) -> List[Dict]:
    """
    Filter repositories that have a README
    
    Args:
        repos: List of repository dictionaries
        
    Returns:
        List of repositories with README
    """
    return [
        repo for repo in repos
        if repo.get("has_readme", False)
    ]


def filter_non_trivial(repos: List[Dict]) -> List[Dict]:
    """
    Filter out trivial repositories
    
    Args:
        repos: List of repository dictionaries
        
    Returns:
        List of non-trivial repositories
    """
    return [
        repo for repo in repos
        if not repo.get("is_trivial", False)
    ]


def filter_by_stars(repos: List[Dict], min_stars: int = 0) -> List[Dict]:
    """
    Filter repositories by minimum star count
    
    Args:
        repos: List of repository dictionaries
        min_stars: Minimum stars required
        
    Returns:
        Filtered list of repositories
    """
    return [
        repo for repo in repos
        if repo.get("stars", 0) >= min_stars
    ]


def filter_matched_repos(
    repos: List[Dict],
    matched_repo_names: List[str]
) -> List[Dict]:
    """
    Filter to only repositories that match given names
    
    Args:
        repos: List of repository dictionaries
        matched_repo_names: List of repo names to match
        
    Returns:
        List of matched repositories
    """
    matched_set = set(matched_repo_names)
    return [
        repo for repo in repos
        if repo.get("name") in matched_set
    ]


def get_top_repos(repos: List[Dict], limit: int = 10, sort_by: str = "stars") -> List[Dict]:
    """
    Get top N repositories sorted by specified criterion
    
    Args:
        repos: List of repository dictionaries
        limit: Maximum number of repos to return
        sort_by: Field to sort by (stars, commit_count, etc.)
        
    Returns:
        Top N repositories
    """
    if sort_by not in ["stars", "commit_count", "forks"]:
        sort_by = "stars"
    
    sorted_repos = sorted(
        repos,
        key=lambda r: r.get(sort_by, 0),
        reverse=True
    )
    
    return sorted_repos[:limit]


def apply_quality_filters(repos: List[Dict]) -> List[Dict]:
    """
    Apply standard quality filters
    Filters: original, has readme, not trivial, min 5 commits
    
    Args:
        repos: List of repository dictionaries
        
    Returns:
        Quality-filtered repositories
    """
    filtered = repos
    filtered = filter_original_only(filtered)
    filtered = filter_with_readme(filtered)
    filtered = filter_non_trivial(filtered)
    filtered = filter_by_commit_count(filtered, min_commits=5)
    
    return filtered