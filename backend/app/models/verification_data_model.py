"""
Verification Data Model - Pydantic models for MongoDB verification_data collection
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# --- GitHub Data Models ---

class GitHubScoreComponents(BaseModel):
    original_ratio: float = 0
    commit_depth: float = 0
    readme_presence: float = 0
    language_match: float = 0
    oss_bonus: float = 0
    penalty: float = 0


class GitHubScoreBreakdown(BaseModel):
    raw_score: float = 0
    total_penalty: float = 0
    final_score: float = 0


class GitHubRepositoryStats(BaseModel):
    total: int = 0
    original: int = 0
    forked: int = 0
    original_ratio: float = 0


class GitHubCommitStats(BaseModel):
    total: int = 0
    average_per_repo: float = 0
    repos_with_low_commits: int = 0
    lastCommitDate: Optional[datetime] = None


class GitHubReadmeStats(BaseModel):
    repos_with_readme: int = 0
    repos_without_readme: int = 0
    repos_with_short_readme: int = 0
    readme_presence_ratio: float = 0


class GitHubDataModel(BaseModel):
    username: Optional[str] = None
    success: bool = False
    score: float = 0
    # --- V2 fields ---
    score100: Optional[float] = None
    score40: Optional[float] = None
    confidenceLevel: Optional[str] = None  # HIGH / MEDIUM / LOW
    # --- End V2 fields ---
    redFlags: List[str] = Field(default_factory=list)
    components: Optional[GitHubScoreComponents] = None
    breakdown: Optional[GitHubScoreBreakdown] = None
    repositoryStats: Optional[GitHubRepositoryStats] = None
    commitStats: Optional[GitHubCommitStats] = None
    readmeStats: Optional[GitHubReadmeStats] = None
    verifiedAt: Optional[datetime] = None
    # NEW: For JD matching
    projects_embedding: Optional[List[float]] = None
    technologies_combined: Optional[str] = None
    # Full V2 result dict for rich data storage
    github_v2_data: Optional[dict] = None


# --- Web Search Data Models ---

class EducationDetail(BaseModel):
    college: Optional[str] = None
    verified: bool = False
    top_result: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    score: float = 0
    tag: Optional[str] = None


class ExperienceDetail(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    verified: bool = False
    top_result: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    score: float = 0
    tag: Optional[str] = None


class EducationVerification(BaseModel):
    average_score: float = 0
    overall_tag: Optional[str] = None
    details: List[EducationDetail] = Field(default_factory=list)


class ExperienceVerification(BaseModel):
    average_score: float = 0
    overall_tag: Optional[str] = None
    details: List[ExperienceDetail] = Field(default_factory=list)


class WebSearchResult(BaseModel):
    profile_url: Optional[str] = None
    education: Optional[EducationVerification] = None
    experience: Optional[ExperienceVerification] = None


class WebSearchDataModel(BaseModel):
    status: Optional[str] = None
    verifiedAt: Optional[datetime] = None
    results: List[WebSearchResult] = Field(default_factory=list)


# --- LinkedIn Data Models ---

class TimePeriod(BaseModel):
    startDate: Optional[dict] = None  # {"month": int, "year": int}
    endDate: Optional[dict] = None


class LinkedInPosition(BaseModel):
    title: Optional[str] = None
    companyName: Optional[str] = None
    locationName: Optional[str] = None
    description: Optional[str] = None
    totalDuration: Optional[str] = None
    companyLogo: Optional[str] = None
    companyUrl: Optional[str] = None
    timePeriod: Optional[TimePeriod] = None


class LinkedInEducation(BaseModel):
    schoolName: Optional[str] = None
    degreeName: Optional[str] = None
    fieldOfStudy: Optional[str] = None
    timePeriod: Optional[TimePeriod] = None


class LinkedInCertification(BaseModel):
    name: Optional[str] = None
    authority: Optional[str] = None
    issuer: Optional[str] = None


class LinkedInSkill(BaseModel):
    name: Optional[str] = None
    endorsements: int = 0


class LinkedInDataModel(BaseModel):
    profileId: Optional[str] = None
    publicIdentifier: Optional[str] = None
    profileUrl: Optional[str] = None
    verifiedAt: Optional[datetime] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    countryCode: Optional[str] = None
    pictureUrl: Optional[str] = None
    positions: List[LinkedInPosition] = Field(default_factory=list)
    educations: List[LinkedInEducation] = Field(default_factory=list)
    certifications: List[LinkedInCertification] = Field(default_factory=list)
    skills: List[LinkedInSkill] = Field(default_factory=list)


# --- Verification Status Models ---

class Discrepancy(BaseModel):
    field: Optional[str] = None
    resumeValue: Optional[str] = None
    linkedinValue: Optional[str] = None
    severity: Optional[str] = None  # minor/major/critical
    description: Optional[str] = None


class VerificationStatusModel(BaseModel):
    linkedin: str = "pending"  # verified/unverified/pending
    github: str = "pending"
    webCheck: str = "pending"
    discrepancies: List[Discrepancy] = Field(default_factory=list)


class MatchScoreModel(BaseModel):
    experienceMatch: float = 0
    skillsMatch: float = 0
    overallCredibility: float = 0


# --- Main Verification Data Model ---

class VerificationDataModel(BaseModel):
    """Main verification data document for MongoDB"""
    candidateId: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    
    githubData: Optional[GitHubDataModel] = None
    webSearchData: Optional[WebSearchDataModel] = None
    linkedinData: Optional[LinkedInDataModel] = None
    
    verificationStatus: VerificationStatusModel = Field(default_factory=VerificationStatusModel)
    matchScore: Optional[MatchScoreModel] = None
    
    def to_mongo_dict(self) -> dict:
        """Convert to MongoDB-compatible dict"""
        data = self.model_dump(exclude_none=True)
        return data
