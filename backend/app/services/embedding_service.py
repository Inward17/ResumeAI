"""
Local Embedding Service using FastEmbed
Model: all-MiniLM-L6-v2 (22M params, 384-dimensional embeddings)
Free, fast, runs locally without API calls
"""
from typing import List, Optional
from math import sqrt

# Lazy-loaded singleton for efficiency
_embedding_model = None


def _get_model():
    """Lazy load the embedding model (first call downloads ~80MB model)"""
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding
        _embedding_model = TextEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """
    Generate 384-dimensional embedding for text.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of 384 floats representing the text embedding
    """
    if not text or not text.strip():
        return [0.0] * 384
    
    model = _get_model()
    embeddings = list(model.embed([text.strip()]))
    return embeddings[0].tolist()


def batch_generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts efficiently.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of 384-dimensional embeddings
    """
    if not texts:
        return []
    
    # Filter empty texts and track indices
    valid_texts = []
    valid_indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            valid_texts.append(text.strip())
            valid_indices.append(i)
    
    if not valid_texts:
        return [[0.0] * 384 for _ in texts]
    
    model = _get_model()
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
    # Normalize from [-1, 1] to [0, 1]
    return max(0.0, min(1.0, (similarity + 1) / 2))
