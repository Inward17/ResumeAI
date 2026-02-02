"""
Unified Verification Service - Orchestrates concurrent verification of GitHub, LinkedIn, and web search
"""
import asyncio
import os
from typing import Dict, Optional, Any
from datetime import datetime

from app.database import db
from app.services.scraper import scrape_linkedin_profiles
from app.services.verifier import verify_profile
from app.services.github_services import (
    GitHubClient,
    RepoAnalyzer,
    ReadmeAnalyzer,
    ScoreEngine
)
from app.models.verification_data_model import (
    VerificationDataModel,
    GitHubDataModel,
    GitHubScoreComponents,
    GitHubScoreBreakdown,
    GitHubRepositoryStats,
    GitHubCommitStats,
    GitHubReadmeStats,
    LinkedInDataModel,
    LinkedInPosition,
    LinkedInEducation,
    LinkedInCertification,
    LinkedInSkill,
    TimePeriod,
    WebSearchDataModel,
    WebSearchResult,
    EducationVerification,
    ExperienceVerification,
    EducationDetail,
    ExperienceDetail,
    VerificationStatusModel,
    MatchScoreModel
)


class VerificationCache:
    """In-memory cache for temporary verification data storage"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def set(self, candidate_id: str, key: str, value: Any):
        """Store a value in cache"""
        if candidate_id not in self._cache:
            self._cache[candidate_id] = {}
        self._cache[candidate_id][key] = value
    
    def get(self, candidate_id: str, key: str = None) -> Any:
        """Retrieve a value from cache"""
        if candidate_id not in self._cache:
            return None
        if key is None:
            return self._cache[candidate_id]
        return self._cache[candidate_id].get(key)
    
    def get_all(self, candidate_id: str) -> Dict:
        """Get all cached data for a candidate"""
        return self._cache.get(candidate_id, {})
    
    def clear(self, candidate_id: str):
        """Clear cache for a candidate"""
        if candidate_id in self._cache:
            del self._cache[candidate_id]
    
    def has_complete_data(self, candidate_id: str) -> bool:
        """Check if all verification data is cached"""
        data = self._cache.get(candidate_id, {})
        return all(key in data for key in ["github", "linkedin", "webSearch"])


class UnifiedVerificationService:
    """Service orchestrating concurrent verification from all sources"""
    
    def __init__(self, db_client=None, github_token: Optional[str] = None):
        self.db = db_client or db
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.cache = VerificationCache()
        
        # Initialize GitHub client
        self.github_client = GitHubClient(self.github_token)
        self.repo_analyzer = RepoAnalyzer(self.github_client)
        self.readme_analyzer = ReadmeAnalyzer(self.github_client)
        self.score_engine = ScoreEngine()
    
    async def run_unified_verification(
        self,
        candidate_id: str,
        github_username: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        profile_data: Optional[dict] = None
    ) -> VerificationDataModel:
        """
        Run all verifications concurrently and store results.
        
        Args:
            candidate_id: Unique ID linking to candidates collection
            github_username: GitHub username to verify
            linkedin_url: LinkedIn profile URL to scrape
            profile_data: Parsed resume/profile data for web verification
            
        Returns:
            Complete verification data model
        """
        # Run all verifications concurrently
        # Using return_exceptions=True so one failure doesn't block others
        tasks = []
        task_names = []
        
        if github_username:
            tasks.append(self._verify_github(candidate_id, github_username))
            task_names.append("github")
        else:
            self.cache.set(candidate_id, "github", None)
        
        if linkedin_url:
            tasks.append(self._verify_linkedin(candidate_id, linkedin_url))
            task_names.append("linkedin")
        else:
            self.cache.set(candidate_id, "linkedin", None)
        
        if profile_data:
            tasks.append(self._verify_web_search(candidate_id, profile_data))
            task_names.append("webSearch")
        else:
            self.cache.set(candidate_id, "webSearch", None)
        
        # Execute all tasks concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Verification error for {task_names[i]}: {result}")
        
        # Build and persist unified verification data
        verification_data = await self._build_and_persist(candidate_id)
        
        # Clear cache after persistence
        self.cache.clear(candidate_id)
        
        return verification_data
    
    async def _verify_github(self, candidate_id: str, username: str) -> dict:
        """Run GitHub verification in thread (blocking API calls)"""
        try:
            # Run blocking GitHub API calls in thread pool
            result = await asyncio.to_thread(
                self._github_analysis_sync, username
            )
            
            # Cache result
            self.cache.set(candidate_id, "github", result)
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "score": 0,
                "redFlags": ["GitHub verification failed"]
            }
            self.cache.set(candidate_id, "github", error_result)
            return error_result
    
    def _github_analysis_sync(self, username: str) -> dict:
        """Synchronous GitHub analysis"""
        try:
            repos = self.github_client.get_user_repos(username)
            
            if not repos:
                return {
                    "success": False,
                    "error": f"No repositories found for '{username}'",
                    "score": 0,
                    "redFlags": ["No repositories found"]
                }
            
            repo_analysis = self.repo_analyzer.analyze_repos(username, repos)
            readme_analysis = self.readme_analyzer.analyze_readmes(
                repo_analysis["enrichedRepositories"]
            )
            score_result = self.score_engine.compute_score(repo_analysis, readme_analysis)
            
            return {
                "success": True,
                "username": username,
                "score": score_result["score"],
                "redFlags": score_result["redFlags"],
                "components": score_result["components"],
                "breakdown": score_result["breakdown"],
                "repositoryStats": repo_analysis["repositoryStats"],
                "commitStats": repo_analysis["commitStats"],
                "readmeStats": readme_analysis["readmeStats"]
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "score": 0,
                "redFlags": ["User not found"]
            }
    
    async def _verify_linkedin(self, candidate_id: str, linkedin_url: str) -> dict:
        """Run LinkedIn scraping"""
        try:
            # LinkedIn scraping via Apify
            result = await scrape_linkedin_profiles([linkedin_url])
            
            if result.get("status") == "success" and result.get("data"):
                linkedin_data = result["data"][0] if result["data"] else {}
                self.cache.set(candidate_id, "linkedin", linkedin_data)
                return linkedin_data
            else:
                error_result = {"error": "LinkedIn scraping failed", "status": "failed"}
                self.cache.set(candidate_id, "linkedin", error_result)
                return error_result
                
        except Exception as e:
            error_result = {"error": str(e), "status": "failed"}
            self.cache.set(candidate_id, "linkedin", error_result)
            return error_result
    
    async def _verify_web_search(self, candidate_id: str, profile_data: dict) -> dict:
        """Run web search verification"""
        try:
            result = await verify_profile(profile_data)
            self.cache.set(candidate_id, "webSearch", result)
            return result
            
        except Exception as e:
            error_result = {"error": str(e), "status": "failed"}
            self.cache.set(candidate_id, "webSearch", error_result)
            return error_result
    
    async def _build_and_persist(self, candidate_id: str) -> VerificationDataModel:
        """Build verification model from cache and persist to MongoDB"""
        cached = self.cache.get_all(candidate_id)
        now = datetime.utcnow()
        
        # Build GitHub data model
        github_data = None
        github_status = "pending"
        if cached.get("github"):
            gh = cached["github"]
            if gh.get("success"):
                github_status = "verified"
                github_data = GitHubDataModel(
                    username=gh.get("username"),
                    success=True,
                    score=gh.get("score", 0),
                    redFlags=gh.get("redFlags", []),
                    components=GitHubScoreComponents(**gh["components"]) if gh.get("components") else None,
                    breakdown=GitHubScoreBreakdown(**gh["breakdown"]) if gh.get("breakdown") else None,
                    repositoryStats=GitHubRepositoryStats(**gh["repositoryStats"]) if gh.get("repositoryStats") else None,
                    commitStats=GitHubCommitStats(**gh["commitStats"]) if gh.get("commitStats") else None,
                    readmeStats=GitHubReadmeStats(**gh["readmeStats"]) if gh.get("readmeStats") else None,
                    verifiedAt=now
                )
            else:
                github_status = "unverified"
                github_data = GitHubDataModel(
                    success=False,
                    redFlags=gh.get("redFlags", []),
                    verifiedAt=now
                )
        
        # Build LinkedIn data model
        linkedin_data = None
        linkedin_status = "pending"
        if cached.get("linkedin") and not cached["linkedin"].get("error"):
            li = cached["linkedin"]
            linkedin_status = "verified"
            
            # Parse positions
            positions = []
            for pos in li.get("positions", []) or li.get("experiences", []):
                positions.append(LinkedInPosition(
                    title=pos.get("title"),
                    companyName=pos.get("companyName") or pos.get("subtitle"),
                    locationName=pos.get("locationName"),
                    description=pos.get("description"),
                    totalDuration=pos.get("totalDuration"),
                    companyLogo=pos.get("companyLogo"),
                    companyUrl=pos.get("companyUrl"),
                    timePeriod=TimePeriod(**pos["timePeriod"]) if pos.get("timePeriod") else None
                ))
            
            # Parse educations
            educations = []
            for edu in li.get("educations", []):
                educations.append(LinkedInEducation(
                    schoolName=edu.get("schoolName") or edu.get("title"),
                    degreeName=edu.get("degreeName"),
                    fieldOfStudy=edu.get("fieldOfStudy"),
                    timePeriod=TimePeriod(**edu["timePeriod"]) if edu.get("timePeriod") else None
                ))
            
            # Parse certifications
            certifications = []
            for cert in li.get("certifications", []):
                certifications.append(LinkedInCertification(
                    name=cert.get("name"),
                    authority=cert.get("authority"),
                    issuer=cert.get("issuer")
                ))
            
            # Parse skills
            skills = []
            for skill in li.get("skills", []):
                if isinstance(skill, dict):
                    skills.append(LinkedInSkill(
                        name=skill.get("name"),
                        endorsements=skill.get("endorsements", 0)
                    ))
                elif isinstance(skill, str):
                    skills.append(LinkedInSkill(name=skill))
            
            linkedin_data = LinkedInDataModel(
                profileId=li.get("profileId") or li.get("id"),
                publicIdentifier=li.get("publicIdentifier"),
                profileUrl=li.get("profileUrl") or li.get("url"),
                verifiedAt=now,
                firstName=li.get("firstName"),
                lastName=li.get("lastName"),
                headline=li.get("headline"),
                summary=li.get("summary"),
                location=li.get("location") or li.get("geoLocation"),
                countryCode=li.get("countryCode"),
                pictureUrl=li.get("pictureUrl") or li.get("profilePicture"),
                positions=positions,
                educations=educations,
                certifications=certifications,
                skills=skills
            )
        elif cached.get("linkedin"):
            linkedin_status = "unverified"
        
        # Build web search data model
        web_search_data = None
        web_status = "pending"
        if cached.get("webSearch") and not cached["webSearch"].get("error"):
            ws = cached["webSearch"]
            web_status = "verified"
            
            # Build education details
            edu_details = []
            if ws.get("education") and ws["education"].get("details"):
                for detail in ws["education"]["details"]:
                    edu_details.append(EducationDetail(
                        college=detail.get("college"),
                        verified=detail.get("verified", False),
                        top_result=detail.get("top_result"),
                        title=detail.get("title"),
                        snippet=detail.get("snippet"),
                        score=detail.get("score", 0),
                        tag=detail.get("tag")
                    ))
            
            # Build experience details
            exp_details = []
            if ws.get("experience") and ws["experience"].get("details"):
                for detail in ws["experience"]["details"]:
                    exp_details.append(ExperienceDetail(
                        company=detail.get("company"),
                        position=detail.get("position"),
                        verified=detail.get("verified", False),
                        top_result=detail.get("top_result"),
                        title=detail.get("title"),
                        snippet=detail.get("snippet"),
                        score=detail.get("score", 0),
                        tag=detail.get("tag")
                    ))
            
            web_search_data = WebSearchDataModel(
                status="success",
                verifiedAt=now,
                results=[WebSearchResult(
                    profile_url=ws.get("profile_url"),
                    education=EducationVerification(
                        average_score=ws.get("education", {}).get("average_score", 0),
                        overall_tag=ws.get("education", {}).get("overall_tag"),
                        details=edu_details
                    ) if ws.get("education") else None,
                    experience=ExperienceVerification(
                        average_score=ws.get("experience", {}).get("average_score", 0),
                        overall_tag=ws.get("experience", {}).get("overall_tag"),
                        details=exp_details
                    ) if ws.get("experience") else None
                )]
            )
        elif cached.get("webSearch"):
            web_status = "unverified"
        
        # Build verification status
        verification_status = VerificationStatusModel(
            linkedin=linkedin_status,
            github=github_status,
            webCheck=web_status,
            discrepancies=[]  # TODO: Compute discrepancies
        )
        
        # Calculate match scores
        match_score = self._calculate_match_scores(github_data, linkedin_data, web_search_data)
        
        # Create verification data model
        verification_data = VerificationDataModel(
            candidateId=candidate_id,
            createdAt=now,
            updatedAt=now,
            githubData=github_data,
            linkedinData=linkedin_data,
            webSearchData=web_search_data,
            verificationStatus=verification_status,
            matchScore=match_score
        )
        
        # Persist to MongoDB
        await self._persist_to_db(verification_data)
        
        return verification_data
    
    def _calculate_match_scores(
        self,
        github_data: Optional[GitHubDataModel],
        linkedin_data: Optional[LinkedInDataModel],
        web_search_data: Optional[WebSearchDataModel]
    ) -> MatchScoreModel:
        """Calculate credibility match scores"""
        experience_match = 0
        skills_match = 0
        
        # Experience verification score from web search
        if web_search_data and web_search_data.results:
            for result in web_search_data.results:
                if result.experience:
                    experience_match = max(experience_match, result.experience.average_score)
        
        # Skills credibility from GitHub score
        if github_data and github_data.success:
            skills_match = github_data.score
        
        # Overall credibility is weighted average
        # GitHub (30%) + LinkedIn presence (20%) + Web verification (50%)
        overall = 0
        weights = 0
        
        if github_data and github_data.success:
            overall += github_data.score * 0.3
            weights += 0.3
        
        if linkedin_data and linkedin_data.profileId:
            overall += 100 * 0.2  # Full score for valid LinkedIn
            weights += 0.2
        
        if web_search_data and web_search_data.results:
            avg_web = experience_match
            overall += avg_web * 0.5
            weights += 0.5
        
        overall_credibility = round(overall / weights, 2) if weights > 0 else 0
        
        return MatchScoreModel(
            experienceMatch=experience_match,
            skillsMatch=skills_match,
            overallCredibility=overall_credibility
        )
    
    async def _persist_to_db(self, verification_data: VerificationDataModel):
        """Persist verification data to MongoDB"""
        doc = verification_data.to_mongo_dict()
        
        await self.db.verification_data.update_one(
            {"candidateId": verification_data.candidateId},
            {"$set": doc},
            upsert=True
        )


# Singleton instance
unified_verification_service = UnifiedVerificationService()
