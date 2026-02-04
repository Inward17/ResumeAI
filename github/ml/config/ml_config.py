"""
ML Configuration for Phase-2 Clone Detection
Centralized config for model selection, thresholds, and caching
"""

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
SIMILARITY_VERY_HIGH = 0.90  # Very likely copied
SIMILARITY_HIGH = 0.80       # Template-based
SIMILARITY_NORMAL = 0.80     # Below this = unique

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

# Cache directory
EMBEDDING_CACHE_DIR = "/tmp/github_embeddings_cache"

# Cache TTL (hours)
EMBEDDING_CACHE_TTL_HOURS = 72

# ============================================
# FEATURE FLAGS
# ============================================

# Enable/disable specific features
ENABLE_README_CLONE_DETECTION = True
ENABLE_BRANCH_AWARE_COMMITS = True
ENABLE_POPULAR_REPO_COMPARISON = True

# ============================================
# INFERENCE SETTINGS
# ============================================

# Batch size for embedding generation
EMBEDDING_BATCH_SIZE = 8

# Device (cpu or cuda)
DEVICE = "cpu"

# Number of threads for CPU inference
NUM_THREADS = 4