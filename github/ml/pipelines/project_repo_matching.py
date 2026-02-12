"""
Project-Repo Matching Pipeline
Matches resume projects to GitHub repositories using embeddings
"""
from typing import Dict, List, Tuple, Optional
import numpy as np
from ..embeddings.embedding_model import EmbeddingModel
from ..embeddings.embedding_cache import EmbeddingCache
from ..config.ml_config import (
    USE_EMBEDDING_CACHE,
    PROJECT_MATCH_THRESHOLD_HIGH,
    PROJECT_MATCH_THRESHOLD_MEDIUM,
    PROJECT_MATCH_THRESHOLD_LOW
)


class ProjectRepoMatching:
    """Matches resume projects to GitHub repositories"""
    
    def __init__(self):
        """Initialize project matching pipeline"""
        self.embedding_model = EmbeddingModel()  # No args - lazy loads internally
        self.cache = EmbeddingCache() if USE_EMBEDDING_CACHE else None  # Uses default cache_dir
    
    def match_projects_to_repos(
        self,
        projects: List[Dict],
        repositories: List[Dict]
    ) -> List[Dict]:
        """
        Match resume projects to GitHub repositories
        
        Args:
            projects: List of project dicts with 'name' and 'description'
            repositories: List of repo dicts with 'name', 'description', 'readme'
            
        Returns:
            List of matches with similarity scores
        """
        if not projects or not repositories:
            return []
        
        matches = []
        
        for project in projects:
            best_match = self._find_best_match(project, repositories)
            if best_match:
                matches.append(best_match)
        
        return matches
    
    def _find_best_match(
        self,
        project: Dict,
        repositories: List[Dict]
    ) -> Optional[Dict]:
        """
        Find best repository match for a project
        
        Args:
            project: Project dict
            repositories: List of repository dicts
            
        Returns:
            Match result or None
        """
        # Create project text (name + description)
        project_text = self._create_project_text(project)
        
        if not project_text:
            return None
        
        # Get project embedding
        project_embedding = self._get_embedding(project_text)
        
        # Create repo texts and get embeddings
        repo_texts = [self._create_repo_text(r) for r in repositories]
        repo_embeddings = self._get_batch_embeddings(repo_texts)
        
        # Calculate similarities
        similarities = [
            self._compute_cosine_similarity(project_embedding, repo_emb)
            for repo_emb in repo_embeddings
        ]
        
        # Find best match
        max_idx = np.argmax(similarities)
        max_similarity = float(similarities[max_idx])
        
        # Only return if above minimum threshold
        if max_similarity < PROJECT_MATCH_THRESHOLD_LOW:
            return None
        
        matched_repo = repositories[max_idx]
        
        return {
            "project": {
                "name": project.get("name"),
                "description": project.get("description", "")
            },
            "repository": {
                "name": matched_repo.get("name"),
                "full_name": matched_repo.get("full_name"),
                "description": matched_repo.get("description", ""),
                "stars": matched_repo.get("stars", 0)
            },
            "similarity": round(max_similarity, 3),
            "match_strength": self._determine_match_strength(max_similarity),
            "is_strong_match": max_similarity >= PROJECT_MATCH_THRESHOLD_HIGH
        }
    
    def _create_project_text(self, project: Dict) -> str:
        """Create searchable text from project"""
        parts = []
        
        if project.get("name"):
            parts.append(project["name"])
        
        if project.get("description"):
            parts.append(project["description"])
        
        if project.get("technologies"):
            parts.append(" ".join(project["technologies"]))
        
        return " ".join(parts).strip()
    
    def _create_repo_text(self, repo: Dict) -> str:
        """Create searchable text from repository"""
        parts = []
        
        if repo.get("name"):
            parts.append(repo["name"])
        
        if repo.get("description"):
            parts.append(repo["description"])
        
        # Use first 500 chars of README if available
        if repo.get("readme"):
            readme_excerpt = repo["readme"][:500]
            parts.append(readme_excerpt)
        
        # Include detected languages
        if repo.get("readme_detected_languages"):
            parts.append(" ".join(repo["readme_detected_languages"]))
        
        return " ".join(parts).strip()
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding with caching"""
        if self.cache:
            cached = self.cache.get(text)
            if cached is not None:
                return cached
        
        embedding = self.embedding_model.encode(text)  # Returns single embedding for single text
        
        if self.cache:
            self.cache.set(text, embedding)
        
        return embedding
    
    def _get_batch_embeddings(self, texts: List[str]) -> np.ndarray:
        """Get batch embeddings with caching"""
        embeddings = []
        
        for text in texts:
            if self.cache:
                cached = self.cache.get(text)
                if cached is not None:
                    embeddings.append(cached)
                    continue
            
            embedding = self.embedding_model.encode(text)  # Returns single embedding
            
            if self.cache:
                self.cache.set(text, embedding)
            
            embeddings.append(embedding)
        
        return np.array(embeddings)
    
    def _compute_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors"""
        return float(np.dot(vec1, vec2))  # Already normalized in embedding_model
    
    def _determine_match_strength(self, similarity: float) -> str:
        """Determine match strength based on similarity"""
        if similarity >= PROJECT_MATCH_THRESHOLD_HIGH:
            return "STRONG"
        elif similarity >= PROJECT_MATCH_THRESHOLD_MEDIUM:
            return "MODERATE"
        else:
            return "WEAK"