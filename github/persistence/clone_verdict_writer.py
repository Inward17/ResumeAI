"""
Clone Verdict Writer - Persist Phase-2 deep analysis results
Extends existing persistence layer with clone detection data
"""
from typing import Dict, List, Optional
from datetime import datetime


class CloneVerdictWriter:
    """Writes clone detection results to database"""
    
    def __init__(self, db_client=None):
        """
        Initialize writer with database client
        
        Args:
            db_client: Database client (MongoDB, PostgreSQL, etc.)
        """
        self.db = db_client
    
    def write_deep_analysis(
        self,
        user_id: str,
        username: str,
        deep_results: List[Dict],
        clone_penalty: int
    ) -> Dict:
        """
        Write deep analysis results to verification_data
        
        Args:
            user_id: User identifier
            username: GitHub username
            deep_results: List of deep analysis results
            clone_penalty: Total clone detection penalty
            
        Returns:
            Structured data for verification_data.deepAnalysis
        """
        # Build deep analysis structure
        deep_analysis_data = {
            "username": username,
            "analyzedAt": datetime.utcnow().isoformat(),
            "clonePenalty": clone_penalty,
            "repositories": self._format_deep_repos(deep_results)
        }
        
        # If database client available, persist
        if self.db:
            self._persist_to_database(user_id, deep_analysis_data)
        
        return deep_analysis_data
    
    def _format_deep_repos(self, deep_results: List[Dict]) -> List[Dict]:
        """
        Format deep analysis results for storage
        Only keeps essential fields - no full embeddings
        """
        formatted = []
        
        for result in deep_results:
            clone_detection = result.get("clone_detection", {})
            commit_stats = result.get("commit_stats", {})
            
            # Extract matched repo info (minimal)
            matched_repo = clone_detection.get("matched_repo")
            matched_repo_summary = None
            if matched_repo:
                matched_repo_summary = {
                    "full_name": matched_repo.get("full_name"),
                    "stars": matched_repo.get("stars"),
                    "url": matched_repo.get("url")
                }
            
            formatted_repo = {
                "repo_name": result.get("repo_name"),
                "owner": result.get("owner"),
                
                # Clone detection results
                "clone_similarity": clone_detection.get("similarity", 0.0),
                "clone_verdict": clone_detection.get("verdict", "UNKNOWN"),
                "matched_repo": matched_repo_summary,
                
                # Commit stats
                "total_commits": commit_stats.get("total_commits", 0),
                "is_dump_pattern": commit_stats.get("is_dump_pattern", False),
                
                # Red flags
                "red_flags": result.get("red_flags", [])
            }
            
            formatted.append(formatted_repo)
        
        return formatted
    
    def _persist_to_database(self, user_id: str, deep_analysis_data: Dict):
        """
        Persist to database
        
        Args:
            user_id: User identifier
            deep_analysis_data: Deep analysis data
        """
        # Example for MongoDB:
        # self.db.verification_data.update_one(
        #     {"userId": user_id},
        #     {"$set": {"deepAnalysis": deep_analysis_data}},
        #     upsert=True
        # )
        
        # Actual implementation depends on database type
        pass
    
    def get_deep_analysis(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve deep analysis for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Deep analysis data or None
        """
        if not self.db:
            return None
        
        # Example implementation:
        # result = self.db.verification_data.find_one(
        #     {"userId": user_id},
        #     {"deepAnalysis": 1}
        # )
        # return result.get("deepAnalysis") if result else None
        
        return None