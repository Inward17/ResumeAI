"""
Tests for GitHub and verification routes.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ============================================================================
# GitHub routes tests
# ============================================================================
class TestGitHubRoutes:
    @patch("app.routes.github_routes.verify_github", new_callable=AsyncMock)
    async def test_analyze_github_post_success(self, mock_verify, client):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_mongo_dict.return_value = {
            "success": True,
            "username": "testuser",
            "score": 85.0,
            "redFlags": [],
            "components": {"original_ratio": 24},
            "breakdown": {"final_score": 85.0},
            "repositoryStats": {"total": 10},
            "commitStats": {"total": 150},
            "readmeStats": {"repos_with_readme": 8},
            "githubData": None,
        }
        mock_verify.return_value = mock_result

        resp = await client.post(
            "/api/v1/github/analyze",
            json={"username": "testuser"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["score"] == 85.0

    @patch("app.routes.github_routes.verify_github", new_callable=AsyncMock)
    async def test_analyze_github_user_not_found(self, mock_verify, client):
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "No repositories found for user 'nonexistent'"
        mock_verify.return_value = mock_result

        resp = await client.post(
            "/api/v1/github/analyze",
            json={"username": "nonexistent"},
        )
        assert resp.status_code == 400

    @patch("app.routes.github_routes.verify_github", new_callable=AsyncMock)
    async def test_analyze_github_get(self, mock_verify, client):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_mongo_dict.return_value = {
            "success": True,
            "username": "testuser",
            "score": 70.0,
            "redFlags": ["Low commit depth"],
            "components": {},
            "breakdown": {},
            "repositoryStats": {},
            "commitStats": {},
            "readmeStats": {},
            "githubData": None,
        }
        mock_verify.return_value = mock_result

        resp = await client.get("/api/v1/github/analyze/testuser")
        assert resp.status_code == 200

    @patch("httpx.AsyncClient.get", new_callable=AsyncMock)
    async def test_rate_limit(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rate": {"remaining": 4999, "limit": 5000}}
        mock_get.return_value = mock_response

        resp = await client.get("/api/v1/github/rate-limit")
        assert resp.status_code == 200
        assert resp.json()["rate"]["remaining"] == 4999


# ============================================================================
# Unified verification routes tests
# ============================================================================
class TestUnifiedVerificationRoutes:
    @patch("app.routes.unified_verification_routes.unified_verification_service")
    async def test_verify_candidate_success(self, mock_service, client):
        """Successful verification with all sources."""
        mock_match = MagicMock()
        mock_match.model_dump.return_value = {
            "experienceMatch": 85,
            "skillsMatch": 70,
            "overallCredibility": 78,
        }
        mock_status = MagicMock()
        mock_status.model_dump.return_value = {
            "linkedin": "verified",
            "github": "verified",
            "webCheck": "verified",
            "discrepancies": [],
        }
        mock_github = MagicMock()
        mock_github.model_dump.return_value = {"score": 85, "username": "testuser"}
        mock_linkedin = MagicMock()
        mock_linkedin.model_dump.return_value = {"firstName": "Jane"}
        mock_web = MagicMock()
        mock_web.model_dump.return_value = {"status": "success"}

        mock_result = MagicMock()
        mock_result.candidateId = "cand-001"
        mock_result.verificationStatus = mock_status
        mock_result.matchScore = mock_match
        mock_result.githubData = mock_github
        mock_result.linkedinData = mock_linkedin
        mock_result.webSearchData = mock_web

        mock_service.run_unified_verification = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/api/v1/verification/verify-candidate",
            json={
                "candidate_id": "cand-001",
                "github_username": "testuser",
                "linkedin_url": "https://linkedin.com/in/janedoe",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["candidateId"] == "cand-001"

    async def test_verify_candidate_missing_sources(self, client):
        resp = await client.post(
            "/api/v1/verification/verify-candidate",
            json={"candidate_id": "cand-001"},
        )
        assert resp.status_code == 400

    async def test_verify_candidate_missing_id(self, client):
        resp = await client.post(
            "/api/v1/verification/verify-candidate",
            json={"github_username": "test"},
        )
        assert resp.status_code == 422  # Pydantic validation

    @patch("app.routes.unified_verification_routes.unified_verification_service")
    async def test_verify_candidate_service_error(self, mock_service, client):
        mock_service.run_unified_verification = AsyncMock(
            side_effect=Exception("Service crashed")
        )
        resp = await client.post(
            "/api/v1/verification/verify-candidate",
            json={"candidate_id": "cand-001", "github_username": "test"},
        )
        assert resp.status_code == 500

    async def test_verification_status_not_found(self, client):
        resp = await client.post(
            "/api/v1/verification/verification-status",
            json={"candidate_id": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    async def test_verification_status_found(self, client, mock_db):
        await mock_db.verification_data.insert_one({
            "candidateId": "cand-001",
            "verificationStatus": {"github": "verified"},
            "matchScore": {"overallCredibility": 80},
        })

        resp = await client.post(
            "/api/v1/verification/verification-status",
            json={"candidate_id": "cand-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "found"
        assert data["data"]["candidateId"] == "cand-001"

    async def test_verification_status_get_found(self, client, mock_db):
        await mock_db.verification_data.insert_one({
            "candidateId": "cand-002",
            "verificationStatus": {"github": "verified"},
        })

        resp = await client.get("/api/v1/verification/verification-status/cand-002")
        assert resp.status_code == 200
        assert resp.json()["status"] == "found"

    async def test_verification_status_get_not_found(self, client):
        resp = await client.get("/api/v1/verification/verification-status/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"


# ============================================================================
# Search routes tests
# ============================================================================
class TestSearchRoutes:
    @patch("app.routes.search_routes.verify_entity", new_callable=AsyncMock)
    async def test_search_success(self, mock_verify, client):
        mock_verify.return_value = {
            "verified": True,
            "top_result": "https://iitd.ac.in",
            "title": "IIT Delhi",
            "snippet": "Indian Institute",
            "confidence": 90.0,
            "match_type": "strong_domain_match",
            "domain": "iitd.ac.in",
            "matched_variation": False,
        }

        resp = await client.post(
            "/api/v1/search/",
            json={"query": "IIT Delhi", "field_type": "education"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["confidence"] == 90.0

    @patch("app.routes.search_routes.verify_entity", new_callable=AsyncMock)
    async def test_search_error(self, mock_verify, client):
        mock_verify.side_effect = Exception("Search failed")
        resp = await client.post(
            "/api/v1/search/",
            json={"query": "test"},
        )
        assert resp.status_code == 500


# ============================================================================
# Verification routes tests
# ============================================================================
class TestVerificationRoutes:
    @patch("app.routes.verification.verify_profile", new_callable=AsyncMock)
    async def test_verify_profile_data(self, mock_verify, client):
        mock_verify.return_value = {
            "profile_url": "janedoe",
            "education": {"average_score": 85, "overall_tag": "Verified"},
            "experience": {"average_score": 90, "overall_tag": "Verified"},
        }

        resp = await client.post(
            "/api/v1/verify-profile-data",
            json={"data": {"publicIdentifier": "janedoe", "educations": [], "experiences": []}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["results"]) == 1

    @patch("app.routes.verification.verify_profile", new_callable=AsyncMock)
    async def test_verify_multiple_profiles(self, mock_verify, client):
        mock_verify.return_value = {"profile_url": "test", "education": {}, "experience": {}}

        resp = await client.post(
            "/api/v1/verify-profile-data",
            json={"data": [
                {"publicIdentifier": "user1"},
                {"publicIdentifier": "user2"},
            ]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2

    @patch("app.routes.verification.verify_profile", new_callable=AsyncMock)
    async def test_verify_profile_error(self, mock_verify, client):
        mock_verify.side_effect = Exception("Verification error")
        resp = await client.post(
            "/api/v1/verify-profile-data",
            json={"data": {"publicIdentifier": "test"}},
        )
        assert resp.status_code == 500


# ============================================================================
# LinkedIn routes tests
# ============================================================================
class TestLinkedInRoutes:
    @patch("app.routes.linkedin.scrape_linkedin_profiles", new_callable=AsyncMock)
    async def test_scrape_success(self, mock_scrape, client):
        mock_scrape.return_value = {
            "status": "success",
            "data": [{"firstName": "Jane"}],
        }

        resp = await client.post(
            "/api/v1/scrape-linkedin",
            json={"profileUrls": ["https://linkedin.com/in/janedoe"]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    @patch("app.routes.linkedin.scrape_linkedin_profiles", new_callable=AsyncMock)
    async def test_scrape_error(self, mock_scrape, client):
        mock_scrape.side_effect = Exception("Apify down")
        resp = await client.post(
            "/api/v1/scrape-linkedin",
            json={"profileUrls": ["https://linkedin.com/in/test"]},
        )
        assert resp.status_code == 500


# ============================================================================
# Health check test
# ============================================================================
class TestHealthCheck:
    async def test_root_endpoint(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "resumeai-backend"
        assert "time" in data
