"""
Tests for resume routes — upload, candidates, helper functions.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO
from datetime import datetime


# ============================================================================
# Helper function tests (pure, no mocking needed)
# ============================================================================
class TestExtractGithubUsername:
    def setup_method(self):
        from app.routes.resume import extract_github_username
        self.extract = extract_github_username

    def test_full_url(self):
        assert self.extract("https://github.com/janedoe") == "janedoe"

    def test_url_with_trailing_slash(self):
        assert self.extract("https://github.com/janedoe/") == "janedoe"

    def test_plain_username(self):
        assert self.extract("janedoe") == "janedoe"

    def test_empty(self):
        assert self.extract("") is None
        assert self.extract(None) is None

    def test_url_without_https(self):
        assert self.extract("github.com/janedoe") == "janedoe"


class TestExtractLinkedinUrl:
    def setup_method(self):
        from app.routes.resume import extract_linkedin_url
        self.extract = extract_linkedin_url

    def test_full_url(self):
        result = self.extract("https://linkedin.com/in/janedoe")
        assert result == "https://linkedin.com/in/janedoe"

    def test_without_protocol(self):
        result = self.extract("linkedin.com/in/janedoe")
        assert result == "https://linkedin.com/in/janedoe"

    def test_username_only(self):
        result = self.extract("janedoe")
        assert result == "https://linkedin.com/in/janedoe"

    def test_empty(self):
        assert self.extract("") is None
        assert self.extract(None) is None


# ============================================================================
# Upload route tests
# ============================================================================
class TestUploadResumes:
    async def test_upload_valid_file(self, client, mock_db):
        """Valid PDF upload should be accepted."""
        with patch("app.routes.resume._parse_and_verify", new_callable=AsyncMock):
            files = [("files", ("resume.pdf", b"fake-pdf-content", "application/pdf"))]
            resp = await client.post("/api/v1/jobs/job-123/upload", files=files)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "accepted"
            assert len(data["saved"]) == 1
            assert "candidate_id" in data["saved"][0]

    async def test_upload_txt_file(self, client):
        with patch("app.routes.resume._parse_and_verify", new_callable=AsyncMock):
            files = [("files", ("resume.txt", b"Plain text resume content", "text/plain"))]
            resp = await client.post("/api/v1/jobs/job-123/upload", files=files)
            assert resp.status_code == 200

    async def test_upload_unsupported_extension(self, client):
        files = [("files", ("resume.xyz", b"content", "application/octet-stream"))]
        resp = await client.post("/api/v1/jobs/job-123/upload", files=files)
        assert resp.status_code == 400

    async def test_upload_multiple_files(self, client):
        with patch("app.routes.resume._parse_and_verify", new_callable=AsyncMock):
            files = [
                ("files", ("resume1.pdf", b"pdf1", "application/pdf")),
                ("files", ("resume2.docx", b"docx1", "application/vnd.openxmlformats")),
            ]
            resp = await client.post("/api/v1/jobs/job-123/upload", files=files)
            assert resp.status_code == 200
            assert len(resp.json()["saved"]) == 2


# ============================================================================
# Candidates route tests
# ============================================================================
class TestGetJobCandidates:
    async def test_no_candidates(self, client):
        resp = await client.get("/api/v1/jobs/job-123/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job-123"
        assert data["candidates"] == []

    async def test_with_candidates(self, client, mock_db, sample_parsed_resume):
        """Insert application + candidate data, then query."""
        await mock_db.applications.delete_many({})
        await mock_db.candidates.delete_many({})
        candidate_id = "cand-001"

        # The route reads personal_info.name, so add that key
        parsed = dict(sample_parsed_resume)
        parsed["personal_info"] = dict(parsed["personal_info"])
        parsed["personal_info"]["name"] = parsed["personal_info"]["full_name"]

        # Insert candidate
        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "parsed": parsed,
            "filename": "resume.pdf",
        })

        # Insert application
        await mock_db.applications.insert_one({
            "candidate_id": candidate_id,
            "job_id": "job-123",
            "status": "Under Review",
            "application_date": datetime.utcnow(),
            "score_details": {
                "overall_score": 80,
                "skills_match_score": 40,
                "experience_match_score": 25,
                "verification_bonus": 5,
            },
        })

        resp = await client.get("/api/v1/jobs/job-123/candidates")
        assert resp.status_code == 200
        candidates = resp.json()["candidates"]
        assert len(candidates) == 1
        assert candidates[0]["name"] == "Jane Doe"
        assert candidates[0]["status"] == "Under Review"
        assert candidates[0]["score_details"]["overall_score"] == 80


# ============================================================================
# _create_application tests
# ============================================================================
class TestCreateApplication:
    async def test_create_with_verification_data(self, mock_db):
        from app.routes.resume import _create_application
        from bson import ObjectId

        candidate_id = "cand-002"
        job_id = "a" * 24  # valid 24-char hex ObjectId

        # Insert candidate so db.candidates.find_one succeeds
        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "parsed": {"skills": "Python", "experience": [], "projects": []},
        })
        # Insert job so db.jobs.find_one succeeds
        await mock_db.jobs.insert_one({
            "_id": ObjectId(job_id),
            "required_skills": ["Python"],
        })
        # Insert verification data
        await mock_db.verification_data.insert_one({
            "candidateId": candidate_id,
            "verificationStatus": {
                "github": "verified",
                "linkedin": "verified",
                "webCheck": "unverified",
            },
            "matchScore": {
                "overallCredibility": 85,
                "skillsMatch": 42,
                "experienceMatch": 28,
            },
        })

        mock_scoring = {"skill_scores": [], "jd_match_score": 5.0}
        with patch("app.routes.resume.db", mock_db), \
             patch("app.routes.resume.run_unified_skill_scoring",
                   new_callable=AsyncMock, return_value=mock_scoring):
            await _create_application(candidate_id, job_id)

        app_doc = await mock_db.applications.find_one({"candidate_id": candidate_id})
        assert app_doc is not None
        assert app_doc["job_id"] == job_id
        assert app_doc["score_details"]["verification_bonus"] == 10  # github + linkedin

    async def test_create_without_verification_data(self, mock_db):
        from app.routes.resume import _create_application
        from bson import ObjectId

        candidate_id = "cand-003"
        job_id = "b" * 24  # valid 24-char hex ObjectId

        # Insert candidate + job so queries succeed
        await mock_db.candidates.insert_one({
            "candidate_id": candidate_id,
            "parsed": {"skills": "", "experience": [], "projects": []},
        })
        await mock_db.jobs.insert_one({
            "_id": ObjectId(job_id),
            "required_skills": [],
        })

        mock_scoring = {"skill_scores": [], "jd_match_score": 0.0}
        with patch("app.routes.resume.db", mock_db), \
             patch("app.routes.resume.run_unified_skill_scoring",
                   new_callable=AsyncMock, return_value=mock_scoring):
            await _create_application(candidate_id, job_id)

        app_doc = await mock_db.applications.find_one({"candidate_id": candidate_id})
        assert app_doc is not None
        assert app_doc["score_details"]["verification_bonus"] == 0

