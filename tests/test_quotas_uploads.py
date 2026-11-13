"""
Regression tests for the 2026-11-13 security review, findings 3 (quotas and
rate limits) and 8 (upload handling).
"""
import asyncio
import os
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from tests.conftest import create_owned_job

PDF = b"%PDF-1.4 resume"


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from app.services import quota
    quota._hits.clear()
    yield
    quota._hits.clear()


def _pdfs(n):
    return [("files", (f"r{i}.pdf", PDF, "application/pdf")) for i in range(n)]


# ── Daily quotas ─────────────────────────────────────────────────────────
class TestQuota:
    async def test_quota_allows_up_to_limit_then_429(self, mock_db, monkeypatch):
        from app.services.quota import use_quota
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "2")
        await use_quota("org1", "ai_call")
        await use_quota("org1", "ai_call")
        with pytest.raises(HTTPException) as exc:
            await use_quota("org1", "ai_call")
        assert exc.value.status_code == 429
        assert "300" not in exc.value.detail and "2 AI calls" in exc.value.detail
        assert "resets at 00:00 UTC" in exc.value.detail
        # The rejected call is not counted, and other workspaces are unaffected
        assert (await mock_db.usage_quotas.find_one({"org_id": "org1"}))["count"] == 2
        await use_quota("org2", "ai_call")

    async def test_upload_quota_counts_files(self, client, mock_db, owned_job_id, monkeypatch):
        monkeypatch.setenv("QUOTA_RESUME_UPLOADS_PER_DAY", "3")
        assert (await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=_pdfs(2))).status_code == 200
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=_pdfs(2))
        assert resp.status_code == 429
        assert "3 resume uploads per day" in resp.json()["detail"]
        assert await mock_db.tasks.count_documents({}) == 2

    async def test_fact_checker_quota(self, client, mock_db, owned_job_id, monkeypatch):
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "1")
        await mock_db.applications.insert_one({"job_id": owned_job_id, "candidate_id": "c1"})
        result = {"response": "ok", "condition": "general_qa", "extracted_query": ""}
        with patch("app.routes.fact_checker_routes.fact_check", new=AsyncMock(return_value=result)):
            assert (await client.post("/api/fact-checker/c1", json={"message": "hi"})).status_code == 200
            resp = await client.post("/api/fact-checker/c1", json={"message": "hi"})
        assert resp.status_code == 429 and "AI calls" in resp.json()["detail"]

    async def test_cached_interview_questions_use_no_quota(self, client, mock_db, owned_job_id, monkeypatch):
        monkeypatch.setenv("QUOTA_AI_CALLS_PER_DAY", "0")
        await mock_db.applications.insert_one(
            {"job_id": owned_job_id, "candidate_id": "c1", "interview_questions": [{"q": "Why?"}]})
        resp = await client.get(f"/api/jobs/{owned_job_id}/candidates/c1/interview-questions")
        assert resp.status_code == 200 and resp.json()["cached"] is True


# ── Rate limit ───────────────────────────────────────────────────────────
class TestRateLimit:
    async def test_upload_rate_limited_per_user(self, client, owned_job_id, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        for _ in range(2):
            assert (await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=_pdfs(1))).status_code == 200
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=_pdfs(1))
        assert resp.status_code == 429
        assert "per minute" in resp.json()["detail"] and int(resp.headers["Retry-After"]) > 0

    def test_window_slides(self, monkeypatch):
        from app.services import quota
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
        now = [1000.0]
        monkeypatch.setattr(quota.time, "monotonic", lambda: now[0])
        quota.rate_limit("u", "ai")
        with pytest.raises(HTTPException):
            quota.rate_limit("u", "ai")
        quota.rate_limit("other-user", "ai")
        now[0] += 60
        quota.rate_limit("u", "ai")


# ── Upload validation ────────────────────────────────────────────────────
class TestUploadValidation:
    async def test_too_many_files(self, client, mock_db, owned_job_id):
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=_pdfs(51))
        assert resp.status_code == 400 and "at most 50" in resp.json()["detail"]
        assert await mock_db.tasks.count_documents({}) == 0

    @pytest.mark.parametrize("name,content", [
        ("fake.pdf", b"MZ\x90\x00 not a pdf"),
        ("fake.docx", b"%PDF-1.4"),
        ("fake.doc", b"plain text"),
        ("bad.txt", b"\xff\xfe\x00binary"),
    ])
    async def test_content_must_match_extension(self, client, mock_db, owned_job_id, name, content):
        files = [("files", ("good.pdf", PDF, "application/pdf")), ("files", (name, content, "application/octet-stream"))]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 400 and name in resp.json()["detail"]
        assert await mock_db.tasks.count_documents({}) == 0

    def test_content_matches_type(self):
        from app.utils.file_utils import content_matches_type
        assert content_matches_type("pdf", b"\n\n%PDF-1.7")
        assert content_matches_type("docx", b"PK\x03\x04rest")
        assert content_matches_type("doc", b"\xD0\xCF\x11\xE0rest")
        assert content_matches_type("txt", "Résumé".encode())
        assert not content_matches_type("txt", b"\xff\xfe")

    async def test_missing_filename_is_400(self, mock_db, test_user):
        from app.routes.resume import upload_resumes
        job_id = await create_owned_job(mock_db)
        with pytest.raises(HTTPException) as exc:
            await upload_resumes(job_id, [UploadFile(BytesIO(PDF), filename=None)], test_user)
        assert exc.value.status_code == 400

    async def test_size_enforced_when_size_unknown(self, mock_db, test_user):
        from app.routes.resume import upload_resumes
        job_id = await create_owned_job(mock_db)
        big = UploadFile(BytesIO(PDF + b"x" * 1024 * 1024), filename="big.pdf", size=None)
        with patch("app.routes.resume.MAX_UPLOAD_MB", 1):
            with pytest.raises(HTTPException) as exc:
                await upload_resumes(job_id, [big], test_user)
        assert exc.value.status_code == 413
        assert await mock_db.tasks.count_documents({}) == 0


# ── Parse step: timeout, safe errors, file cleanup ───────────────────────
async def _queued_task(mock_db, tmp_path, name="t1_resume.txt", content=b"Jane Doe resume"):
    (tmp_path / name).write_bytes(content)
    task = {"task_id": "t1", "job_id": "j1", "owner_uid": "test-user", "filename": name, "status": "processing"}
    await mock_db.tasks.insert_one(dict(task))
    return task


class TestParseStep:
    async def test_provider_error_text_not_stored_and_file_deleted(self, mock_db, tmp_path):
        from app.routes.resume import process_resume_task
        task = await _queued_task(mock_db, tmp_path)
        boom = RuntimeError("429 from https://internal-host.example/v1?key=abc")
        with patch("app.routes.resume.parse_resume", new=AsyncMock(side_effect=boom)):
            await process_resume_task(task)
        doc = await mock_db.tasks.find_one({"task_id": "t1"})
        assert doc["status"] == "failed"
        assert "RuntimeError" in doc["error"] and "internal-host" not in doc["error"]
        assert not (tmp_path / task["filename"]).exists()

    async def test_extraction_timeout_fails_task(self, mock_db, tmp_path):
        from app.routes.resume import process_resume_task
        task = await _queued_task(mock_db, tmp_path)

        def slow_read(*_):
            import time
            time.sleep(0.5)
            return "text"

        with patch("app.routes.resume.read_file", side_effect=slow_read), \
             patch("app.routes.resume.TEXT_EXTRACT_TIMEOUT_SECONDS", 0.05), \
             patch("app.routes.resume.parse_resume", new=AsyncMock()) as parse:
            await process_resume_task(task)
        doc = await mock_db.tasks.find_one({"task_id": "t1"})
        assert doc["status"] == "failed" and "too long" in doc["error"]
        parse.assert_not_called()

    async def test_file_deleted_after_candidate_stored(self, mock_db, tmp_path, sample_parsed_resume):
        from app.routes.resume import process_resume_task
        task = await _queued_task(mock_db, tmp_path)
        with patch("app.routes.resume.parse_resume", new=AsyncMock(return_value=sample_parsed_resume)), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 384), \
             patch("app.routes.resume._run_unified_verification", new=AsyncMock()) as verify:
            await process_resume_task(task)
        assert await mock_db.candidates.count_documents({"candidate_id": "t1"}) == 1
        assert not (tmp_path / task["filename"]).exists()
        verify.assert_awaited_once()

    async def test_retry_after_parse_skips_parsing(self, mock_db, tmp_path):
        """A task re-queued after a crash during verification has no file left; it goes straight to verification."""
        from app.routes.resume import process_resume_task
        task = {"task_id": "t1", "job_id": "j1", "owner_uid": "u", "filename": "gone.pdf",
                "status": "processing", "resolved_candidate_id": "c-existing"}
        await mock_db.tasks.insert_one(dict(task))
        with patch("app.routes.resume.parse_resume", new=AsyncMock()) as parse, \
             patch("app.routes.resume._run_unified_verification", new=AsyncMock()) as verify:
            await process_resume_task(task)
        parse.assert_not_called()
        verify.assert_awaited_once_with("c-existing", "j1", "t1")


class TestJobDeletionCleansFiles:
    async def test_delete_job_removes_leftover_files(self, client, mock_db, owned_job_id, tmp_path):
        for status in ("queued", "failed", "processing"):
            (tmp_path / f"{status}.pdf").write_bytes(PDF)
            await mock_db.tasks.insert_one({"task_id": status, "job_id": owned_job_id,
                                            "filename": f"{status}.pdf", "status": status})
        assert (await client.delete(f"/api/jobs/{owned_job_id}")).status_code == 200
        assert not (tmp_path / "queued.pdf").exists() and not (tmp_path / "failed.pdf").exists()
        # A worker is still parsing this one; it deletes the file itself
        assert (tmp_path / "processing.pdf").exists()
