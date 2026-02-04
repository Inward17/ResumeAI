"""
Similarity Engine - Compute cosine similarity between embeddings
Clean, testable, no dependencies beyond numpy
"""
import numpy as np
from typing import List, Tuple
from ..embeddings.embedding_model import EmbeddingModel
from ..embeddings.embedding_cache import EmbeddingCache
from ..config.ml_config import (
    SIMILARITY_VERY_HIGH,
    SIMILARITY_HIGH,
    CLONE_VERDICT_COPIED,
    CLONE_VERDICT_TEMPLATE,
    CLONE_VERDICT_ORIGINAL
)


class SimilarityEngine:
    """Compute and interpret similarity scores"""
    
    def __init__(self):
        """Initialize similarity engine with model and cache"""
        self.model = EmbeddingModel()
        self.cache = EmbeddingCache()
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        # Try to get embeddings from cache
        emb1 = self.cache.get(text1)
        if emb1 is None:
            emb1 = self.model.encode(text1, normalize=True)
            self.cache.set(text1, emb1)
        
        emb2 = self.cache.get(text2)
        if emb2 is None:
            emb2 = self.model.encode(text2, normalize=True)
            self.cache.set(text2, emb2)
        
        # Compute cosine similarity (dot product of normalized vectors)
        similarity = float(np.dot(emb1, emb2))
        
        # Clamp to [0, 1] range (should already be, but just in case)
        return max(0.0, min(1.0, similarity))
    
    def compute_max_similarity(
        self, 
        query_text: str, 
        candidate_texts: List[str]
    ) -> Tuple[float, int]:
        """
        Find maximum similarity between query and list of candidates
        
        Args:
            query_text: Text to compare
            candidate_texts: List of texts to compare against
            
        Returns:
            Tuple of (max_similarity, index_of_most_similar)
        """
        if not candidate_texts:
            return 0.0, -1
        
        # Get query embedding (with caching)
        query_emb = self.cache.get(query_text)
        if query_emb is None:
            query_emb = self.model.encode(query_text, normalize=True)
            self.cache.set(query_text, query_emb)
        
        # Compute similarities
        max_sim = 0.0
        max_idx = -1
        
        for idx, candidate_text in enumerate(candidate_texts):
            # Get candidate embedding (with caching)
            cand_emb = self.cache.get(candidate_text)
            if cand_emb is None:
                cand_emb = self.model.encode(candidate_text, normalize=True)
                self.cache.set(candidate_text, cand_emb)
            
            # Compute similarity
            sim = float(np.dot(query_emb, cand_emb))
            
            if sim > max_sim:
                max_sim = sim
                max_idx = idx
        
        return max_sim, max_idx
    
    def get_verdict(self, similarity: float) -> str:
        """
        Convert similarity score to verdict
        
        Args:
            similarity: Similarity score (0.0 to 1.0)
            
        Returns:
            Verdict string (COPIED, TEMPLATE, ORIGINAL)
        """
        if similarity >= SIMILARITY_VERY_HIGH:
            return CLONE_VERDICT_COPIED
        elif similarity >= SIMILARITY_HIGH:
            return CLONE_VERDICT_TEMPLATE
        else:
            return CLONE_VERDICT_ORIGINAL
    
    def get_penalty(self, similarity: float) -> int:
        """
        Get scoring penalty based on similarity
        
        Args:
            similarity: Similarity score
            
        Returns:
            Penalty points to subtract from score
        """
        from ..config.ml_config import (
            PENALTY_VERY_HIGH_SIMILARITY,
            PENALTY_HIGH_SIMILARITY,
            PENALTY_NORMAL_SIMILARITY
        )
        
        if similarity >= SIMILARITY_VERY_HIGH:
            return PENALTY_VERY_HIGH_SIMILARITY
        elif similarity >= SIMILARITY_HIGH:
            return PENALTY_HIGH_SIMILARITY
        else:
            return PENALTY_NORMAL_SIMILARITY