"""
GitHub Writer - Persist analysis results to verification_data
Writes to verification_data.githubData without creating new collections
"""
from typing import Dict, Optional
from datetime import datetime


class GitHubWriter:
    """Writes GitHub analysis data to database"""
    
    def __init__(self, db_client=None):
        """
        Initialize writer with database client
        
        Args:
            db_client: Database client (MongoDB, etc.)
        """
        self.db = db_client
    
    def write_github_data(
        self,
        user_id: str,
        username: str,
        score_result: Dict,
        repo_analysis: Dict,
        readme_analysis: Dict
    ) -> Dict:
        """
        Write GitHub analysis to verification_data.githubData
        
        Args:
            user_id: User identifier
            username: GitHub username
            score_result: Score and red flags from ScoreEngine
            repo_analysis: Repository analysis results
            readme_analysis: README analysis results
            
        Returns:
            Structured data for verification_data.githubData
        """
        enhanced_repos = readme_analysis["enhancedRepositories"]
        
        # Build the githubData structure
        github_data = {
            "username": username,
            "analyzedAt": datetime.utcnow().isoformat(),
            
            # Profile-level scores and flags
            "score": score_result["score"],
            "redFlags": score_result["redFlags"],
            "scoreComponents": score_result["components"],
            
            # Repository statistics
            "repositoryStats": repo_analysis["repositoryStats"],
            "commitStats": repo_analysis["commitStats"],
            "readmeStats": readme_analysis["readmeStats"],
            "languageMatchStats": readme_analysis["languageMatchStats"],
            
            # OSS contributions
            "ossContributions": repo_analysis["ossContributions"],
            
            # Enhanced repository list (enriched with all signals)
            "repositories": self._format_repositories(enhanced_repos),
        }
        
        # If database client is available, write to DB
        if self.db:
            self._persist_to_database(user_id, github_data)
        
        return github_data
    
    def _format_repositories(self, enhanced_repos: list) -> list:
        """
        Format enhanced repositories for storage
        Only keeps essential fields to reduce storage
        """
        formatted_repos = []
        
        for repo in enhanced_repos:
            formatted_repo = {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "owner": repo["owner"],
                "description": repo.get("description", ""),
                
                # Ownership signals
                "is_fork": repo["is_fork"],
                "is_original": repo["is_original"],
                "is_oss_contribution": repo["is_oss_contribution"],
                
                # Commit signals
                "commit_count": repo["commit_count"],
                "has_dump_pattern": repo["has_dump_pattern"],
                
                # README signals
                "has_readme": repo["has_readme"],
                "readme_length": repo.get("readme_length", 0),
                "has_language_mismatch": repo.get("has_language_mismatch", False),
                "readme_detected_languages": repo.get("readme_detected_languages", []),
                
                # Metadata
                "languages": repo.get("languages", {}),
                "stars": repo.get("stars", 0),
                "forks": repo.get("forks", 0),
                "is_trivial": repo.get("is_trivial", False),
                
                # Dates
                "created_at": repo.get("created_at", ""),
                "updated_at": repo.get("updated_at", ""),
            }
            
            formatted_repos.append(formatted_repo)
        
        return formatted_repos
    
    def _persist_to_database(self, user_id: str, github_data: Dict):
        """
        Persist to database (implementation depends on DB type)
        
        Args:
            user_id: User identifier
            github_data: Structured GitHub data
        """
        # Example for MongoDB:
        # self.db.verification_data.update_one(
        #     {"userId": user_id},
        #     {"$set": {"githubData": github_data}},
        #     upsert=True
        # )
        
        # This is a placeholder - actual implementation depends on:
        # - Database type (MongoDB, PostgreSQL, etc.)
        # - Schema structure
        # - Whether verification_data is a collection or embedded document
        
        pass
    
    def get_github_data(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve GitHub data for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            GitHub data or None if not found
        """
        if not self.db:
            return None
        
        # Example implementation:
        # result = self.db.verification_data.find_one(
        #     {"userId": user_id},
        #     {"githubData": 1}
        # )
        # return result.get("githubData") if result else None
        
        return None