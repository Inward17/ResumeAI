"""
Enterprise GitHub Verification — Data Models
Pydantic models for structured results and MongoDB-compatible output.
These are the HARD-LOCKED shapes that the module returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# Sub-result models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MatchedProject:
    """Single resume-project → GitHub-repo match."""
    projectName: str
    repoName: str
    repoFullName: str
    similarity: float
    matchStage: str          # "EXACT" | "FUZZY" | "EMBEDDING"
    matchStrength: str       # "STRONG" | "MODERATE"


@dataclass
class ResumeVerificationResult:
    """Resume → repo matching aggregate."""
    projectsClaimed: int
    projectsMatched: int
    projectsNotFound: int
    resumeConsistency: float          # 0–1
    matches: List[MatchedProject] = field(default_factory=list)


@dataclass
class CloneAnalysisResult:
    """README + Code clone detection aggregate."""
    readmeSimilarityMax: float        # 0–1
    readmeVerdict: str                # COPIED | SUSPICIOUS | ORIGINAL
    readmeMatchedRepo: Optional[str]
    readmeOriginality: float          # 0–1  (1 - readmeSimilarityMax)
    codeSimilarityMax: float          # 0–1
    codeVerdict: str                  # COPIED | SUSPICIOUS | ORIGINAL
    codeMatchedRepo: Optional[str]
    codeOriginality: float            # 0–1  (1 - codeSimilarityMax)
    repoDetails: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BehavioralAnalysisResult:
    """Behavioral intelligence scores."""
    commitConsistency: float          # 0–1
    burstRisk: float                  # 0–1
    messageQuality: float             # 0–1
    fileDiversity: float              # 0–1
    behavioralAuthenticity: float     # 0–1 average of above (with burstRisk inverted)
    ossContributionScore: float       # 0, 0.5, or 1.0
    ossDetails: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthenticityResult:
    """Top-level authenticity verdict (Mongo: githubData.authenticity)."""
    probability: float                # 0–1 weighted fusion score
    score100: float                   # round(probability * 100, 2)
    score40: int                      # round(score100 * 0.4)
    cloneRiskProbability: float       # max(codeSimilarityMax, readmeSimilarityMax)
    confidenceLevel: str              # HIGH | MEDIUM | LOW


@dataclass
class RepositoryStats:
    """Aggregate repository statistics."""
    total: int
    original: int
    forked: int
    originalRatio: float
    trivial: int
    nonTrivialRatio: float
    avgCommitsPerRepo: float
    lastCommitDate: Optional[str]
    repositoryAuthenticity: float     # 0–1 composite sub-signal


@dataclass
class SignalScores:
    """All 6 normalised signals used in fusion scoring."""
    ResumeConsistency: Optional[float] = None
    RepositoryAuthenticity: Optional[float] = None
    ReadmeOriginality: Optional[float] = None
    CodeOriginality: Optional[float] = None
    BehavioralAuthenticity: Optional[float] = None
    OSSContribution: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════
# Top-level result — the ONLY public return type
# ═══════════════════════════════════════════════════════════════════

@dataclass
class GitHubVerificationResult:
    """
    Returned by ``verify_github()``.
    This is the HARD-LOCKED MongoDB-compatible output shape.
    """
    success: bool
    candidateId: str
    username: Optional[str]

    # Scores
    score100: float = 0.0
    score40: int = 0
    confidenceLevel: str = "LOW"

    # Red flags (rule-based, not LLM)
    redFlags: List[str] = field(default_factory=list)

    # Sub-results
    signals: Optional[SignalScores] = None
    authenticity: Optional[AuthenticityResult] = None
    resumeVerification: Optional[ResumeVerificationResult] = None
    cloneAnalysis: Optional[CloneAnalysisResult] = None
    behavioralAnalysis: Optional[BehavioralAnalysisResult] = None
    repositoryStats: Optional[RepositoryStats] = None

    # LLM escalation (only if triggered)
    llmEscalation: Optional[Dict[str, Any]] = None

    # Metadata
    error: Optional[str] = None
    analyzedAt: Optional[str] = None

    # ─────────────────────────────────────────────────────────────
    # Mongo serialisation
    # ─────────────────────────────────────────────────────────────
    def to_mongo_dict(self) -> Dict[str, Any]:
        """
        HARD-LOCKED MongoDB output structure.
        Extends existing ``githubData`` with the fields below.
        Legacy fields are never removed.
        Embeddings and raw code are NEVER stored.

        Shape::

            githubData: {
                username: str,
                analyzedAt: str,
                authenticity: {
                    probability: float,
                    score100: float,
                    score40: int,
                    cloneRiskProbability: float,
                    confidenceLevel: str
                },
                resumeVerification: {
                    projectsClaimed: int,
                    projectsMatched: int,
                    projectsNotFound: int,
                    resumeConsistency: float,
                    matches: [{ projectName, repoName, repoFullName,
                                similarity, matchStage, matchStrength }]
                },
                cloneAnalysis: {
                    readmeSimilarityMax: float,
                    readmeVerdict: str,
                    readmeMatchedRepo: str | null,
                    readmeOriginality: float,
                    codeSimilarityMax: float,
                    codeVerdict: str,
                    codeMatchedRepo: str | null,
                    codeOriginality: float,
                    repoDetails: [...]
                },
                behavioralAnalysis: {
                    commitConsistency: float,
                    burstRisk: float,
                    messageQuality: float,
                    fileDiversity: float,
                    behavioralAuthenticity: float,
                    ossContributionScore: float,
                    ossDetails: {...}
                },
                repositoryStats: {
                    total: int, original: int, forked: int,
                    originalRatio: float, trivial: int,
                    nonTrivialRatio: float, avgCommitsPerRepo: float,
                    lastCommitDate: str | null,
                    repositoryAuthenticity: float
                },
                signals: {
                    ResumeConsistency: float | null,
                    RepositoryAuthenticity: float | null,
                    ReadmeOriginality: float | null,
                    CodeOriginality: float | null,
                    BehavioralAuthenticity: float | null,
                    OSSContribution: float | null
                },
                redFlags: [str],
                llmEscalation: {...} | null,
                score100: float,
                score40: int,
                confidenceLevel: str
            }
        """
        doc: Dict[str, Any] = {
            "username": self.username,
            "analyzedAt": self.analyzedAt,
            "score100": self.score100,
            "score40": self.score40,
            "confidenceLevel": self.confidenceLevel,
            "redFlags": self.redFlags,
        }

        if self.authenticity:
            doc["authenticity"] = {
                "probability": self.authenticity.probability,
                "score100": self.authenticity.score100,
                "score40": self.authenticity.score40,
                "cloneRiskProbability": self.authenticity.cloneRiskProbability,
                "confidenceLevel": self.authenticity.confidenceLevel,
            }

        if self.resumeVerification:
            rv = self.resumeVerification
            doc["resumeVerification"] = {
                "projectsClaimed": rv.projectsClaimed,
                "projectsMatched": rv.projectsMatched,
                "projectsNotFound": rv.projectsNotFound,
                "resumeConsistency": rv.resumeConsistency,
                "matches": [
                    {
                        "projectName": m.projectName,
                        "repoName": m.repoName,
                        "repoFullName": m.repoFullName,
                        "similarity": m.similarity,
                        "matchStage": m.matchStage,
                        "matchStrength": m.matchStrength,
                    }
                    for m in rv.matches
                ],
            }

        if self.cloneAnalysis:
            ca = self.cloneAnalysis
            doc["cloneAnalysis"] = {
                "readmeSimilarityMax": ca.readmeSimilarityMax,
                "readmeVerdict": ca.readmeVerdict,
                "readmeMatchedRepo": ca.readmeMatchedRepo,
                "readmeOriginality": ca.readmeOriginality,
                "codeSimilarityMax": ca.codeSimilarityMax,
                "codeVerdict": ca.codeVerdict,
                "codeMatchedRepo": ca.codeMatchedRepo,
                "codeOriginality": ca.codeOriginality,
                "repoDetails": ca.repoDetails,
            }

        if self.behavioralAnalysis:
            ba = self.behavioralAnalysis
            doc["behavioralAnalysis"] = {
                "commitConsistency": ba.commitConsistency,
                "burstRisk": ba.burstRisk,
                "messageQuality": ba.messageQuality,
                "fileDiversity": ba.fileDiversity,
                "behavioralAuthenticity": ba.behavioralAuthenticity,
                "ossContributionScore": ba.ossContributionScore,
                "ossDetails": ba.ossDetails,
            }

        if self.repositoryStats:
            rs = self.repositoryStats
            doc["repositoryStats"] = {
                "total": rs.total,
                "original": rs.original,
                "forked": rs.forked,
                "originalRatio": rs.originalRatio,
                "trivial": rs.trivial,
                "nonTrivialRatio": rs.nonTrivialRatio,
                "avgCommitsPerRepo": rs.avgCommitsPerRepo,
                "lastCommitDate": rs.lastCommitDate,
                "repositoryAuthenticity": rs.repositoryAuthenticity,
            }

        if self.signals:
            doc["signals"] = {
                "ResumeConsistency": self.signals.ResumeConsistency,
                "RepositoryAuthenticity": self.signals.RepositoryAuthenticity,
                "ReadmeOriginality": self.signals.ReadmeOriginality,
                "CodeOriginality": self.signals.CodeOriginality,
                "BehavioralAuthenticity": self.signals.BehavioralAuthenticity,
                "OSSContribution": self.signals.OSSContribution,
            }

        if self.llmEscalation:
            doc["llmEscalation"] = self.llmEscalation

        return doc
