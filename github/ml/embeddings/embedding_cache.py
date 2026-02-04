"""
Embedding Cache - Simple file-based cache for embeddings
Reduces redundant model inference calls
"""
import os
import json
import hashlib
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from ..config.ml_config import (
    ENABLE_EMBEDDING_CACHE,
    EMBEDDING_CACHE_DIR,
    EMBEDDING_CACHE_TTL_HOURS
)


class EmbeddingCache:
    """Simple file-based cache for embeddings"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize embedding cache
        
        Args:
            cache_dir: Directory for cache files (default from config)
        """
        self.cache_dir = cache_dir or EMBEDDING_CACHE_DIR
        self.enabled = ENABLE_EMBEDDING_CACHE
        self.ttl_hours = EMBEDDING_CACHE_TTL_HOURS
        
        if self.enabled:
            os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_key(self, text: str) -> str:
        """
        Generate cache key from text
        
        Args:
            text: Input text
            
        Returns:
            Hash string
        """
        # Use SHA256 hash of text as key
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get file path for cache key"""
        return os.path.join(self.cache_dir, f"{cache_key}.npy")
    
    def _get_metadata_path(self, cache_key: str) -> str:
        """Get metadata file path"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding from cache
        
        Args:
            text: Input text
            
        Returns:
            Cached embedding or None if not found/expired
        """
        if not self.enabled:
            return None
        
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)
        metadata_path = self._get_metadata_path(cache_key)
        
        # Check if cache exists
        if not os.path.exists(cache_path):
            return None
        
        # Check if expired
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                cached_time = datetime.fromisoformat(metadata['timestamp'])
                if datetime.now() - cached_time > timedelta(hours=self.ttl_hours):
                    # Cache expired, delete it
                    os.remove(cache_path)
                    os.remove(metadata_path)
                    return None
        
        # Load and return embedding
        try:
            embedding = np.load(cache_path)
            return embedding
        except Exception:
            return None
    
    def set(self, text: str, embedding: np.ndarray):
        """
        Store embedding in cache
        
        Args:
            text: Input text
            embedding: Embedding array to cache
        """
        if not self.enabled:
            return
        
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)
        metadata_path = self._get_metadata_path(cache_key)
        
        try:
            # Save embedding
            np.save(cache_path, embedding)
            
            # Save metadata
            metadata = {
                'timestamp': datetime.now().isoformat(),
                'text_length': len(text)
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
        except Exception:
            pass  # Fail silently if cache write fails
    
    def clear_expired(self):
        """Remove expired cache entries"""
        if not self.enabled or not os.path.exists(self.cache_dir):
            return
        
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.json'):
                metadata_path = os.path.join(self.cache_dir, filename)
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        cached_time = datetime.fromisoformat(metadata['timestamp'])
                        if datetime.now() - cached_time > timedelta(hours=self.ttl_hours):
                            # Remove both metadata and embedding
                            cache_key = filename.replace('.json', '')
                            cache_path = self._get_cache_path(cache_key)
                            if os.path.exists(cache_path):
                                os.remove(cache_path)
                            os.remove(metadata_path)
                except Exception:
                    continue