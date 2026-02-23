"""
Tests for UnifiedVerificationService — orchestration, caching, score calculation.
All sub-verifications (GitHub, LinkedIn, web search) are mocked.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from dataclasses import dataclass

from app.services.unified_verification import (
    UnifiedVerificationService,
    VerificationCache,
)
from app.models.verification_data_model import (
    GitHubDataModel,
    LinkedInDataModel,
    WebSearchDataModel,
    WebSearchResult,
    EducationVerification,
    ExperienceVerification,
    MatchScoreModel,
)


# ============================================================================
# VerificationCache tests
# ============================================================================
class TestVerificationCache:
    def test_set_and_get(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        assert cache.get("cand-1", "github") == {"score": 85}

    def test_get_nonexistent_candidate(self):
        cache = VerificationCache()
        assert cache.get("nonexistent") is None
        assert cache.get("nonexistent", "github") is None

    def test_get_all(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        cache.set("cand-1", "linkedin", {"name": "Jane"})
        data = cache.get_all("cand-1")
        assert len(data) == 2

    def test_clear(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        cache.clear("cand-1")
        assert cache.get("cand-1") is None

    def test_clear_nonexistent(self):
        """Should not raise for nonexistent candidate."""
        cache = VerificationCache()
        cache.clear("nonexistent")  # Should not raise

    def test_has_complete_data_true(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        cache.set("cand-1", "linkedin", {"name": "Jane"})
        cache.set("cand-1", "webSearch", {"verified": True})
        assert cache.has_complete_data("cand-1") is True

    def test_has_complete_data_false(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        assert cache.has_complete_data("cand-1") is False

    def test_get_without_key(self):
        cache = VerificationCache()
        cache.set("cand-1", "github", {"score": 85})
        data = cache.get("cand-1")
        assert isinstance(data, dict)
        assert "github" in data


# ============================================================================
# UnifiedVerificationService tests
# ============================================================================
class TestUnifiedVerificationService:
    def _make_service(self, mock_db):
        with patch.object(UnifiedVerificationService, "__init__", lambda self, **kwargs: None):
            service = UnifiedVerificationService.__new__(UnifiedVerificationService)
            service.db = mock_db
            service.github_token = "fake-token"
            service.cache = VerificationCache()
            return service

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_github", new_callable=AsyncMock)
    async def test_github_only_verification(self, mock_gh_verify, mock_verify, mock_scrape, mock_db):
        service = self._make_service(mock_db)

        # Mock the new verify_github to return a GitHubVerificationResult-like object
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.username = "testuser"
        mock_result.score100 = 85.0
        mock_result.score40 = 34.0
        mock_result.confidenceLevel = "HIGH"
        mock_result.redFlags = []
        mock_result.to_mongo_dict.return_value = {"username": "testuser", "score100": 85.0}
        mock_gh_verify.return_value = mock_result

        result = await service.run_unified_verification(
            candidate_id="cand-github",
            github_username="testuser",
        )

        assert result.candidateId == "cand-github"
        assert result.verificationStatus.github in ("verified", "pending")

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_web_search_only(self, mock_verify, mock_scrape, mock_db):
        service = self._make_service(mock_db)

        mock_verify.return_value = {
            "profile_url": "cand-web",
            "education": {"details": [], "average_score": 85, "overall_tag": "Verified"},
            "experience": {"details": [], "average_score": 90, "overall_tag": "Verified"},
        }

        result = await service.run_unified_verification(
            candidate_id="cand-web",
            profile_data={"publicIdentifier": "test", "educations": [], "experiences": []},
        )

        assert result.candidateId == "cand-web"
        assert result.verificationStatus.webCheck in ("verified", "pending")

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_no_sources(self, mock_verify, mock_scrape, mock_db):
        """When no verification sources provided, all should be None/pending."""
        service = self._make_service(mock_db)

        result = await service.run_unified_verification(candidate_id="cand-empty")
        assert result.githubData is None
        assert result.linkedinData is None
        assert result.webSearchData is None

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    @patch("app.services.unified_verification.verify_profile", new_callable=AsyncMock)
    async def test_linkedin_only(self, mock_verify, mock_scrape, mock_db):
        service = self._make_service(mock_db)

        mock_scrape.return_value = {
            "status": "success",
            "data": [{
                "profileId": "li-123",
                "publicIdentifier": "janedoe",
                "firstName": "Jane",
                "lastName": "Doe",
                "headline": "SWE",
                "positions": [{"title": "SWE", "companyName": "Google"}],
                "educations": [{"schoolName": "MIT"}],
                "skills": [{"name": "Python", "endorsements": 50}],
                "certifications": [],
            }],
        }

        result = await service.run_unified_verification(
            candidate_id="cand-li",
            linkedin_url="https://linkedin.com/in/janedoe",
        )
        assert result.candidateId == "cand-li"

    @patch("app.services.unified_verification.scrape_linkedin_profiles", new_callable=AsyncMock)
    async def test_linkedin_scrape_failure(self, mock_scrape, mock_db):
        service = self._make_service(mock_db)
        mock_scrape.side_effect = Exception("Apify error")

        result = await service.run_unified_verification(
            candidate_id="cand-li-fail",
            linkedin_url="https://linkedin.com/in/test",
        )
        # Should not crash — error is caught
        assert result.candidateId == "cand-li-fail"
        assert result.verificationStatus.linkedin in ("unverified", "pending")


# ============================================================================
# Match score calculation tests
# ============================================================================
class TestCalculateMatchScores:
    def _make_service(self):
        with patch.object(UnifiedVerificationService, "__init__", lambda self, **kwargs: None):
            service = UnifiedVerificationService.__new__(UnifiedVerificationService)
            service.cache = VerificationCache()
            return service

    def test_github_only_score(self):
        service = self._make_service()
        github_data = GitHubDataModel(success=True, score=85.0)

        result = service._calculate_match_scores(github_data, None, None)
        assert result.skillsMatch == 85.0
        assert result.overallCredibility > 0

    def test_linkedin_only_score(self):
        service = self._make_service()
        linkedin_data = LinkedInDataModel(profileId="li-1")

        result = service._calculate_match_scores(None, linkedin_data, None)
        assert result.overallCredibility > 0  # LinkedIn presence gives 100 * 0.2

    def test_web_search_only_score(self):
        service = self._make_service()
        web_data = WebSearchDataModel(
            status="success",
            results=[WebSearchResult(
                experience=ExperienceVerification(average_score=80),
            )],
        )

        result = service._calculate_match_scores(None, None, web_data)
        assert result.experienceMatch == 80
        assert result.overallCredibility > 0

    def test_all_sources_score(self):
        service = self._make_service()
        github_data = GitHubDataModel(success=True, score=85.0)
        linkedin_data = LinkedInDataModel(profileId="li-1")
        web_data = WebSearchDataModel(
            status="success",
            results=[WebSearchResult(
                experience=ExperienceVerification(average_score=80),
            )],
        )

        result = service._calculate_match_scores(github_data, linkedin_data, web_data)
        # Weighted: GitHub(50%) + LinkedIn(20%) + Web(30%)
        expected = (85 * 0.5 + 100 * 0.2 + 80 * 0.3) / 1.0
        assert abs(result.overallCredibility - expected) < 1.0

    def test_no_sources_score(self):
        service = self._make_service()
        result = service._calculate_match_scores(None, None, None)
        assert result.overallCredibility == 0

    def test_failed_github_not_counted(self):
        service = self._make_service()
        github_data = GitHubDataModel(success=False, score=0)
        result = service._calculate_match_scores(github_data, None, None)
        assert result.skillsMatch == 0
        assert result.overallCredibility == 0
