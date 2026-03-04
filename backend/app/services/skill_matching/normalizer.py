"""
Skill Normalizer
================
Maps common tech aliases and abbreviations to their canonical forms before
any embedding or keyword matching.  Solves the "GCP vs Google Cloud Platform"
class of problems without requiring an external ontology API.

Usage:
    from app.services.skill_matching.normalizer import normalize_skill

    normalize_skill("GCP")   # → "google cloud platform"
    normalize_skill("K8s")   # → "kubernetes"
"""

SKILL_ALIASES: dict[str, str] = {
    # ── Cloud Platforms ────────────────────────────────────────────────────
    "gcp": "google cloud platform",
    "aws": "amazon web services",
    "azure": "microsoft azure",
    # ── Container / Orchestration ──────────────────────────────────────────
    "k8s": "kubernetes",
    "kube": "kubernetes",
    "docker swarm": "container orchestration",
    # ── JavaScript Ecosystem ───────────────────────────────────────────────
    "js": "javascript",
    "ts": "typescript",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "angularjs": "angular",
    "angular.js": "angular",
    "nodejs": "node",
    "node.js": "node",
    "nextjs": "next",
    "next.js": "next",
    "nuxtjs": "nuxt",
    "nuxt.js": "nuxt",
    "expressjs": "express",
    "express.js": "express",
    # ── Databases ──────────────────────────────────────────────────────────
    "postgres": "postgresql",
    "pg": "postgresql",
    "mongo": "mongodb",
    "dynamo": "dynamodb",
    "dynamodb": "amazon dynamodb",
    "redis": "redis cache",
    "elastic": "elasticsearch",
    "mssql": "microsoft sql server",
    "mysql": "sql",
    # ── ML / AI ────────────────────────────────────────────────────────────
    "ml": "machine learning",
    "dl": "deep learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "llm": "large language model",
    "genai": "generative ai",
    "gen ai": "generative ai",
    # ── ML Frameworks ──────────────────────────────────────────────────────
    "tf": "tensorflow",
    "jax": "google jax",
    "scikit": "scikit-learn",
    "sklearn": "scikit-learn",
    "xgboost": "gradient boosting",
    # ── DevOps / CI-CD ──────────────────────────────────────────────────────
    "ci/cd": "continuous integration continuous deployment",
    "cicd": "continuous integration continuous deployment",
    "iac": "infrastructure as code",
    "terraform": "infrastructure as code terraform",
    "ansible": "infrastructure automation ansible",
    "gh actions": "github actions",
    "gha": "github actions",
    # ── Languages (short forms) ────────────────────────────────────────────
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "cpp": "c++",
    "c sharp": "c#",
    "csharp": "c#",
    "golang": "go",
    "kotlin": "kotlin android",
    # ── Mobile ────────────────────────────────────────────────────────────
    "rn": "react native",
    "flutter": "flutter dart",
    "ios": "ios swift development",
    "android": "android kotlin development",
    # ── APIs / Architecture ────────────────────────────────────────────────
    "rest": "rest api",
    "restful": "rest api",
    "grpc": "grpc protocol buffers",
    "graphql": "graphql api",
    "microservices": "microservices architecture",
    # ── Data / Analytics ──────────────────────────────────────────────────
    "bi": "business intelligence",
    "etl": "extract transform load",
    "dbt": "data build tool",
    "airflow": "apache airflow",
    "kafka": "apache kafka",
    "spark": "apache spark",
}


def normalize_skill(skill: str) -> str:
    """
    Return the canonical form of *skill*.

    Lowercases, strips whitespace, applies alias table.
    If no alias exists, returns the lowercased input unchanged.

    Args:
        skill: Raw skill string (e.g., "GCP", "ReactJS", "K8s").

    Returns:
        Canonical skill string (e.g., "google cloud platform").
    """
    normalised = skill.lower().strip()
    return SKILL_ALIASES.get(normalised, normalised)
