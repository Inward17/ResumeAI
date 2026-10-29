"""
Unified Verification Service - Orchestrates concurrent verification of GitHub, LinkedIn, and web search
"""
import asyncio
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from rapidfuzz import fuzz

from app.database import db
from app.services.linkedinScraper import scrape_linkedin_profiles
from app.services.verifier import verify_profile, _clean_company_name, _clean_education_name
from app.services.github_services_v2 import verify_github, GitHubVerificationResult
from app.models.verification_data_model import (
    VerificationDataModel,
    GitHubDataModel,
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
    MatchScoreModel,
    Discrepancy,
)

# Fuzzy score (0-100) at which a resume entry counts as present on LinkedIn
LINKEDIN_MATCH_THRESHOLD = 80


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
    
    async def run_unified_verification(
        self,
        candidate_id: str,
        github_username: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        profile_data: Optional[dict] = None,
        parsed_resume: Optional[dict] = None,
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
        # Kept so LinkedIn data can be compared with the resume's claims
        self.cache.set(candidate_id, "resume", parsed_resume or {})
        
        if github_username:
            # Pass the full parsed resume (not just the web-search stub)
            # so that projects reach the resume→repo matching stage.
            tasks.append(self._verify_github(candidate_id, github_username, parsed_resume))
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
    
    async def _verify_github(self, candidate_id: str, username: str, parsed_resume: Optional[dict] = None) -> dict:
        """Run GitHub verification using the new async pipeline"""
        try:
            # Build a parsed_resume dict suitable for verify_github
            resume_for_github = parsed_resume or {}
            # Ensure github_username is present in the resume data
            if "github_username" not in resume_for_github:
                resume_for_github = {**resume_for_github, "github_username": username}
            
            # Run the async verification pipeline directly
            result: GitHubVerificationResult = await verify_github(
                candidate_id=candidate_id,
                parsed_resume=resume_for_github,
            )
            
            # Cache the result object
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
        gh_cached = cached.get("github")
        if gh_cached is not None:
            # Handle new GitHubVerificationResult object (duck-type check)
            if hasattr(gh_cached, 'to_mongo_dict'):
                gh = gh_cached
                if gh.success:
                    github_status = "verified"
                    
                    github_data = GitHubDataModel(
                        username=gh.username,
                        success=True,
                        score=gh.score100,
                        score100=gh.score100,
                        score40=gh.score40,
                        confidenceLevel=gh.confidenceLevel,
                        redFlags=gh.redFlags or [],
                        verifiedAt=now,
                        # Store the full v2 result as a dict for rich data
                        github_v2_data=gh.to_mongo_dict(),
                    )
                else:
                    github_status = "unverified"
                    github_data = GitHubDataModel(
                        success=False,
                        redFlags=gh.redFlags or [],
                        verifiedAt=now
                    )
            # Handle legacy dict format (from error path)
            elif isinstance(gh_cached, dict):
                gh = gh_cached
                if gh.get("success"):
                    github_status = "verified"
                    github_data = GitHubDataModel(
                        username=gh.get("username"),
                        success=True,
                        score=gh.get("score", 0),
                        redFlags=gh.get("redFlags", []),
                        verifiedAt=now,
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
        linkedin_match: Optional[float] = None
        discrepancies: List[Discrepancy] = []
        if cached.get("linkedin") and not cached["linkedin"].get("error"):
            li = cached["linkedin"]
            
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
            # A scraped profile only counts as verified if it agrees with the resume
            linkedin_match, discrepancies = _compare_linkedin_with_resume(
                linkedin_data, cached.get("resume") or {}
            )
            linkedin_status = "verified" if linkedin_match is not None and linkedin_match >= 60 else "unverified"
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
                    # verify_profile() returns "education"/"experience" — these were
                    # previously read from non-existent keys, so web checks never counted
                    education=EducationVerification(
                        average_score=ws["education"].get("average_score", 0),
                        overall_tag=ws["education"].get("overall_tag"),
                        details=edu_details
                    ) if edu_details else None,
                    experience=ExperienceVerification(
                        average_score=ws["experience"].get("average_score", 0),
                        overall_tag=ws["experience"].get("overall_tag"),
                        details=exp_details
                    ) if exp_details else None
                )]
            )
        elif cached.get("webSearch"):
            web_status = "unverified"
        
        # Build verification status
        verification_status = VerificationStatusModel(
            linkedin=linkedin_status,
            github=github_status,
            webCheck=web_status,
            discrepancies=discrepancies,
        )
        
        # Calculate match scores
        match_score = self._calculate_match_scores(github_data, linkedin_match, web_search_data)
        
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
        linkedin_match: Optional[float],
        web_search_data: Optional[WebSearchDataModel]
    ) -> MatchScoreModel:
        """Calculate credibility match scores.

        Each source only takes part in the weighted average when it actually
        had something to check, so a missing source never drags the score down.
        """
        experience_match = 0
        skills_match = 0
        web_scores: List[float] = []
        
        # Experience/education verification scores from web search
        if web_search_data and web_search_data.results:
            for result in web_search_data.results:
                if result.experience:
                    experience_match = max(experience_match, result.experience.average_score)
                    web_scores.append(result.experience.average_score)
                if result.education:
                    web_scores.append(result.education.average_score)
        
        # Skills credibility from GitHub score
        if github_data and github_data.success:
            skills_match = github_data.score100 if github_data.score100 else github_data.score
        
        # Overall credibility is weighted average
        # GitHub (50%) + LinkedIn presence (20%) + Web verification (30%)
        overall = 0
        weights = 0
        
        github_score = github_data.score100 if (github_data and github_data.score100) else (github_data.score if github_data else 0)
        if github_data and github_data.success:
            overall += github_score * 0.5
            weights += 0.5
        
        # LinkedIn scores by agreement with the resume, not mere existence
        if linkedin_match is not None:
            overall += linkedin_match * 0.2
            weights += 0.2
        
        if web_scores:
            avg_web = sum(web_scores) / len(web_scores)
            overall += avg_web * 0.3
            weights += 0.3
        
        overall_credibility = round(overall / weights, 2) if weights > 0 else 0
        
        return MatchScoreModel(
            experienceMatch=experience_match,
            skillsMatch=skills_match,
            linkedinMatch=round(linkedin_match, 2) if linkedin_match is not None else 0,
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


def _resume_companies(parsed: dict) -> List[str]:
    companies = [c for c in (parsed.get("company") or []) if isinstance(c, str) and c.strip()]
    if companies:
        return companies
    # Older parses have no "company" list — fall back to "<role> at <company>" lines
    found = []
    for exp in parsed.get("experience") or []:
        if isinstance(exp, str) and " at " in exp:
            found.append(exp.split(" at ", 1)[1].split("(")[0].split("|")[0].split(" - ")[0].strip())
    return [c for c in found if c]


def _best_ratio(value: str, candidates: List[str]) -> float:
    return max((fuzz.token_set_ratio(value.lower(), c.lower()) for c in candidates if c), default=0)


def _compare_linkedin_with_resume(
    linkedin: LinkedInDataModel, parsed: dict
) -> Tuple[Optional[float], List[Discrepancy]]:
    """
    Compare the scraped LinkedIn profile with the resume's claims.

    Returns (match 0-100, discrepancies). Match is the share of checks that
    agree: candidate name, each resume company and each resume university.
    None when there was nothing to compare.
    """
    checks: List[bool] = []
    discrepancies: List[Discrepancy] = []

    resume_name = ((parsed.get("personal_info") or {}).get("full_name") or "").strip()
    linkedin_name = " ".join(filter(None, [linkedin.firstName, linkedin.lastName])).strip()
    if resume_name and linkedin_name:
        ok = fuzz.token_set_ratio(resume_name.lower(), linkedin_name.lower()) >= LINKEDIN_MATCH_THRESHOLD
        checks.append(ok)
        if not ok:
            discrepancies.append(Discrepancy(
                field="name", resumeValue=resume_name, linkedinValue=linkedin_name,
                severity="critical", description="Name on resume differs from LinkedIn profile",
            ))

    linkedin_companies = [_clean_company_name(p.companyName) for p in linkedin.positions if p.companyName]
    for company in _resume_companies(parsed):
        ok = _best_ratio(_clean_company_name(company), linkedin_companies) >= LINKEDIN_MATCH_THRESHOLD
        checks.append(ok)
        if not ok:
            discrepancies.append(Discrepancy(
                field="experience", resumeValue=company, linkedinValue=None, severity="major",
                description="Company on resume not found in LinkedIn experience",
            ))

    linkedin_schools = [_clean_education_name(e.schoolName) for e in linkedin.educations if e.schoolName]
    for school in parsed.get("university") or []:
        if not isinstance(school, str) or not school.strip():
            continue
        ok = _best_ratio(_clean_education_name(school), linkedin_schools) >= LINKEDIN_MATCH_THRESHOLD
        checks.append(ok)
        if not ok:
            discrepancies.append(Discrepancy(
                field="education", resumeValue=school, linkedinValue=None, severity="major",
                description="University on resume not found in LinkedIn education",
            ))

    if not checks:
        return None, discrepancies
    return round(100 * sum(checks) / len(checks), 2), discrepancies


# Singleton instance
unified_verification_service = UnifiedVerificationService()
