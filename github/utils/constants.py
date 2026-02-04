"""
Constants for GitHub scoring system
Thresholds, weights, allowlists, and configuration
"""

# ============================================
# SCORING WEIGHTS
# ============================================
WEIGHTS = {
    "original_repo_ratio": 30,
    "commit_depth": 25,
    "readme_presence": 15,
    "readme_language_match": 15,
    "oss_contribution_bonus": 10
}

RED_FLAG_PENALTY_MAX = 25

# ============================================
# THRESHOLDS
# ============================================

# Commit-related thresholds
MIN_COMMITS_PER_REPO = 5
COMMIT_DUMP_RATIO = 0.70  # 70% commits in 1-2 days triggers flag

# README thresholds
MIN_README_LENGTH = 100  # characters

# OSS contribution thresholds
MIN_OSS_COMMITS = 10  # Minimum commits to count as OSS contribution

# Language mismatch thresholds
MISMATCH_REPO_THRESHOLD = 2  # Flag if mismatch appears in 2+ repos

# ============================================
# OSS ORGANIZATION ALLOWLIST
# ============================================
# Popular OSS organizations where forks are considered valuable
OSS_ALLOWLIST = {
    "apache",
    "kubernetes",
    "tensorflow",
    "pytorch",
    "react",
    "facebook",
    "google",
    "microsoft",
    "angular",
    "vue",
    "nodejs",
    "rust-lang",
    "golang",
    "python",
    "django",
    "rails",
    "dotnet",
    "docker",
    "elastic",
    "mongodb",
    "redis",
    "postgresql",
    "mysql",
    "nginx",
    "jenkins",
    "grafana",
    "prometheus",
    "ansible",
    "terraform",
    "envoyproxy",
    "istio",
    "helm",
    "etcd",
    "containerd",
    "grpc",
    "protocolbuffers",
}

# ============================================
# TRIVIAL REPO NAME PATTERNS
# ============================================
# Names that suggest low-effort projects
TRIVIAL_REPO_PATTERNS = [
    "todo",
    "clone",
    "calculator",
    "test",
    "demo",
    "practice",
    "tutorial",
    "learning",
    "sample",
    "example",
    "hello-world",
    "hello_world",
    "helloworld",
]

# ============================================
# LANGUAGE KEYWORDS
# ============================================
# Keywords to extract from README and match against repo languages
LANGUAGE_KEYWORDS = {
    "Python": ["python", "django", "flask", "fastapi", "pandas", "numpy", "pytorch", "tensorflow"],
    "JavaScript": ["javascript", "js", "node", "nodejs", "react", "vue", "angular", "express", "next"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java", "spring", "springboot", "maven", "gradle"],
    "Go": ["golang", "go"],
    "Rust": ["rust", "cargo"],
    "C++": ["c++", "cpp"],
    "C": ["c"],
    "Ruby": ["ruby", "rails"],
    "PHP": ["php", "laravel", "symfony"],
    "Swift": ["swift", "ios"],
    "Kotlin": ["kotlin", "android"],
    "C#": ["c#", "csharp", ".net", "dotnet"],
    "Scala": ["scala"],
    "R": ["r", "rstats"],
    "Dart": ["dart", "flutter"],
    "Elixir": ["elixir", "phoenix"],
    "Haskell": ["haskell"],
    "Clojure": ["clojure"],
}

# ============================================
# RED FLAG MESSAGES
# ============================================
RED_FLAGS = {
    "mostly_forked": "Mostly forked repositories",
    "low_commit_depth": "Low commit depth across repositories",
    "commit_dump": "Commit dump pattern detected (burst commits)",
    "missing_readme": "Many repositories missing README",
    "tech_stack_mismatch": "README tech stack doesn't match repository languages",
    "trivial_repos": "Multiple trivial/tutorial repositories",
}

# ============================================
# API CONFIGURATION
# ============================================
MAX_COMMITS_PER_REPO = 100  # Maximum commits to fetch per repo
REQUEST_TIMEOUT = 30  # seconds

# Analyze all branches (Phase-2)
ANALYZE_ALL_BRANCHES = True
MAX_BRANCHES_TO_ANALYZE = 10
