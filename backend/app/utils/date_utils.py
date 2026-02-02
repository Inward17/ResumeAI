"""
Date utilities for analyzing commit patterns
"""
from datetime import datetime
from typing import List
from collections import Counter


def parse_github_date(date_string: str) -> datetime:
    """
    Parse GitHub ISO 8601 date format
    
    Args:
        date_string: ISO 8601 date string
        
    Returns:
        datetime object
    """
    # GitHub format: "2024-01-15T10:30:00Z"
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")


def analyze_commit_spread(commit_dates: List[str]) -> dict:
    """
    Analyze commit distribution to detect dump patterns
    
    Args:
        commit_dates: List of ISO 8601 date strings
        
    Returns:
        Dictionary with spread analysis:
        - total_commits: Total number of commits
        - unique_days: Number of unique days with commits
        - is_dump_pattern: Whether commits show dump pattern
        - max_day_ratio: Ratio of commits on busiest day
    """
    if not commit_dates:
        return {
            "total_commits": 0,
            "unique_days": 0,
            "is_dump_pattern": False,
            "max_day_ratio": 0.0
        }
    
    # Extract just the date part (YYYY-MM-DD)
    dates = []
    for date_str in commit_dates:
        try:
            dt = parse_github_date(date_str)
            dates.append(dt.date())
        except:
            continue
    
    if not dates:
        return {
            "total_commits": 0,
            "unique_days": 0,
            "is_dump_pattern": False,
            "max_day_ratio": 0.0
        }
    
    # Count commits per day
    day_counts = Counter(dates)
    
    total_commits = len(dates)
    unique_days = len(day_counts)
    
    # Get the two busiest days
    top_days = day_counts.most_common(2)
    commits_on_top_days = sum(count for _, count in top_days)
    
    # Calculate ratio
    max_day_ratio = commits_on_top_days / total_commits if total_commits > 0 else 0.0
    
    # Detect dump pattern: 70%+ commits in 1-2 days
    is_dump_pattern = max_day_ratio >= 0.70
    
    return {
        "total_commits": total_commits,
        "unique_days": unique_days,
        "is_dump_pattern": is_dump_pattern,
        "max_day_ratio": max_day_ratio,
        "date_range_days": (max(dates) - min(dates)).days if len(dates) > 1 else 0
    }


def get_most_recent_commit_date(commit_dates: List[str]) -> str:
    """
    Get the most recent commit date
    
    Args:
        commit_dates: List of ISO 8601 date strings
        
    Returns:
        Most recent date as ISO string, or empty string if none
    """
    if not commit_dates:
        return ""
    
    try:
        dates = [parse_github_date(d) for d in commit_dates]
        most_recent = max(dates)
        return most_recent.isoformat()
    except:
        return ""


def calculate_commit_consistency(commit_dates: List[str]) -> float:
    """
    Calculate how consistently commits are spread over time
    
    Args:
        commit_dates: List of ISO 8601 date strings
        
    Returns:
        Consistency score (0.0 to 1.0), higher is more consistent
    """
    if len(commit_dates) < 2:
        return 0.0
    
    spread_analysis = analyze_commit_spread(commit_dates)
    
    unique_days = spread_analysis["unique_days"]
    total_commits = spread_analysis["total_commits"]
    
    if total_commits == 0:
        return 0.0
    
    # More unique days relative to total commits = more consistent
    # Perfect consistency would be 1 commit per day
    consistency = min(unique_days / total_commits, 1.0)
    
    return consistency