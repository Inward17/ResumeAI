"""
Branch Utilities - Helper functions for branch-aware analysis
Already implemented in github_client.py, this provides helpers
"""
from typing import List, Dict


def aggregate_branch_commits(branch_commits: Dict[str, List[Dict]]) -> Dict:
    """
    Aggregate commits across branches (already deduplicated)
    
    Args:
        branch_commits: Dict mapping branch_name -> commit_list
        
    Returns:
        Aggregated statistics
    """
    all_commits = {}
    
    for branch_name, commits in branch_commits.items():
        for commit in commits:
            sha = commit.get("sha")
            if sha and sha not in all_commits:
                all_commits[sha] = {
                    **commit,
                    "branches": [branch_name]
                }
            elif sha:
                # Same commit in multiple branches
                all_commits[sha]["branches"].append(branch_name)
    
    total_commits = len(all_commits)
    total_branches = len(branch_commits)
    
    # Calculate branch distribution
    commits_per_branch = {
        branch: len(commits) 
        for branch, commits in branch_commits.items()
    }
    
    return {
        "total_unique_commits": total_commits,
        "total_branches": total_branches,
        "commits_per_branch": commits_per_branch,
        "unique_commits": list(all_commits.values())
    }


def get_primary_development_branch(branch_commits: Dict[str, List[Dict]]) -> str:
    """
    Identify the primary development branch
    
    Args:
        branch_commits: Dict mapping branch_name -> commit_list
        
    Returns:
        Name of primary branch (most commits)
    """
    if not branch_commits:
        return "unknown"
    
    # Find branch with most commits
    max_commits = 0
    primary_branch = "main"
    
    for branch_name, commits in branch_commits.items():
        if len(commits) > max_commits:
            max_commits = len(commits)
            primary_branch = branch_name
    
    return primary_branch


def analyze_branch_strategy(branch_commits: Dict[str, List[Dict]]) -> Dict:
    """
    Analyze branching strategy (feature branches, gitflow, etc.)
    
    Args:
        branch_commits: Dict mapping branch_name -> commit_list
        
    Returns:
        Dict with strategy analysis
    """
    branch_names = list(branch_commits.keys())
    num_branches = len(branch_names)
    
    # Common branch patterns
    has_main = any(b in ['main', 'master'] for b in branch_names)
    has_develop = any(b == 'develop' for b in branch_names)
    has_feature_branches = any(b.startswith('feature/') for b in branch_names)
    has_release_branches = any(b.startswith('release/') for b in branch_names)
    
    # Determine strategy
    if has_develop and (has_feature_branches or has_release_branches):
        strategy = "gitflow"
    elif has_feature_branches:
        strategy = "feature_branch"
    elif num_branches == 1:
        strategy = "single_branch"
    elif num_branches <= 3:
        strategy = "simple_multi_branch"
    else:
        strategy = "complex_multi_branch"
    
    return {
        "strategy": strategy,
        "num_branches": num_branches,
        "has_main": has_main,
        "has_develop": has_develop,
        "has_feature_branches": has_feature_branches,
        "branch_names": branch_names
    }