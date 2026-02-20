"""
Enterprise GitHub Verification — Behavioral Analysis + OSS Contribution
Exact formulas from specification — no approximations.

Formulas:
  commitConsistency   = min(1.0, (D / T) * 2)
  burstRisk           = clamp(commits_in_top_2_days / total_commits, 0, 1)
  messageQuality      = 0.5 * unique_msg_ratio + 0.5 * min(1.0, avg_len / 40)
  fileDiversity       = linear interp  0.1→0  0.5→1 of (unique_files / total_commits)
  BehavioralAuth      = average(consistency, 1-burstRisk, msgQuality, fileDiversity)

OSS:
  ≥ 3 external contributions → 1.0
  1–2 → 0.5
  0 → 0.0
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import (
    COMMIT_MESSAGE_LENGTH_CAP,
    FILE_DIVERSITY_HIGH,
    FILE_DIVERSITY_LOW,
    OSS_HIGH_THRESHOLD,
    OSS_LOW_THRESHOLD,
)
from ..github_client import GitHubClient
from ..models import BehavioralAnalysisResult

logger = logging.getLogger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ═══════════════════════════════════════════════════════════════════
# Core behavioral sub-scores (pure functions — deterministic)
# ═══════════════════════════════════════════════════════════════════

def compute_commit_consistency(total_commits: int, unique_days: int) -> float:
    """
    consistency = min(1.0, (D / T) * 2)
    If T == 0 → 0
    """
    if total_commits == 0:
        return 0.0
    return _clamp(min(1.0, (unique_days / total_commits) * 2))


def compute_burst_risk(commits_in_top_2_days: int, total_commits: int) -> float:
    """
    burstRisk = clamp(commits_in_top_2_days / total_commits, 0, 1)
    """
    if total_commits == 0:
        return 0.0
    return _clamp(commits_in_top_2_days / total_commits)


def compute_message_quality(
    unique_messages: int,
    total_commits: int,
    avg_message_length: float,
) -> float:
    """
    quality = 0.5 * (unique_messages / total_commits) + 0.5 * min(1.0, avg_len / 40)
    """
    if total_commits == 0:
        return 0.0
    unique_ratio = unique_messages / total_commits
    length_ratio = min(1.0, avg_message_length / COMMIT_MESSAGE_LENGTH_CAP)
    return _clamp(0.5 * unique_ratio + 0.5 * length_ratio)


def compute_file_diversity(unique_files_touched: int, total_commits: int) -> float:
    """
    ratio = unique_files_touched / total_commits
    If ≥ 0.5 → 1.0
    If ≤ 0.1 → 0.0
    Else linear interpolation.
    """
    if total_commits == 0:
        return 0.0
    ratio = unique_files_touched / total_commits
    if ratio >= FILE_DIVERSITY_HIGH:
        return 1.0
    if ratio <= FILE_DIVERSITY_LOW:
        return 0.0
    # Linear interpolation between 0.1→0 and 0.5→1
    return _clamp((ratio - FILE_DIVERSITY_LOW) / (FILE_DIVERSITY_HIGH - FILE_DIVERSITY_LOW))


def compute_behavioral_authenticity(
    consistency: float,
    burst_risk: float,
    message_quality: float,
    file_diversity: float,
) -> float:
    """
    BehavioralAuthenticity = average(consistency, 1-burstRisk, msgQuality, fileDiversity)
    """
    return _clamp(
        (consistency + (1.0 - burst_risk) + message_quality + file_diversity) / 4.0
    )


def compute_oss_score(external_contributions: int) -> float:
    """
    ≥ 3 → 1.0
    1–2 → 0.5
    0   → 0.0
    """
    if external_contributions >= OSS_HIGH_THRESHOLD:
        return 1.0
    if external_contributions >= OSS_LOW_THRESHOLD:
        return 0.5
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# Commit data extraction helpers
# ═══════════════════════════════════════════════════════════════════

def _extract_commit_stats(commits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract all signals from a list of commit objects."""
    total = len(commits)
    if total == 0:
        return {
            "total_commits": 0,
            "unique_days": 0,
            "commits_in_top_2_days": 0,
            "unique_messages": 0,
            "avg_message_length": 0.0,
            "unique_files_touched": 0,
        }

    # Dates
    day_counts: Counter = Counter()
    messages: List[str] = []
    files_touched: set = set()

    for c in commits:
        commit_data = c.get("commit", {})
        author_data = commit_data.get("author", {})
        date_str = author_data.get("date", "")

        # Parse date → day
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                day_counts[dt.strftime("%Y-%m-%d")] += 1
            except Exception:
                pass

        # Message
        msg = commit_data.get("message", "")
        if msg:
            messages.append(msg.strip())

        # Files (if available — GitHub commits endpoint may not include them)
        for f in c.get("files", []):
            fname = f.get("filename", "")
            if fname:
                files_touched.add(fname)

    unique_days = len(day_counts)

    # Top 2 days by commit count
    top_2 = day_counts.most_common(2)
    commits_in_top_2 = sum(count for _, count in top_2)

    # Messages
    unique_messages = len(set(messages))
    avg_msg_len = sum(len(m) for m in messages) / total if total > 0 else 0.0

    return {
        "total_commits": total,
        "unique_days": unique_days,
        "commits_in_top_2_days": commits_in_top_2,
        "unique_messages": unique_messages,
        "avg_message_length": avg_msg_len,
        "unique_files_touched": len(files_touched),
    }


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

async def analyse_behavior(
    repos: List[Dict[str, Any]],
    username: str,
    all_repos: List[Dict[str, Any]],
    client: GitHubClient,
) -> BehavioralAnalysisResult:
    """
    Run behavioral analysis across all repos for *username*.

    Args:
        repos:     repos selected for deep analysis (max 3)
        username:  GitHub username
        all_repos: full repo list (for OSS detection)
        client:    async GitHub client

    Returns:
        ``BehavioralAnalysisResult``
    """
    import asyncio

    # Gather commits for the deep-analysed repos
    all_commits: List[Dict[str, Any]] = []
    for repo in repos:
        owner = repo.get("owner", {})
        owner_login = owner.get("login", owner) if isinstance(owner, dict) else str(owner)
        repo_name = repo.get("name", "")
        commits = await client.get_repo_commits(owner_login, repo_name, username)
        all_commits.extend(commits)

    stats = _extract_commit_stats(all_commits)

    # Sub-scores
    consistency = compute_commit_consistency(stats["total_commits"], stats["unique_days"])
    burst_risk = compute_burst_risk(stats["commits_in_top_2_days"], stats["total_commits"])
    msg_quality = compute_message_quality(
        stats["unique_messages"], stats["total_commits"], stats["avg_message_length"]
    )
    file_div = compute_file_diversity(stats["unique_files_touched"], stats["total_commits"])
    behavioral_auth = compute_behavioral_authenticity(consistency, burst_risk, msg_quality, file_div)

    # ── OSS contribution ──
    oss_details = await _detect_oss_contributions(username, all_repos, client)
    oss_score = compute_oss_score(oss_details.get("external_contributions", 0))

    return BehavioralAnalysisResult(
        commitConsistency=round(consistency, 4),
        burstRisk=round(burst_risk, 4),
        messageQuality=round(msg_quality, 4),
        fileDiversity=round(file_div, 4),
        behavioralAuthenticity=round(behavioral_auth, 4),
        ossContributionScore=oss_score,
        ossDetails=oss_details,
    )


async def _detect_oss_contributions(
    username: str,
    all_repos: List[Dict[str, Any]],
    client: GitHubClient,
) -> Dict[str, Any]:
    """
    Detect:
      - Commits to repos NOT owned by candidate
      - Distinct external orgs contributed to
    """
    external_contributions = 0
    external_orgs: set = set()

    for repo in all_repos:
        owner = repo.get("owner", {})
        owner_login = owner.get("login", "") if isinstance(owner, dict) else str(owner)

        if owner_login.lower() == username.lower():
            continue  # owned by candidate — skip

        # This is an external repo (fork or org membership)
        if repo.get("fork", False):
            # Check if candidate actually committed
            repo_name = repo.get("name", "")
            commits = await client.get_repo_commits(owner_login, repo_name, username, max_commits=5)
            if commits:
                external_contributions += 1
                external_orgs.add(owner_login)

    return {
        "external_contributions": external_contributions,
        "distinct_external_orgs": len(external_orgs),
        "external_org_list": list(external_orgs),
    }
