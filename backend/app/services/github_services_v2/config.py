"""
Enterprise GitHub Verification — Centralised Configuration
All thresholds, weights, model configs, rate limits, and guardrails.
No magic numbers anywhere else in the codebase.
"""

import os

# ═══════════════════════════════════════════════════════════════════
# MODEL CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

# Code clone detection — local CodeBERT (768-dim)
CODEBERT_MODEL: str = "microsoft/codebert-base"
CODEBERT_EMBEDDING_DIM: int = 768

# Semantic embedding — resume matching + README similarity (1024-dim)
BGE_MODEL: str = "BAAI/bge-large-en-v1.5"
BGE_EMBEDDING_DIM: int = 1024

# Inference
EMBEDDING_BATCH_SIZE: int = 8
DEVICE: str = "cpu"
NUM_THREADS: int = 4
MAX_SEQUENCE_LENGTH: int = 512


# ═══════════════════════════════════════════════════════════════════
# RESUME → REPO MATCHING THRESHOLDS
# ═══════════════════════════════════════════════════════════════════

# Stage 2 — fuzzy match minimum
FUZZY_MATCH_THRESHOLD: int = 85  # token_set_ratio ≥ 85

# Stage 3 — embedding cosine similarity
EMBEDDING_MATCH_STRONG: float = 0.80    # ≥ 0.80 → STRONG
EMBEDDING_MATCH_MODERATE: float = 0.65  # 0.65–0.80 → MODERATE
# < 0.65 → no match


# ═══════════════════════════════════════════════════════════════════
# README CLONE DETECTION THRESHOLDS
# ═══════════════════════════════════════════════════════════════════

README_SIMILARITY_COPIED: float = 0.90     # ≥ 0.90 → COPIED
README_SIMILARITY_SUSPICIOUS: float = 0.75  # 0.75–0.90 → SUSPICIOUS
# < 0.75 → ORIGINAL


# ═══════════════════════════════════════════════════════════════════
# CODE CLONE DETECTION THRESHOLDS
# ═══════════════════════════════════════════════════════════════════

CODE_SIMILARITY_COPIED: float = 0.90       # ≥ 0.90 → COPIED
CODE_SIMILARITY_SUSPICIOUS: float = 0.75   # 0.75–0.90 → SUSPICIOUS
# < 0.75 → ORIGINAL

# LLM escalation band
LLM_ESCALATION_LOW: float = 0.75
LLM_ESCALATION_HIGH: float = 0.90


# ═══════════════════════════════════════════════════════════════════
# SIGNAL FUSION WEIGHTS (must sum to 1.0)
# ═══════════════════════════════════════════════════════════════════

SIGNAL_WEIGHTS: dict = {
    "ResumeConsistency":       0.20,
    "RepositoryAuthenticity":  0.20,
    "ReadmeOriginality":       0.15,
    "CodeOriginality":         0.20,
    "BehavioralAuthenticity":  0.15,
    "OSSContribution":         0.10,
}


# ═══════════════════════════════════════════════════════════════════
# REPOSITORY AUTHENTICITY FORMULA
# ═══════════════════════════════════════════════════════════════════
# RepositoryAuthenticity = weighted sum of 4 sub-signals:
#   original_ratio_weight * (original / total)
# + commit_depth_weight  * min(1.0, avg_commits_per_repo / COMMIT_DEPTH_CAP)
# + recency_weight       * recency_score          (1.0 if last commit ≤ 90d, linear decay to 0 at 365d)
# + non_trivial_weight   * (non_trivial / total)
#
# All sub-signals are 0–1 normalised.  Final clamped 0–1.

REPO_AUTH_ORIGINAL_RATIO_WEIGHT: float = 0.40
REPO_AUTH_COMMIT_DEPTH_WEIGHT: float = 0.25
REPO_AUTH_RECENCY_WEIGHT: float = 0.15
REPO_AUTH_NON_TRIVIAL_WEIGHT: float = 0.20

COMMIT_DEPTH_CAP: float = 50.0       # avg ≥ 50 commits/repo → sub-signal = 1.0
RECENCY_FULL_DAYS: int = 90          # ≤ 90 days → recency = 1.0
RECENCY_ZERO_DAYS: int = 365         # ≥ 365 days → recency = 0.0


# ═══════════════════════════════════════════════════════════════════
# CONFIDENCE LEVEL
# ═══════════════════════════════════════════════════════════════════

CONFIDENCE_HIGH_MAX_STD: float = 0.15   # std_dev < 0.15 → HIGH
CONFIDENCE_MEDIUM_MAX_STD: float = 0.30  # 0.15 ≤ std_dev ≤ 0.30 → MEDIUM
# > 0.30 → LOW
MIN_SIGNALS_FOR_CONFIDENCE: int = 3     # fewer → LOW regardless


# ═══════════════════════════════════════════════════════════════════
# BEHAVIORAL ANALYSIS
# ═══════════════════════════════════════════════════════════════════

COMMIT_MESSAGE_LENGTH_CAP: int = 40  # avg ≥ 40 chars → sub-signal = 1.0
FILE_DIVERSITY_HIGH: float = 0.5     # ≥ 0.5 → 1.0
FILE_DIVERSITY_LOW: float = 0.1      # ≤ 0.1 → 0.0
MAX_COMMIT_DETAIL_FETCHES: int = 30  # max commits enriched with per-file details (caps GitHub API calls)


# ═══════════════════════════════════════════════════════════════════
# OSS CONTRIBUTION
# ═══════════════════════════════════════════════════════════════════

OSS_HIGH_THRESHOLD: int = 3   # ≥ 3 ext contributions → 1.0
OSS_LOW_THRESHOLD: int = 1    # 1–2 → 0.5, 0 → 0.0


# ═══════════════════════════════════════════════════════════════════
# RATE LIMITING & RETRY
# ═══════════════════════════════════════════════════════════════════

MAX_CONCURRENT_GITHUB_CALLS: int = 10
RETRY_ATTEMPTS: int = 3
RETRY_BACKOFF_SECONDS: tuple = (0.5, 1.0, 2.0)  # exponential
REQUEST_TIMEOUT_SECONDS: int = 30


# ═══════════════════════════════════════════════════════════════════
# PERFORMANCE GUARDRAILS
# ═══════════════════════════════════════════════════════════════════

MAX_CODE_FILES_PER_REPO: int = 40
MAX_CODE_FILE_SIZE_BYTES: int = 200_000        # 200 KB
MAX_TOTAL_CODE_SIZE_BYTES: int = 1_500_000     # 1.5 MB
MAX_DEEP_ANALYSIS_REPOS: int = 3
MAX_EXTERNAL_REPOS: int = 10
DEEP_ANALYSIS_TIMEOUT_SECONDS: int = 60


# ═══════════════════════════════════════════════════════════════════
# CODE PROCESSING
# ═══════════════════════════════════════════════════════════════════

SUPPORTED_CODE_EXTENSIONS: tuple = (
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".cpp", ".c", ".h", ".hpp",
    ".go", ".cs", ".php", ".rb", ".rs",
    ".kt", ".swift", ".scala", ".dart",
    ".vue", ".lua", ".r", ".sh",
)

EXCLUDED_DIRECTORIES: tuple = (
    "node_modules", "dist", "build", "vendor",
    ".git", "venv", "env", "__pycache__",
)

CODE_CHUNK_SIZE: int = 1500          # characters per chunk
CODE_CHUNK_MIN_SIZE: int = 200       # drop chunks < 200 chars
STRUCTURE_JACCARD_THRESHOLD: float = 0.25  # skip ref repo if < 0.25
TOP_CHUNK_PERCENT: float = 0.30      # top 30% chunk similarities


# ═══════════════════════════════════════════════════════════════════
# EMBEDDING CACHE
# ═══════════════════════════════════════════════════════════════════

EMBEDDING_CACHE_DIR: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".cache", "github_embeddings",
)
EMBEDDING_CACHE_TTL_HOURS: int = 72
EMBEDDING_LRU_MAX_SIZE: int = 4096

# ═══════════════════════════════════════════════════════════════════
# GITHUB SEARCH CACHE
# ═══════════════════════════════════════════════════════════════════

SEARCH_CACHE_DIR: str = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".cache", "github_search",
)
SEARCH_CACHE_TTL_HOURS: int = 48


# ═══════════════════════════════════════════════════════════════════
# LLM ESCALATION
# ═══════════════════════════════════════════════════════════════════

LLM_TEMPERATURE: float = 0.0
LLM_TIMEOUT_SECONDS: int = 15        # hard timeout per LLM call
LLM_MAX_INPUT_CHARS: int = 4000      # truncate input beyond this


# ═══════════════════════════════════════════════════════════════════
# EXPLAINABILITY RED FLAG RULES
# ═══════════════════════════════════════════════════════════════════

RED_FLAG_RULES: dict = {
    "low_resume_consistency":  {"signal": "ResumeConsistency",  "threshold": 0.5,  "direction": "below",
                                "message": "Less than half of claimed projects found on GitHub"},
    "code_similarity_high":    {"signal": "codeSimilarityMax",  "threshold": 0.75, "direction": "above",
                                "message": "High code similarity with external repositories detected"},
    "readme_similarity_high":  {"signal": "readmeSimilarityMax","threshold": 0.75, "direction": "above",
                                "message": "README content highly similar to external repositories"},
    "commit_burst":            {"signal": "burstRisk",          "threshold": 0.6,  "direction": "above",
                                "message": "Commit burst pattern detected — majority of commits in 1–2 days"},
    "poor_commit_messages":    {"signal": "messageQuality",     "threshold": 0.4,  "direction": "below",
                                "message": "Low quality commit messages (short / repetitive)"},
    "low_original_ratio":      {"signal": "originalRatio",      "threshold": 0.4,  "direction": "below",
                                "message": "Majority of repositories are forks, not original work"},
}


# ═══════════════════════════════════════════════════════════════════
# TRIVIAL REPO DETECTION
# ═══════════════════════════════════════════════════════════════════

# Word-level tokens — repo name is split on [-_.] and checked for exact token matches
TRIVIAL_REPO_TOKENS: set = {
    "todo", "clone", "calculator", "test", "demo",
    "practice", "tutorial", "learning", "sample",
    "example", "helloworld",
}

# Compound patterns that OVERRIDE trivial detection — if the repo name contains
# any of these substrings, it is NOT marked trivial regardless of token matches
TRIVIAL_EXCLUSION_COMPOUNDS: list = [
    "machine-learning", "deep-learning", "reinforcement-learning",
    "machine_learning", "deep_learning", "reinforcement_learning",
    "hackathon", "competition", "challenge",
]

# ═══════════════════════════════════════════════════════════════════
# GITHUB API
# ═══════════════════════════════════════════════════════════════════

GITHUB_API_BASE_URL: str = "https://api.github.com"
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
