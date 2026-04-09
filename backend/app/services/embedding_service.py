"""
Local Embedding Service using FastEmbed
Model: all-MiniLM-L6-v2 (22M params, 384-dimensional embeddings)
Free, fast, runs locally without API calls
"""
from typing import List, Optional
from math import sqrt

import logging

_logger = logging.getLogger(__name__)

# Lazy-loaded singleton for efficiency
_embedding_model = None
_fastembed_available = None  # None = untested, True = OK, False = broken


def _get_model():
    """Lazy load the embedding model (first call downloads ~80MB model)"""
    global _embedding_model, _fastembed_available
    if _fastembed_available is False:
        return None  # already known broken — skip fast
    if _embedding_model is None:
        try:
            from fastembed import TextEmbedding
            _embedding_model = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            _fastembed_available = True
        except Exception as e:
            _fastembed_available = False
            _logger.warning(
                "fastembed/onnxruntime unavailable (DLL or import error). "
                "Embeddings will be zero-vectors. Error: %s", e
            )
            return None
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """
    Generate 384-dimensional embedding for text.
    Falls back to zero-vector if fastembed/onnxruntime is unavailable.
    """
    if not text or not text.strip():
        return [0.0] * 384

    model = _get_model()
    if model is None:
        return [0.0] * 384  # fallback: onnxruntime DLL not working

    embeddings = list(model.embed([text.strip()]))
    return embeddings[0].tolist()


def batch_generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts efficiently.
    Falls back to zero-vectors if fastembed/onnxruntime is unavailable.
    """
    if not texts:
        return []

    model = _get_model()
    if model is None:
        return [[0.0] * 384 for _ in texts]  # fallback

    # Filter empty texts and track indices
    valid_texts = []
    valid_indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            valid_texts.append(text.strip())
            valid_indices.append(i)

    if not valid_texts:
        return [[0.0] * 384 for _ in texts]

    embeddings_gen = model.embed(valid_texts)
    valid_embeddings = [emb.tolist() for emb in embeddings_gen]

    # Reconstruct full list with zeros for empty texts
    result = [[0.0] * 384 for _ in texts]
    for idx, emb in zip(valid_indices, valid_embeddings):
        result[idx] = emb

    return result


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Formula: cos(θ) = (A · B) / (||A|| × ||B||)
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Similarity score normalized to 0.0-1.0 range
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    # Check for zero vectors
    if all(v == 0 for v in vec1) or all(v == 0 for v in vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sqrt(sum(a ** 2 for a in vec1))
    norm2 = sqrt(sum(b ** 2 for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    # Clamp to [0, 1] — do NOT apply (similarity+1)/2 which compresses the
    # range and inflates weak matches toward 0.5.
    # MiniLM sentence embeddings produce cosine values in [0, 1] for
    # semantically related text; negative values only appear for unrelated
    # content and should simply become 0 (no evidence).
    return max(0.0, min(1.0, similarity))


def build_github_projects_text(github_v2_data: dict) -> str:
    """
    Build a single text corpus from stored GitHub verification data,
    suitable for passing to generate_embedding().

    Pulls from (in priority order):
      1. resumeVerification.matches  — names of repos matched to resume projects
      2. repositoryStats             — language / originality signals
      3. cloneAnalysis               — originality verdicts (as signal words)

    Returns:
        Concatenated text string, or "" if no usable data found.

    This function is pure and stateless — it has no DB or network dependency.
    """
    if not github_v2_data or not isinstance(github_v2_data, dict):
        return ""

    parts: List[str] = []

    # 1. Matched repo names (highest-value signal: these are confirmed projects)
    resume_verification = github_v2_data.get("resumeVerification") or {}
    matches = resume_verification.get("matches") or []
    for m in matches:
        if isinstance(m, dict):
            repo_name = m.get("repoName", "")
            project_name = m.get("projectName", "")
            # Both the GitHub repo name and the claimed project name are useful
            for token in (repo_name, project_name):
                if token:
                    # Convert hyphens/underscores to spaces for better tokenisation
                    parts.append(token.replace("-", " ").replace("_", " "))

    # 2. Repository stats — primary language inferred from the account
    repo_stats = github_v2_data.get("repositoryStats") or {}
    total = repo_stats.get("total", 0)
    original = repo_stats.get("original", 0)
    if total > 0:
        parts.append(f"{original} original repositories")

    # 3. Clone-analysis verdicts — lightweight originality signal
    clone_analysis = github_v2_data.get("cloneAnalysis") or {}
    for detail in clone_analysis.get("repoDetails") or []:
        if isinstance(detail, dict) and not detail.get("skipped"):
            repo = detail.get("repo", "")
            if repo:
                parts.append(repo.replace("-", " ").replace("_", " "))

    return " ".join(parts)
