"""
Tests for Pydantic models and GitHubWriter.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

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
    MatchScoreModel,
    Discrepancy,
)
from app.models.github_writer import GitHubWriter


# ============================================================================
# VerificationDataModel tests
# ============================================================================
class TestVerificationDataModel:
    def test_minimal_creation(self):
        model = VerificationDataModel(candidateId="test-123")
        assert model.candidateId == "test-123"
        assert model.githubData is None
        assert model.linkedinData is None
        assert model.webSearchData is None
        assert model.verificationStatus.linkedin == "pending"

    def test_to_mongo_dict(self):
        model = VerificationDataModel(
            candidateId="test-123",
            githubData=GitHubDataModel(username="testuser", success=True, score=85.5),
            matchScore=MatchScoreModel(overallCredibility=80.0),
        )
        doc = model.to_mongo_dict()
        assert doc["candidateId"] == "test-123"
        assert doc["githubData"]["username"] == "testuser"
        assert doc["matchScore"]["overallCredibility"] == 80.0
        # None fields excluded
        assert "linkedinData" not in doc

    def test_full_construction(self):
        now = datetime.utcnow()
        model = VerificationDataModel(
            candidateId="full-test",
            createdAt=now,
            updatedAt=now,
            githubData=GitHubDataModel(
                username="dev",
                success=True,
                score=75.0,
                redFlags=["Low commit depth"],
                components=GitHubScoreComponents(original_ratio=24.0, commit_depth=18.0),
                breakdown=GitHubScoreBreakdown(raw_score=82.0, total_penalty=5.0, final_score=77.0),
                repositoryStats=GitHubRepositoryStats(total=10, original=8, forked=2, original_ratio=0.8),
                commitStats=GitHubCommitStats(total=150, average_per_repo=15.0),
                readmeStats=GitHubReadmeStats(repos_with_readme=8, readme_presence_ratio=0.8),
            ),
            linkedinData=LinkedInDataModel(
                profileId="li-456",
                firstName="Jane",
                lastName="Doe",
                positions=[LinkedInPosition(title="SWE", companyName="Google")],
                educations=[LinkedInEducation(schoolName="MIT")],
                certifications=[LinkedInCertification(name="AWS")],
                skills=[LinkedInSkill(name="Python", endorsements=50)],
            ),
            webSearchData=WebSearchDataModel(
                status="success",
                results=[
                    WebSearchResult(
                        profile_url="janedoe",
                        education=EducationVerification(average_score=85),
                        experience=ExperienceVerification(average_score=90),
                    )
                ],
            ),
            verificationStatus=VerificationStatusModel(
                linkedin="verified",
                github="verified",
                webCheck="verified",
                discrepancies=[Discrepancy(field="title", severity="minor")],
            ),
            matchScore=MatchScoreModel(
                experienceMatch=90, skillsMatch=75, overallCredibility=82
            ),
        )
        doc = model.to_mongo_dict()
        assert doc["githubData"]["score"] == 75.0
        assert doc["linkedinData"]["firstName"] == "Jane"
        assert len(doc["verificationStatus"]["discrepancies"]) == 1


class TestGitHubDataModel:
    def test_success_state(self):
        model = GitHubDataModel(username="dev", success=True, score=85.0, redFlags=[])
        assert model.success is True
        assert model.score == 85.0

    def test_failure_state(self):
        model = GitHubDataModel(success=False, redFlags=["User not found"])
        assert model.success is False
        assert "User not found" in model.redFlags

    def test_defaults(self):
        model = GitHubDataModel()
        assert model.username is None
        assert model.success is False
        assert model.score == 0
        assert model.redFlags == []


class TestLinkedInDataModel:
    def test_with_positions_and_skills(self):
        model = LinkedInDataModel(
            profileId="li-1",
            positions=[
                LinkedInPosition(
                    title="SWE",
                    companyName="Google",
                    timePeriod=TimePeriod(startDate={"month": 1, "year": 2020}),
                )
            ],
            skills=[LinkedInSkill(name="Python", endorsements=50)],
        )
        assert len(model.positions) == 1
        assert model.positions[0].companyName == "Google"
        assert model.skills[0].endorsements == 50


class TestMatchScoreModel:
    def test_default_scores(self):
        model = MatchScoreModel()
        assert model.experienceMatch == 0
        assert model.skillsMatch == 0
        assert model.overallCredibility == 0

    def test_custom_scores(self):
        model = MatchScoreModel(experienceMatch=85, skillsMatch=70, overallCredibility=78)
        assert model.overallCredibility == 78


class TestTimePeriod:
    def test_with_dates(self):
        tp = TimePeriod(
            startDate={"month": 1, "year": 2020},
            endDate={"month": 6, "year": 2024},
        )
        assert tp.startDate["year"] == 2020

    def test_empty(self):
        tp = TimePeriod()
        assert tp.startDate is None


# ============================================================================
# GitHubWriter tests
# ============================================================================
class TestGitHubWriter:
    def test_write_github_data(self):
        writer = GitHubWriter(db_client=None)

        score_result = {
            "score": 85.0,
            "redFlags": [],
            "components": {"original_ratio": 24, "commit_depth": 20},
        }
        repo_analysis = {
            "repositoryStats": {"total": 5, "original": 4},
            "commitStats": {"total": 100, "average_per_repo": 20},
            "ossContributions": 1,
        }
        readme_analysis = {
            "readmeStats": {"repos_with_readme": 4, "readme_presence_ratio": 0.8},
            "languageMatchStats": {"has_global_mismatch": False},
            "enhancedRepositories": [
                {
                    "name": "my-repo",
                    "full_name": "user/my-repo",
                    "owner": "user",
                    "is_fork": False,
                    "is_original": True,
                    "is_oss_contribution": False,
                    "commit_count": 25,
                    "has_dump_pattern": False,
                    "has_readme": True,
                    "readme_length": 500,
                    "description": "A project",
                    "languages": {"Python": 50000},
                    "stars": 10,
                    "forks": 2,
                    "created_at": "2024-01-01",
                    "updated_at": "2024-06-01",
                }
            ],
        }

        result = writer.write_github_data(
            user_id="user-1",
            username="testuser",
            score_result=score_result,
            repo_analysis=repo_analysis,
            readme_analysis=readme_analysis,
        )

        assert result["username"] == "testuser"
        assert result["score"] == 85.0
        assert len(result["repositories"]) == 1
        assert result["repositories"][0]["name"] == "my-repo"

    def test_format_repositories(self):
        writer = GitHubWriter()
        repos = [
            {
                "name": "test",
                "full_name": "user/test",
                "owner": "user",
                "description": "desc",
                "is_fork": False,
                "is_original": True,
                "is_oss_contribution": False,
                "commit_count": 10,
                "has_dump_pattern": False,
                "has_readme": True,
                "readme_length": 200,
                "languages": {"Python": 5000},
                "stars": 5,
                "forks": 1,
                "created_at": "2024-01-01",
                "updated_at": "2024-06-01",
            }
        ]
        result = writer._format_repositories(repos)
        assert len(result) == 1
        assert result[0]["name"] == "test"
        assert result[0]["commit_count"] == 10

    def test_get_github_data_no_db(self):
        writer = GitHubWriter(db_client=None)
        assert writer.get_github_data("user-1") is None

    def test_persist_to_database_placeholder(self):
        """_persist_to_database is a placeholder, should not raise."""
        writer = GitHubWriter(db_client=MagicMock())
        writer._persist_to_database("user-1", {"score": 50})  # Should not raise
