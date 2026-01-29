"""
README Analyzer - Parse READMEs and match with repository languages
"""
from typing import Dict, List, Set
from .github_client import GitHubClient
from ..utils.constants import MIN_README_LENGTH, MISMATCH_REPO_THRESHOLD
from ..utils.text_utils import extract_keywords_from_text, clean_text


class ReadmeAnalyzer:
    """Analyzes README files and matches with repo languages"""
    
    def __init__(self, github_client: GitHubClient):
        self.client = github_client
    
    def analyze_readmes(self, enriched_repos: List[Dict]) -> Dict:
        """
        Analyze READMEs across all repositories
        
        Args:
            enriched_repos: List of enriched repository data
            
        Returns:
            README analysis results
        """
        repos_with_readme = 0
        repos_without_readme = 0
        repos_with_short_readme = 0
        repos_with_language_mismatch = 0
        
        readme_enhanced_repos = []
        
        for repo_data in enriched_repos:
            readme_info = self._analyze_single_readme(repo_data)
            
            # Merge README info into repo data
            enhanced_repo = {**repo_data, **readme_info}
            readme_enhanced_repos.append(enhanced_repo)
            
            # Aggregate stats
            if readme_info["has_readme"]:
                repos_with_readme += 1
                
                if readme_info["readme_length"] < MIN_README_LENGTH:
                    repos_with_short_readme += 1
            else:
                repos_without_readme += 1
            
            if readme_info["has_language_mismatch"]:
                repos_with_language_mismatch += 1
        
        total_repos = len(enriched_repos)
        readme_presence_ratio = repos_with_readme / total_repos if total_repos > 0 else 0.0
        
        # Global mismatch flag (only if multiple repos have mismatch)
        has_global_mismatch = repos_with_language_mismatch >= MISMATCH_REPO_THRESHOLD
        
        return {
            "readmeStats": {
                "repos_with_readme": repos_with_readme,
                "repos_without_readme": repos_without_readme,
                "repos_with_short_readme": repos_with_short_readme,
                "readme_presence_ratio": readme_presence_ratio,
            },
            "languageMatchStats": {
                "repos_with_mismatch": repos_with_language_mismatch,
                "has_global_mismatch": has_global_mismatch,
            },
            "enhancedRepositories": readme_enhanced_repos,
        }
    
    def _analyze_single_readme(self, repo_data: Dict) -> Dict:
        """
        Analyze README for a single repository
        
        Args:
            repo_data: Enriched repository data
            
        Returns:
            README analysis for this repo
        """
        owner = repo_data["owner"]
        repo_name = repo_data["name"]
        repo_languages = repo_data.get("languages", {})
        
        # Fetch README
        readme_content = self.client.get_repo_readme(owner, repo_name)
        
        has_readme = readme_content is not None and len(readme_content) > 0
        readme_length = len(readme_content) if readme_content else 0
        
        # Extract keywords if README exists
        detected_languages = set()
        has_language_mismatch = False
        
        if has_readme and readme_content:
            cleaned_readme = clean_text(readme_content)
            detected_languages = extract_keywords_from_text(cleaned_readme)
            
            # Check for language mismatch
            has_language_mismatch = self._check_language_mismatch(
                detected_languages, 
                repo_languages
            )
        
        return {
            "has_readme": has_readme,
            "readme_length": readme_length,
            "readme_detected_languages": list(detected_languages),
            "has_language_mismatch": has_language_mismatch,
        }
    
    def _check_language_mismatch(
        self, 
        detected_languages: Set[str], 
        repo_languages: Dict[str, int]
    ) -> bool:
        """
        Check if README languages match repository languages
        
        Args:
            detected_languages: Languages detected from README
            repo_languages: Languages from GitHub API (name -> bytes)
            
        Returns:
            True if there's a mismatch
        """
        if not detected_languages or not repo_languages:
            return False
        
        # Get top 3 repo languages by bytes
        top_repo_languages = set(
            sorted(repo_languages.keys(), key=lambda k: repo_languages[k], reverse=True)[:3]
        )
        
        # Check if any detected language is in top repo languages
        for detected_lang in detected_languages:
            if detected_lang in top_repo_languages:
                return False  # Found a match, no mismatch
        
        # No matches found = mismatch
        # But only flag if README actually mentions languages
        return True
    
    def get_dominant_languages(self, repo_languages: Dict[str, int], top_n: int = 3) -> List[str]:
        """
        Get the dominant languages from a repository
        
        Args:
            repo_languages: Language -> bytes mapping
            top_n: Number of top languages to return
            
        Returns:
            List of top language names
        """
        if not repo_languages:
            return []
        
        sorted_languages = sorted(
            repo_languages.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return [lang for lang, _ in sorted_languages[:top_n]]