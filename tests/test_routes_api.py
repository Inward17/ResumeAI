"""
Tests for GitHub and verification routes.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from tests.conftest import create_owned_job


# ============================================================================
# Removed routes stay removed (security review 2026-11-13, finding 2)
# ============================================================================
@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/verification/verify-candidate"),
    ("post", "/api/v1/verification/verify-candidate-async"),
    ("post", "/api/v1/github/analyze"),
    ("get", "/api/v1/github/analyze/someone"),
    ("get", "/api/v1/github/rate-limit"),
    ("post", "/api/v1/scrape-linkedin"),
    ("post", "/api/v1/verify-profile-data"),
    ("post", "/api/v1/search/"),
])
async def test_unscoped_verification_routes_are_gone(client, method, path):
    resp = await client.request(method, path, json={"candidate_id": "x", "github_username": "x"})
    assert resp.status_code in (404, 405)


# ============================================================================
# Verification status routes tests
# ============================================================================
class TestUnifiedVerificationRoutes:
    async def test_verification_status_not_found(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "pending", "job_id": owned_job_id})
        resp = await client.post(
            "/api/v1/verification/verification-status",
            json={"candidate_id": "pending"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"

    async def test_verification_status_other_users_candidate(self, client, mock_db):
        other_job = await create_owned_job(mock_db, owner_uid="someone-else")
        await mock_db.applications.insert_one({"candidate_id": "theirs", "job_id": other_job})
        await mock_db.verification_data.insert_one({"candidateId": "theirs"})
        resp = await client.post(
            "/api/v1/verification/verification-status",
            json={"candidate_id": "theirs"},
        )
        assert resp.status_code == 404

    async def test_verification_status_found(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "cand-001", "job_id": owned_job_id})
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

    async def test_verification_status_get_found(self, client, mock_db, owned_job_id):
        await mock_db.applications.insert_one({"candidate_id": "cand-002", "job_id": owned_job_id})
        await mock_db.verification_data.insert_one({
            "candidateId": "cand-002",
            "verificationStatus": {"github": "verified"},
        })

        resp = await client.get("/api/v1/verification/verification-status/cand-002")
        assert resp.status_code == 200
        assert resp.json()["status"] == "found"

    async def test_verification_status_get_not_found(self, client):
        resp = await client.get("/api/v1/verification/verification-status/nonexistent")
        assert resp.status_code == 404


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
