"""
Embedding Model - Wrapper for sentence-transformers
CPU-only, no fine-tuning, simple inference
"""
from typing import List, Union
import numpy as np
from ..config.ml_config import (
    EMBEDDING_MODEL_NAME,
    MAX_SEQUENCE_LENGTH,
    EMBEDDING_DIM,
    DEVICE,
    NUM_THREADS
)


class EmbeddingModel:
    """Wrapper for sentence-transformer model"""
    
    def __init__(self):
        """
        Initialize the embedding model
        Lazy loading - only loads when first encode() is called
        """
        self.model = None
        self.model_name = EMBEDDING_MODEL_NAME
        self.device = DEVICE
        
    def _load_model(self):
        """Lazy load the model"""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Set CPU threads
            torch.set_num_threads(NUM_THREADS)
            
            # Load model
            self.model = SentenceTransformer(self.model_name)
            self.model.to(self.device)
            self.model.eval()  # Set to evaluation mode
            
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        normalize: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for text(s)
        
        Args:
            texts: Single text or list of texts
            normalize: Whether to normalize embeddings (for cosine similarity)
            
        Returns:
            Numpy array of embeddings (normalized if specified)
        """
        self._load_model()
        
        # Convert single string to list
        if isinstance(texts, str):
            texts = [texts]
            single_input = True
        else:
            single_input = False
        
        # Truncate texts to max length
        texts = [text[:MAX_SEQUENCE_LENGTH * 4] for text in texts]  # Rough char limit
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )
        
        # Return single embedding or array
        if single_input:
            return embeddings[0]
        
        return embeddings
        
    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Wrapper for single text encoding"""
        return self.encode(text, normalize=normalize)
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension"""
        return EMBEDDING_DIM
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None

    def batch_cosine_similarity(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity between query and candidates
        Assumes embeddings are already normalized
        """
        # Dot product of normalized vectors = cosine similarity
        return np.dot(candidate_embeddings, query_embedding)