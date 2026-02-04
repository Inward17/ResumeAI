"""
README Clone Detection Pipeline
Compares README similarity with popular repos
"""
from typing import Dict, List, Tuple
from ..inference.similarity_engine import SimilarityEngine
from ..config.ml_config import (
    RED_FLAG_MESSAGES,
    CLONE_VERDICT_UNKNOWN
)


class ReadmeCloneDetection:
    """Pipeline for detecting cloned/template READMEs"""
    
    def __init__(self):
        """Initialize with similarity engine"""
        self.similarity_engine = SimilarityEngine()
    
    def detect_clone(
        self, 
        candidate_readme: str, 
        popular_repos: List[Dict]
    ) -> Dict:
        """
        Detect if README is cloned from popular repos
        
        Args:
            candidate_readme: README text to check
            popular_repos: List of popular repo data with 'readme' field
            
        Returns:
            Dict with similarity, verdict, matched_repo, red_flags
        """
        if not candidate_readme or len(candidate_readme) < 100:
            return {
                "similarity": 0.0,
                "verdict": CLONE_VERDICT_UNKNOWN,
                "matched_repo": None,
                "red_flags": []
            }
        
        if not popular_repos:
            return {
                "similarity": 0.0,
                "verdict": CLONE_VERDICT_UNKNOWN,
                "matched_repo": None,
                "red_flags": []
            }
        
        # Extract READMEs from popular repos
        popular_readmes = [
            repo.get("readme", "") for repo in popular_repos
        ]
        
        # Filter out empty READMEs
        valid_repos = []
        valid_readmes = []
        for repo, readme in zip(popular_repos, popular_readmes):
            if readme and len(readme) >= 100:
                valid_repos.append(repo)
                valid_readmes.append(readme)
        
        if not valid_readmes:
            return {
                "similarity": 0.0,
                "verdict": CLONE_VERDICT_UNKNOWN,
                "matched_repo": None,
                "red_flags": []
            }
        
        # Find maximum similarity
        max_similarity, max_idx = self.similarity_engine.compute_max_similarity(
            candidate_readme,
            valid_readmes
        )
        
        # Get verdict
        verdict = self.similarity_engine.get_verdict(max_similarity)
        
        # Identify matched repo
        matched_repo = None
        if max_idx >= 0:
            matched_repo = {
                "name": valid_repos[max_idx]["name"],
                "owner": valid_repos[max_idx]["owner"],
                "full_name": valid_repos[max_idx]["full_name"],
                "stars": valid_repos[max_idx]["stars"],
                "url": valid_repos[max_idx]["url"]
            }
        
        # Generate red flags
        red_flags = self._generate_red_flags(max_similarity, verdict)
        
        return {
            "similarity": round(max_similarity, 3),
            "verdict": verdict,
            "matched_repo": matched_repo,
            "red_flags": red_flags
        }
    
    def _generate_red_flags(self, similarity: float, verdict: str) -> List[str]:
        """Generate red flags based on similarity and verdict"""
        from ..config.ml_config import (
            CLONE_VERDICT_COPIED,
            CLONE_VERDICT_TEMPLATE,
            SIMILARITY_VERY_HIGH
        )
        
        red_flags = []
        
        if verdict == CLONE_VERDICT_COPIED:
            red_flags.append(RED_FLAG_MESSAGES["readme_highly_similar"])
            red_flags.append(RED_FLAG_MESSAGES["suspicious_clone"])
        elif verdict == CLONE_VERDICT_TEMPLATE:
            red_flags.append(RED_FLAG_MESSAGES["likely_template"])
        
        return red_flags
    
    def batch_detect(
        self,
        repos_with_readmes: List[Dict],
        popular_repos_map: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Batch clone detection for multiple repos
        
        Args:
            repos_with_readmes: List of repos with README text
            popular_repos_map: Dict mapping repo_name -> popular_repos
            
        Returns:
            List of clone detection results
        """
        results = []
        
        for repo in repos_with_readmes:
            repo_name = repo.get("name", "")
            readme = repo.get("readme", "")
            
            # Get popular repos for this repo
            popular_repos = popular_repos_map.get(repo_name, [])
            
            # Detect clone
            detection = self.detect_clone(readme, popular_repos)
            
            results.append({
                "repo_name": repo_name,
                **detection
            })
        
        return results