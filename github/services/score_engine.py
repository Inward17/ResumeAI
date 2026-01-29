"""
Score Engine - Compute final GitHub ownership score
Applies weights, penalties, and generates red flags
"""
from typing import Dict, List
from ..utils.constants import (
    WEIGHTS,
    RED_FLAG_PENALTY_MAX,
    RED_FLAGS,
    MIN_COMMITS_PER_REPO,
    COMMIT_DUMP_RATIO,
)


class ScoreEngine:
    """Computes GitHub ownership score and identifies red flags"""
    
    def compute_score(
        self,
        repo_analysis: Dict,
        readme_analysis: Dict
    ) -> Dict:
        """
        Compute final ownership score
        
        Args:
            repo_analysis: Results from RepoAnalyzer
            readme_analysis: Results from ReadmeAnalyzer
            
        Returns:
            Score, red flags, and component breakdown
        """
        # Extract statistics
        repo_stats = repo_analysis["repositoryStats"]
        commit_stats = repo_analysis["commitStats"]
        commit_spread = repo_analysis["commitSpread"]
        oss_contributions = repo_analysis["ossContributions"]
        trivial_repos = repo_analysis["trivialRepos"]
        repos_dump_pattern = repo_analysis["reposDumpPattern"]
        
        readme_stats = readme_analysis["readmeStats"]
        language_match_stats = readme_analysis["languageMatchStats"]
        
        # Calculate component scores
        original_ratio_score = self._score_original_ratio(repo_stats["original_ratio"])
        commit_depth_score = self._score_commit_depth(commit_stats)
        readme_presence_score = self._score_readme_presence(readme_stats)
        language_match_score = self._score_language_match(language_match_stats)
        oss_bonus = self._score_oss_contributions(oss_contributions)
        
        # Sum component scores
        raw_score = (
            original_ratio_score +
            commit_depth_score +
            readme_presence_score +
            language_match_score +
            oss_bonus
        )
        
        # Identify red flags
        red_flags = self._identify_red_flags(
            repo_stats,
            commit_stats,
            commit_spread,
            readme_stats,
            language_match_stats,
            trivial_repos,
            repos_dump_pattern
        )
        
        # Apply penalties
        penalty = self._calculate_penalty(red_flags)
        final_score = max(0, min(100, raw_score - penalty))
        
        return {
            "score": round(final_score, 1),
            "redFlags": red_flags,
            "components": {
                "original_ratio": round(original_ratio_score, 1),
                "commit_depth": round(commit_depth_score, 1),
                "readme_presence": round(readme_presence_score, 1),
                "language_match": round(language_match_score, 1),
                "oss_bonus": round(oss_bonus, 1),
                "penalty": round(penalty, 1),
            },
            "breakdown": {
                "raw_score": round(raw_score, 1),
                "total_penalty": round(penalty, 1),
                "final_score": round(final_score, 1),
            }
        }
    
    def _score_original_ratio(self, original_ratio: float) -> float:
        """
        Score based on original vs forked repository ratio
        Weight: 30 points
        """
        return original_ratio * WEIGHTS["original_repo_ratio"]
    
    def _score_commit_depth(self, commit_stats: Dict) -> float:
        """
        Score based on commit depth and activity
        Weight: 25 points
        """
        avg_commits = commit_stats["average_per_repo"]
        
        # Scoring scale:
        # 0-5 commits: Low (0-10 points)
        # 5-20 commits: Medium (10-18 points)
        # 20-50 commits: Good (18-23 points)
        # 50+ commits: Excellent (23-25 points)
        
        if avg_commits >= 50:
            return WEIGHTS["commit_depth"]
        elif avg_commits >= 20:
            return WEIGHTS["commit_depth"] * 0.92
        elif avg_commits >= 10:
            return WEIGHTS["commit_depth"] * 0.72
        elif avg_commits >= 5:
            return WEIGHTS["commit_depth"] * 0.40
        else:
            return WEIGHTS["commit_depth"] * 0.20
    
    def _score_readme_presence(self, readme_stats: Dict) -> float:
        """
        Score based on README presence and quality
        Weight: 15 points
        """
        readme_ratio = readme_stats["readme_presence_ratio"]
        return readme_ratio * WEIGHTS["readme_presence"]
    
    def _score_language_match(self, language_match_stats: Dict) -> float:
        """
        Score based on README-language consistency
        Weight: 15 points
        """
        has_global_mismatch = language_match_stats["has_global_mismatch"]
        
        if has_global_mismatch:
            return WEIGHTS["readme_language_match"] * 0.3
        else:
            return WEIGHTS["readme_language_match"]
    
    def _score_oss_contributions(self, oss_count: int) -> float:
        """
        Bonus for OSS contributions
        Weight: 10 points
        """
        # Scoring scale:
        # 0 contributions: 0 points
        # 1-2 contributions: 5 points
        # 3+ contributions: 10 points
        
        if oss_count >= 3:
            return WEIGHTS["oss_contribution_bonus"]
        elif oss_count >= 1:
            return WEIGHTS["oss_contribution_bonus"] * 0.5
        else:
            return 0
    
    def _identify_red_flags(
        self,
        repo_stats: Dict,
        commit_stats: Dict,
        commit_spread: Dict,
        readme_stats: Dict,
        language_match_stats: Dict,
        trivial_repos: int,
        repos_dump_pattern: int
    ) -> List[str]:
        """
        Identify red flags in the profile
        """
        flags = []
        
        total_repos = repo_stats["total"]
        
        # Flag 1: Mostly forked repositories
        if repo_stats["original_ratio"] < 0.4:
            flags.append(RED_FLAGS["mostly_forked"])
        
        # Flag 2: Low commit depth
        if commit_stats["average_per_repo"] < MIN_COMMITS_PER_REPO:
            flags.append(RED_FLAGS["low_commit_depth"])
        
        # Flag 3: Commit dump pattern
        if commit_spread["is_dump_pattern"] or repos_dump_pattern >= 2:
            flags.append(RED_FLAGS["commit_dump"])
        
        # Flag 4: Missing READMEs
        if readme_stats["readme_presence_ratio"] < 0.5:
            flags.append(RED_FLAGS["missing_readme"])
        
        # Flag 5: Tech stack mismatch
        if language_match_stats["has_global_mismatch"]:
            flags.append(RED_FLAGS["tech_stack_mismatch"])
        
        # Flag 6: Too many trivial repos
        if total_repos > 0 and (trivial_repos / total_repos) > 0.4:
            flags.append(RED_FLAGS["trivial_repos"])
        
        return flags
    
    def _calculate_penalty(self, red_flags: List[str]) -> float:
        """
        Calculate total penalty from red flags
        Capped at RED_FLAG_PENALTY_MAX
        """
        # Each flag is worth 5 points penalty
        penalty_per_flag = 5
        total_penalty = len(red_flags) * penalty_per_flag
        
        return min(total_penalty, RED_FLAG_PENALTY_MAX)