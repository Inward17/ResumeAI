"""
Enterprise GitHub Verification — Main Orchestrator
Public entrypoint: ``verify_github(candidate_id, parsed_resume)``.
15-step pipeline — fully async, no blocking, failure-resilient.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import (
    CODE_SIMILARITY_SUSPICIOUS,
    CODE_SIMILARITY_COPIED,
    COMMIT_DEPTH_CAP,
    MAX_DEEP_ANALYSIS_REPOS,
    RECENCY_FULL_DAYS,
    RECENCY_ZERO_DAYS,
    REPO_AUTH_COMMIT_DEPTH_WEIGHT,
    REPO_AUTH_NON_TRIVIAL_WEIGHT,
    REPO_AUTH_ORIGINAL_RATIO_WEIGHT,
    REPO_AUTH_RECENCY_WEIGHT,
    TRIVIAL_REPO_PATTERNS,
)
from .github_client import GitHubClient
from .models import (
    AuthenticityResult,
    BehavioralAnalysisResult,
    CloneAnalysisResult,
    GitHubVerificationResult,
    RepositoryStats,
    ResumeVerificationResult,
    SignalScores,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Public entrypoint
# ═══════════════════════════════════════════════════════════════════

async def verify_github(
    candidate_id: str,
    parsed_resume: dict,
) -> GitHubVerificationResult:
    """
    Run the full GitHub verification pipeline.

    This is the ONLY public function.  Returns a fully populated
    ``GitHubVerificationResult`` that is MongoDB-compatible via
    ``.to_mongo_dict()``.

    The pipeline continues on partial failure — any block that throws
    is logged and the pipeline moves on with available signals.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Extract GitHub username ──────────────────────────
    username = _extract_username(parsed_resume)

    # ── Step 2: No username → fail fast ──────────────────────────
    if not username:
        return GitHubVerificationResult(
            success=False,
            candidateId=candidate_id,
            username=None,
            error="No GitHub username found in parsed resume",
            analyzedAt=now_iso,
        )

    client = GitHubClient()
    try:
        return await _run_pipeline(candidate_id, username, parsed_resume, client, now_iso)
    finally:
        await client.close()


async def _run_pipeline(
    candidate_id: str,
    username: str,
    parsed_resume: dict,
    client: GitHubClient,
    now_iso: str,
) -> GitHubVerificationResult:
    """Internal: execute steps 3–15."""

    # ── Step 3: Fetch repos (async) ──────────────────────────────
    all_repos: List[Dict[str, Any]] = []
    try:
        all_repos = await client.get_user_repos(username)
    except Exception as exc:
        logger.error("Failed to fetch repos for %s: %s", username, exc)
        return GitHubVerificationResult(
            success=False,
            candidateId=candidate_id,
            username=username,
            error=f"Failed to fetch repositories: {exc}",
            analyzedAt=now_iso,
        )

    if not all_repos:
        return GitHubVerificationResult(
            success=False,
            candidateId=candidate_id,
            username=username,
            error="No public repositories found",
            analyzedAt=now_iso,
        )

    # ── Step 4: Repository stats + RepositoryAuthenticity ────────
    repo_stats = _compute_repo_stats(all_repos, username)
    repo_auth_signal = repo_stats.repositoryAuthenticity

    # ── Step 5: Resume → Repo matching ───────────────────────────
    resume_verification: Optional[ResumeVerificationResult] = None
    resume_consistency: Optional[float] = None
    try:
        projects = _extract_projects(parsed_resume)
        from .matching.project_matcher import match_projects_to_repos
        resume_verification = await match_projects_to_repos(projects, all_repos)
        resume_consistency = resume_verification.resumeConsistency
    except Exception as exc:
        logger.warning("Project matching failed: %s", exc)

    # ── Step 6: Select top repos for deep analysis ───────────────
    deep_repos = _select_deep_repos(all_repos, resume_verification, username)

    # ── Step 7: README Similarity ────────────────────────────────
    readme_result: Optional[Dict[str, Any]] = None
    try:
        from .analysis.readme_similarity import analyse_readme_similarity
        readme_result = await analyse_readme_similarity(deep_repos, client)
    except Exception as exc:
        logger.warning("README similarity failed: %s", exc)

    # ── Step 8: Code Clone Detection ─────────────────────────────
    code_result: Optional[Dict[str, Any]] = None
    if not client.rate_limited:
        try:
            from .analysis.code_similarity import analyse_code_similarity
            code_result = await analyse_code_similarity(deep_repos, client)
        except Exception as exc:
            logger.warning("Code similarity failed: %s", exc)

    # ── Step 9: Behavioral Analysis ──────────────────────────────
    behavioral: Optional[BehavioralAnalysisResult] = None
    try:
        from .analysis.behavioral_analysis import analyse_behavior
        behavioral = await analyse_behavior(deep_repos, username, all_repos, client)
    except Exception as exc:
        logger.warning("Behavioral analysis failed: %s", exc)

    # ── Step 10: (OSS done inside behavioral — included) ─────────

    # ── Step 11: Normalise signals ───────────────────────────────
    signals = SignalScores()
    raw_signals: Dict[str, float] = {}

    signals.RepositoryAuthenticity = repo_auth_signal
    raw_signals["originalRatio"] = repo_stats.originalRatio

    if resume_consistency is not None:
        signals.ResumeConsistency = resume_consistency
    if readme_result:
        signals.ReadmeOriginality = readme_result.get("readmeOriginality")
        raw_signals["readmeSimilarityMax"] = readme_result.get("readmeSimilarityMax", 0.0)
    if code_result:
        signals.CodeOriginality = code_result.get("codeOriginality")
        raw_signals["codeSimilarityMax"] = code_result.get("codeSimilarityMax", 0.0)
    if behavioral:
        signals.BehavioralAuthenticity = behavioral.behavioralAuthenticity
        signals.OSSContribution = behavioral.ossContributionScore
        raw_signals["burstRisk"] = behavioral.burstRisk
        raw_signals["messageQuality"] = behavioral.messageQuality

    # ── Step 12: Signal Fusion ───────────────────────────────────
    from .scoring.signal_fusion import fuse_signals
    auth_result, red_flags = fuse_signals(signals, raw_signals)

    # ── Step 13: Explainability (red flags done in fusion) ───────

    # ── Step 13b: LLM Escalation (optional) ──────────────────────
    llm_escalation: Optional[Dict[str, Any]] = None
    code_sim_max = raw_signals.get("codeSimilarityMax", 0.0)
    if CODE_SIMILARITY_SUSPICIOUS <= code_sim_max < CODE_SIMILARITY_COPIED:
        try:
            from .llm.llm_provider import escalate_to_llm
            cand_summary = _repo_summary(deep_repos[0]) if deep_repos else ""
            ref_name = code_result.get("codeMatchedRepo", "") if code_result else ""
            ref_summary = f"External repository: {ref_name}"
            llm_escalation = await escalate_to_llm(
                candidate_repo=f"{username}/{deep_repos[0].get('name', '') if deep_repos else ''}",
                candidate_summary=cand_summary,
                reference_repo=ref_name,
                reference_summary=ref_summary,
                similarity=code_sim_max,
                key_functions="",
            )
        except Exception as exc:
            logger.warning("LLM escalation failed (non-fatal): %s", exc)

    # ── Step 14: Build Mongo-compatible output ───────────────────
    clone_analysis: Optional[CloneAnalysisResult] = None
    if readme_result or code_result:
        clone_analysis = CloneAnalysisResult(
            readmeSimilarityMax=readme_result.get("readmeSimilarityMax", 0.0) if readme_result else 0.0,
            readmeVerdict=readme_result.get("readmeVerdict", "ORIGINAL") if readme_result else "ORIGINAL",
            readmeMatchedRepo=readme_result.get("readmeMatchedRepo") if readme_result else None,
            readmeOriginality=readme_result.get("readmeOriginality", 1.0) if readme_result else 1.0,
            codeSimilarityMax=code_result.get("codeSimilarityMax", 0.0) if code_result else 0.0,
            codeVerdict=code_result.get("codeVerdict", "ORIGINAL") if code_result else "ORIGINAL",
            codeMatchedRepo=code_result.get("codeMatchedRepo") if code_result else None,
            codeOriginality=code_result.get("codeOriginality", 1.0) if code_result else 1.0,
            repoDetails=(
                (readme_result.get("repoDetails", []) if readme_result else [])
                + (code_result.get("repoDetails", []) if code_result else [])
            ),
        )

    # ── Step 15: Return result ───────────────────────────────────
    return GitHubVerificationResult(
        success=True,
        candidateId=candidate_id,
        username=username,
        score100=auth_result.score100,
        score40=auth_result.score40,
        confidenceLevel=auth_result.confidenceLevel,
        redFlags=red_flags,
        signals=signals,
        authenticity=auth_result,
        resumeVerification=resume_verification,
        cloneAnalysis=clone_analysis,
        behavioralAnalysis=behavioral,
        repositoryStats=repo_stats,
        llmEscalation=llm_escalation,
        analyzedAt=now_iso,
    )


# ═══════════════════════════════════════════════════════════════════
# Helpers — RepositoryAuthenticity (Step 4)
# ═══════════════════════════════════════════════════════════════════

def _compute_repo_stats(
    repos: List[Dict[str, Any]],
    username: str,
) -> RepositoryStats:
    """
    Compute aggregate repository statistics and the
    RepositoryAuthenticity sub-signal.

    Formula:
      RepositoryAuthenticity =
          0.40 * (original / total)
        + 0.25 * min(1.0, avg_commits / COMMIT_DEPTH_CAP)
        + 0.15 * recency_score
        + 0.20 * (non_trivial / total)
    """
    total = len(repos)
    if total == 0:
        return RepositoryStats(
            total=0, original=0, forked=0, originalRatio=0.0,
            trivial=0, nonTrivialRatio=0.0, avgCommitsPerRepo=0.0,
            lastCommitDate=None, repositoryAuthenticity=0.0,
        )

    original = 0
    forked = 0
    trivial = 0
    total_size = 0
    last_push: Optional[str] = None

    for r in repos:
        if r.get("fork", False):
            forked += 1
        else:
            original += 1

        name_lower = r.get("name", "").lower()
        if any(pat in name_lower for pat in TRIVIAL_REPO_PATTERNS):
            trivial += 1

        total_size += r.get("size", 0)

        pushed = r.get("pushed_at")
        if pushed and (last_push is None or pushed > last_push):
            last_push = pushed

    non_trivial = total - trivial
    original_ratio = original / total
    non_trivial_ratio = non_trivial / total

    # Approximate avg commits/repo from repo sizes (heuristic when we don't
    # fetch all commits up front — will be refined during deep analysis)
    avg_size = total_size / total if total > 0 else 0
    # Rough: 1 commit ~ 10KB
    avg_commits = min(avg_size / 10_000, 200.0)
    commit_depth_score = min(1.0, avg_commits / COMMIT_DEPTH_CAP)

    # Recency
    recency = _compute_recency(last_push)

    # RepositoryAuthenticity composite
    repo_auth = (
        REPO_AUTH_ORIGINAL_RATIO_WEIGHT * original_ratio
        + REPO_AUTH_COMMIT_DEPTH_WEIGHT * commit_depth_score
        + REPO_AUTH_RECENCY_WEIGHT * recency
        + REPO_AUTH_NON_TRIVIAL_WEIGHT * non_trivial_ratio
    )
    repo_auth = max(0.0, min(1.0, repo_auth))

    return RepositoryStats(
        total=total,
        original=original,
        forked=forked,
        originalRatio=round(original_ratio, 4),
        trivial=trivial,
        nonTrivialRatio=round(non_trivial_ratio, 4),
        avgCommitsPerRepo=round(avg_commits, 2),
        lastCommitDate=last_push,
        repositoryAuthenticity=round(repo_auth, 4),
    )


def _compute_recency(last_push: Optional[str]) -> float:
    """
    1.0 if ≤ 90 days ago
    Linear decay to 0.0 at 365 days
    0.0 if > 365 or unknown
    """
    if not last_push:
        return 0.0
    try:
        dt = datetime.fromisoformat(last_push.replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - dt).days
        if days_ago <= RECENCY_FULL_DAYS:
            return 1.0
        if days_ago >= RECENCY_ZERO_DAYS:
            return 0.0
        return (RECENCY_ZERO_DAYS - days_ago) / (RECENCY_ZERO_DAYS - RECENCY_FULL_DAYS)
    except Exception:
        return 0.0


# ═══════════════════════════════════════════════════════════════════
# Helpers — Project extraction
# ═══════════════════════════════════════════════════════════════════

def _extract_username(parsed_resume: dict) -> Optional[str]:
    """Try multiple key paths to find a GitHub username."""
    # Direct field
    for key in ("github_username", "githubUsername", "github"):
        val = parsed_resume.get(key)
        if val and isinstance(val, str):
            return val.strip().split("/")[-1]

    # Links array
    for link in parsed_resume.get("links", []):
        url = link if isinstance(link, str) else link.get("url", "")
        if "github.com/" in url:
            parts = url.rstrip("/").split("github.com/")
            if len(parts) > 1:
                return parts[-1].split("/")[0]

    # Social profiles
    profiles = parsed_resume.get("socialProfiles", parsed_resume.get("social_profiles", {}))
    if isinstance(profiles, dict):
        gh = profiles.get("github", "")
        if gh:
            return gh.strip().split("/")[-1]

    return None


def _extract_projects(parsed_resume: dict) -> List[Dict[str, Any]]:
    """Extract project list from resume.  Each must have at least ``name``."""
    projects = parsed_resume.get("projects", [])
    if not isinstance(projects, list):
        return []
    return [p for p in projects if isinstance(p, dict) and p.get("name")]


# ═══════════════════════════════════════════════════════════════════
# Helpers — Top-N repo selection
# ═══════════════════════════════════════════════════════════════════

def _select_deep_repos(
    all_repos: List[Dict[str, Any]],
    resume_verification: Optional[ResumeVerificationResult],
    username: str,
) -> List[Dict[str, Any]]:
    """
    Select top repos for deep analysis (max MAX_DEEP_ANALYSIS_REPOS).

    Priority:
      1. Repos matched to resume projects (highest similarity first)
      2. Original (non-fork) repos by stars / size descending
    """
    selected_names: set = set()
    selected: List[Dict[str, Any]] = []

    # 1. Matched repos first
    if resume_verification and resume_verification.matches:
        matched_names = {m.repoName for m in resume_verification.matches}
        for repo in all_repos:
            if repo.get("name") in matched_names and repo.get("name") not in selected_names:
                selected.append(repo)
                selected_names.add(repo["name"])
                if len(selected) >= MAX_DEEP_ANALYSIS_REPOS:
                    return selected

    # 2. Non-fork repos by star count
    originals = [r for r in all_repos if not r.get("fork", False) and r.get("name") not in selected_names]
    originals.sort(key=lambda r: (r.get("stargazers_count", 0), r.get("size", 0)), reverse=True)

    for repo in originals:
        if len(selected) >= MAX_DEEP_ANALYSIS_REPOS:
            break
        selected.append(repo)
        selected_names.add(repo["name"])

    return selected


def _repo_summary(repo: Dict[str, Any]) -> str:
    """Build a short text summary for LLM context."""
    parts = [repo.get("name", "")]
    if repo.get("description"):
        parts.append(repo["description"])
    lang = repo.get("language", "")
    if lang:
        parts.append(f"Language: {lang}")
    return " | ".join(parts)
