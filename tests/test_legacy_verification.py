"""
test_unified_verification.py (agent-aware) — Section 15

Legacy path integration test.  Confirms that the existing
UnifiedVerificationService produces the correct VerificationDataModel
shape and that no agent changes broke the legacy pipeline.

NOTE: The project already has tests/test_unified_verification.py.
      This file adds agent-specific assertions to confirm the legacy path
      still works in the presence of the new agent code.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime


# ===========================================================================
# Tests
# ===========================================================================
class TestLegacyPathAgentCoexistence:
    """
    Verify that the existing unified_verification pipeline still
    produces the correct output shape when the agent layer is present
    in the codebase but USE_AGENT_SYSTEM=false.
    """

    @pytest.mark.asyncio
    async def test_verification_data_model_shape(self, mock_db):
        """Legacy verification result has the expected top-level keys."""
        from app.services.unified_verification import UnifiedVerificationService

        svc = UnifiedVerificationService(db_client=mock_db)

        # Mock all external calls
        with patch("app.services.unified_verification.verify_github",
                    new_callable=AsyncMock) as mock_gh, \
             patch("app.services.unified_verification.scrape_linkedin_profiles",
                    new_callable=AsyncMock) as mock_li, \
             patch("app.services.unified_verification.verify_profile",
                    new_callable=AsyncMock) as mock_ws:

            # GitHub mock
            gh_result = MagicMock()
            gh_result.success = True
            gh_result.username = "testuser"
            gh_result.score100 = 75
            gh_result.score40 = 30
            gh_result.confidenceLevel = "medium"
            gh_result.redFlags = []
            gh_result.to_mongo_dict.return_value = {"score": 75}
            mock_gh.return_value = gh_result

            # LinkedIn mock
            mock_li.return_value = {"status": "success", "data": [{
                "profileId": "li-123",
                "publicIdentifier": "testuser",
                "firstName": "Test",
                "lastName": "User",
                "positions": [],
                "educations": [],
                "skills": [],
                "certifications": [],
            }]}

            # Web search mock
            mock_ws.return_value = {
                "profile_url": "test",
                "education": {"details": [], "average_score": 80, "overall_tag": "Verified"},
                "experience": {"details": [], "average_score": 70, "overall_tag": "Verified"},
                "university": {"average_score": 80, "overall_tag": "Verified"},
                "company": {"average_score": 70, "overall_tag": "Verified"},
            }

            result = await svc.run_unified_verification(
                candidate_id="test-cand",
                github_username="testuser",
                linkedin_url="https://linkedin.com/in/testuser",
                profile_data={"educations": [], "experiences": []},
            )

        # Verify the VerificationDataModel shape
        assert result.candidateId == "test-cand"
        assert result.githubData is not None
        assert result.linkedinData is not None
        assert result.webSearchData is not None
        assert result.verificationStatus is not None
        assert result.matchScore is not None

    @pytest.mark.asyncio
    async def test_legacy_github_failure_does_not_block_linkedin(self, mock_db):
        """asyncio.gather(return_exceptions=True) ensures isolation."""
        from app.services.unified_verification import UnifiedVerificationService

        svc = UnifiedVerificationService(db_client=mock_db)

        with patch("app.services.unified_verification.verify_github",
                    new_callable=AsyncMock, side_effect=RuntimeError("GitHub API down")), \
             patch("app.services.unified_verification.scrape_linkedin_profiles",
                    new_callable=AsyncMock, return_value={"status": "success", "data": [{
                        "profileId": "li-456",
                        "positions": [], "educations": [],
                        "skills": [], "certifications": [],
                    }]}), \
             patch("app.services.unified_verification.verify_profile",
                    new_callable=AsyncMock, return_value={
                        "profile_url": "test",
                        "university": {"average_score": 80, "overall_tag": "OK"},
                        "company": {"average_score": 70, "overall_tag": "OK"},
                        "education": {"details": [], "average_score": 80, "overall_tag": "OK"},
                        "experience": {"details": [], "average_score": 70, "overall_tag": "OK"},
                    }):

            result = await svc.run_unified_verification(
                candidate_id="test-cand-2",
                github_username="testuser",
                linkedin_url="https://linkedin.com/in/test",
                profile_data={"educations": [], "experiences": []},
            )

        # GitHub failed but LinkedIn and web search should still be present
        assert result.linkedinData is not None
        assert result.webSearchData is not None
        assert result.verificationStatus.github in ("unverified", "pending")

    @pytest.mark.asyncio
    async def test_no_inputs_produces_empty_verification(self, mock_db):
        """All inputs None → empty verification_data still persisted."""
        from app.services.unified_verification import UnifiedVerificationService

        svc = UnifiedVerificationService(db_client=mock_db)

        result = await svc.run_unified_verification(
            candidate_id="test-empty",
            github_username=None,
            linkedin_url=None,
            profile_data=None,
        )

        assert result.candidateId == "test-empty"
        assert result.matchScore is not None
