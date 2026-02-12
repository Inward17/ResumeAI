"""
ML Configuration for Phase-2 Clone Detection
Centralized config for model selection, thresholds, and caching
"""
import tempfile
import os

# ============================================
# EMBEDDING MODEL CONFIGURATION
# ============================================

# Using sentence-transformers/all-MiniLM-L6-v2
# - CPU-only compatible
# - Fast inference
# - Good balance of speed/accuracy
# - No fine-tuning needed
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Max sequence length for embeddings
MAX_SEQUENCE_LENGTH = 512

# Embedding dimension (model-specific, don't change)
EMBEDDING_DIM = 384

# ============================================
# SIMILARITY THRESHOLDS
# ============================================

# README clone detection thresholds (defensible)
SIMILARITY_VERY_HIGH = 0.90  # Very likely copied (≥ 0.90 → COPIED verdict)
SIMILARITY_HIGH = 0.80       # Template-based (0.80-0.89 → TEMPLATE verdict)
# Below SIMILARITY_HIGH (< 0.80) → ORIGINAL verdict

# Scoring penalties based on similarity
PENALTY_VERY_HIGH_SIMILARITY = 25  # ≥ 0.90
PENALTY_HIGH_SIMILARITY = 15       # 0.80-0.90
PENALTY_NORMAL_SIMILARITY = 0      # < 0.80

# ============================================
# POPULAR REPO FETCHING
# ============================================

# Number of top repos to compare against
TOP_REPOS_COUNT = 10

# GitHub Search API parameters
GITHUB_SEARCH_SORT = "stars"
GITHUB_SEARCH_ORDER = "desc"

# Cache TTL for popular repos (hours)
POPULAR_REPO_CACHE_TTL_HOURS = 48

# ============================================
# PROJECT MATCHING THRESHOLDS
# ============================================

# Thresholds for matching resume projects to GitHub repos
PROJECT_MATCH_THRESHOLD_HIGH = 0.75    # Strong match
PROJECT_MATCH_THRESHOLD_MEDIUM = 0.60  # Moderate match
PROJECT_MATCH_THRESHOLD_LOW = 0.50     # Minimum to consider

# ============================================
# PROCESSING LIMITS
# ============================================

# Only apply deep analysis to matched repos
ENABLE_DEEP_ANALYSIS = True

# Maximum repos to analyze deeply per profile
MAX_DEEP_ANALYSIS_REPOS = 10

# ============================================
# VERDICTS
# ============================================

CLONE_VERDICT_COPIED = "COPIED"           # ≥ 0.90 similarity
CLONE_VERDICT_TEMPLATE = "TEMPLATE"       # 0.80-0.90 similarity
CLONE_VERDICT_ORIGINAL = "ORIGINAL"       # < 0.80 similarity
CLONE_VERDICT_UNKNOWN = "UNKNOWN"         # Error/no data

# ============================================
# RED FLAG MESSAGES
# ============================================

RED_FLAG_MESSAGES = {
    "readme_highly_similar": "README highly similar to popular repository",
    "likely_template": "Likely template-based project",
    "suspicious_clone": "Repository appears to be copied",
}

# ============================================
# CACHING
# ============================================

# Enable embedding caching
ENABLE_EMBEDDING_CACHE = True

# Cache directory (cross-platform - works on Windows, Linux, macOS)
EMBEDDING_CACHE_DIR = os.path.join(tempfile.gettempdir(), "github_embeddings_cache")

# Cache TTL (hours)
EMBEDDING_CACHE_TTL_HOURS = 72

# ============================================
# FEATURE FLAGS
# ============================================

# Enable/disable specific features
ENABLE_README_CLONE_DETECTION = True
ENABLE_BRANCH_AWARE_COMMITS = True
ENABLE_POPULAR_REPO_COMPARISON = True

# Enable project-repo matching (for resume-based analysis)
ENABLE_PROJECT_MATCHING = True

# Only deep analyze matched repos (not all repos)
DEEP_ANALYZE_MATCHED_REPOS_ONLY = True

# Maximum repos to deep analyze when matching is enabled
# Alias to MAX_DEEP_ANALYSIS_REPOS for consistency (Issue #4 fix)
MAX_DEEP_ANALYZED_REPOS = MAX_DEEP_ANALYSIS_REPOS

# Alias for embedding cache (used by project_repo_matching.py)
USE_EMBEDDING_CACHE = ENABLE_EMBEDDING_CACHE

# ============================================
# INFERENCE SETTINGS
# ============================================

# Batch size for embedding generation
EMBEDDING_BATCH_SIZE = 8

# Device (cpu or cuda)
DEVICE = "cpu"

# Number of threads for CPU inference
NUM_THREADS = 4