"""
Tests for resume routes — upload, candidates, helper functions.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from io import BytesIO
from datetime import datetime

from tests.conftest import create_owned_job


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
    async def test_upload_valid_file(self, client, mock_db, owned_job_id):
        """Valid PDF upload should be accepted."""
        files = [("files", ("resume.pdf", b"fake-pdf-content", "application/pdf"))]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        assert len(data["saved"]) == 1
        assert "candidate_id" in data["saved"][0]

    async def test_upload_txt_file(self, client, owned_job_id):
        files = [("files", ("resume.txt", b"Plain text resume content", "text/plain"))]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 200

    async def test_upload_unsupported_extension(self, client, owned_job_id):
        files = [("files", ("resume.xyz", b"content", "application/octet-stream"))]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 400

    async def test_upload_unsupported_file_rejects_whole_batch(self, client, mock_db, owned_job_id):
        """A bad file must not leave the valid files of the batch queued."""
        files = [
            ("files", ("good.pdf", b"pdf", "application/pdf")),
            ("files", ("bad.xyz", b"content", "application/octet-stream")),
        ]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 400
        assert await mock_db.tasks.count_documents({}) == 0

    async def test_upload_multiple_files(self, client, mock_db, owned_job_id):
        files = [
            ("files", ("resume1.pdf", b"pdf1", "application/pdf")),
            ("files", ("resume2.docx", b"docx1", "application/vnd.openxmlformats")),
        ]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 200
        assert len(resp.json()["saved"]) == 2
        assert await mock_db.tasks.count_documents({"job_id": owned_job_id, "status": "queued"}) == 2

    async def test_upload_large_batch_is_queued(self, client, mock_db, owned_job_id):
        """100 resumes in one request are all queued (previously processed one by one in-request)."""
        files = [("files", (f"resume{i}.txt", b"resume text", "text/plain")) for i in range(100)]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 200
        assert len(resp.json()["saved"]) == 100
        assert await mock_db.tasks.count_documents({"job_id": owned_job_id, "status": "queued"}) == 100

    async def test_upload_to_other_users_job_is_404(self, client, mock_db):
        other_job = await create_owned_job(mock_db, owner_uid="someone-else")
        files = [("files", ("resume.pdf", b"pdf", "application/pdf"))]
        resp = await client.post(f"/api/v1/jobs/{other_job}/upload", files=files)
        assert resp.status_code == 404
        assert await mock_db.tasks.count_documents({}) == 0


class TestJobTasks:
    async def test_task_progress_counts(self, client, mock_db, owned_job_id):
        now = datetime.utcnow()
        for i, status in enumerate(["queued", "processing", "verifying", "done", "done", "failed", "verification_failed"]):
            await mock_db.tasks.insert_one({
                "task_id": f"t{i}", "job_id": owned_job_id, "status": status,
                "original_filename": f"r{i}.pdf", "created_at": now,
            })
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/tasks")
        assert resp.status_code == 200
        counts = resp.json()["counts"]
        assert counts == {"queued": 1, "processing": 2, "done": 3, "failed": 1, "total": 7}
        assert len(resp.json()["tasks"]) == 7


# ============================================================================
# Candidates route tests
# ============================================================================
class TestGetJobCandidates:
    async def test_no_candidates(self, client, owned_job_id):
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == owned_job_id
        assert data["candidates"] == []

    async def test_more_than_100_candidates_returned(self, client, mock_db, owned_job_id):
        """The list used to be silently capped at 100 applications."""
        for i in range(150):
            cid = f"bulk-{i}"
            await mock_db.candidates.insert_one({
                "candidate_id": cid,
                "parsed": {"personal_info": {"full_name": f"C{i}", "phone_number": f"+1 {i}"}},
            })
            await mock_db.applications.insert_one({
                "candidate_id": cid, "job_id": owned_job_id, "status": "Under Review",
                "application_date": datetime.utcnow(), "score_details": {},
            })
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        assert resp.status_code == 200
        candidates = resp.json()["candidates"]
        assert len(candidates) == 150
        assert candidates[0]["phone"].startswith("+1 ")

    async def test_other_users_job_is_404(self, client, mock_db):
        other_job = await create_owned_job(mock_db, owner_uid="someone-else")
        resp = await client.get(f"/api/v1/jobs/{other_job}/candidates")
        assert resp.status_code == 404

    async def test_with_candidates(self, client, mock_db, sample_parsed_resume, owned_job_id):
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
            "job_id": owned_job_id,
            "status": "Under Review",
            "application_date": datetime.utcnow(),
            "score_details": {
                "overall_score": 80,
                "skills_match_score": 40,
                "experience_match_score": 25,
                "verification_bonus": 5,
            },
        })

        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
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

