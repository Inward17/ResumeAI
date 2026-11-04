"""
Issue #5: a resume task must only report success after the candidate's
application is saved to the job's pipeline.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes import resume

JOB_ID = "a" * 24
SCORING = {"skill_scores": [], "jd_match_score": 5.0}
SAVE_ERROR = "Could not save this candidate to the job"


class _FailingApplicationWrites:
    """The real mock database, except writes to applications raise."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        collection = getattr(self._db, name)
        if name != "applications":
            return collection
        failing = MagicMock()
        failing.find_one = collection.find_one
        failing.update_one = AsyncMock(side_effect=RuntimeError("mongodb://secret-host write failed"))
        failing.insert_one = failing.update_one
        return failing


@pytest.fixture(autouse=True)
def _scoring():
    with patch.object(resume, "run_unified_skill_scoring", AsyncMock(return_value=SCORING)):
        yield


async def _candidate(mock_db, **fields):
    """Without fields the candidate has no verification sources."""
    await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {}, **fields})
    await mock_db.tasks.insert_one({"task_id": "c1", "status": "parsed"})


async def _task(mock_db):
    return await mock_db.tasks.find_one({"task_id": "c1"})


def _verified():
    result = MagicMock()
    result.matchScore.overallCredibility = 70
    result.to_mongo_dict.return_value = {"matchScore": {"overallCredibility": 70}}
    return patch.object(resume.unified_verification_service, "run_unified_verification", AsyncMock(return_value=result))


def _verification_down():
    return patch.object(resume.unified_verification_service, "run_unified_verification",
                        AsyncMock(side_effect=RuntimeError("GitHub is down")))


class TestSaveFailures:
    async def test_failed_insert_is_not_reported_as_done(self, mock_db):
        await _candidate(mock_db)
        with patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", JOB_ID)
        task = await _task(mock_db)
        assert task["status"] == "failed"
        assert SAVE_ERROR in task["error"] and "Re-upload" in task["error"]
        assert task["completed_at"]
        assert await mock_db.applications.count_documents({}) == 0

    async def test_failed_update_is_not_reported_as_done(self, mock_db):
        await _candidate(mock_db)
        await mock_db.applications.insert_one({"candidate_id": "c1", "job_id": JOB_ID, "status": "Offer"})
        with patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", JOB_ID)
        assert (await _task(mock_db))["status"] == "failed"
        assert (await mock_db.applications.find_one({}))["status"] == "Offer"

    async def test_failed_scoring_is_not_reported_as_done(self, mock_db):
        await _candidate(mock_db)
        with patch.object(resume, "run_unified_skill_scoring", AsyncMock(side_effect=ValueError("bad"))):
            await resume._run_unified_verification("c1", JOB_ID)
        assert SAVE_ERROR in (await _task(mock_db))["error"]

    async def test_error_does_not_expose_driver_message(self, mock_db):
        await _candidate(mock_db)
        with patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", JOB_ID)
        assert "secret-host" not in (await _task(mock_db))["error"]

    async def test_verification_fallback_needs_the_save_too(self, mock_db):
        await _candidate(mock_db, github_username="jane")
        with _verification_down(), patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", JOB_ID)
        assert (await _task(mock_db))["status"] == "failed"

    async def test_failed_task_counts_as_failed_in_progress(self, client, mock_db, owned_job_id):
        await _candidate(mock_db)
        await mock_db.tasks.update_one({"task_id": "c1"}, {"$set": {"job_id": owned_job_id}})
        with patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", owned_job_id)
        counts = (await client.get(f"/api/v1/jobs/{owned_job_id}/tasks")).json()["counts"]
        assert counts["failed"] == 1 and counts["done"] == 0

    async def test_missing_candidate_fails_without_an_application(self, mock_db):
        await mock_db.tasks.insert_one({"task_id": "c1", "status": "parsed"})
        await resume._run_unified_verification("c1", JOB_ID)
        assert (await _task(mock_db))["status"] == "failed"
        assert await mock_db.applications.count_documents({}) == 0


class TestSuccessfulPaths:
    async def test_verified_candidate(self, mock_db):
        await _candidate(mock_db, github_username="jane")
        with _verified():
            await resume._run_unified_verification("c1", JOB_ID)
        task = await _task(mock_db)
        assert task["status"] == "done" and task["result"] == {"verified": True}
        app = await mock_db.applications.find_one({})
        assert app["score_details"]["overall_score"] == 70 and app["status"] == "Under Review"

    async def test_no_verification_sources(self, mock_db):
        await _candidate(mock_db)
        await resume._run_unified_verification("c1", JOB_ID)
        task = await _task(mock_db)
        assert task["status"] == "done" and task["result"]["verified"] is False
        assert await mock_db.applications.count_documents({}) == 1

    async def test_verification_failure_falls_back_after_saving(self, mock_db):
        await _candidate(mock_db, github_username="jane")
        with _verification_down():
            await resume._run_unified_verification("c1", JOB_ID)
        task = await _task(mock_db)
        assert task["status"] == "verification_failed" and task["error"] == "GitHub is down"
        assert task["completed_at"]
        assert (await mock_db.applications.find_one({}))["score_details"]["score_source"] == "unverified"

    @pytest.mark.parametrize("verification", [_verified, _verification_down])
    async def test_terminal_status_is_written_after_the_save(self, mock_db, verification):
        await _candidate(mock_db, github_username="jane")
        seen = []

        async def save(*args, **kwargs):
            seen.append((await _task(mock_db))["status"])

        with verification(), patch.object(resume, "_create_application", save):
            await resume._run_unified_verification("c1", JOB_ID)
        assert seen == ["verifying"]
        assert (await _task(mock_db))["status"] in ("done", "verification_failed")


class TestRetry:
    async def test_retry_after_failure_creates_one_application(self, mock_db):
        await _candidate(mock_db)
        with patch.object(resume, "db", _FailingApplicationWrites(mock_db)):
            await resume._run_unified_verification("c1", JOB_ID)
        await resume._run_unified_verification("c1", JOB_ID)
        assert (await _task(mock_db))["status"] == "done"
        assert await mock_db.applications.count_documents({"candidate_id": "c1", "job_id": JOB_ID}) == 1

    async def test_retry_keeps_recruiter_status_and_notes(self, mock_db):
        await _candidate(mock_db)
        await mock_db.applications.insert_one({
            "candidate_id": "c1", "job_id": JOB_ID, "status": "Shortlisted",
            "recruiter_notes": "Strong referral", "score_details": {"jd_match_score": 1.0},
        })
        await resume._run_unified_verification("c1", JOB_ID)
        assert await mock_db.applications.count_documents({}) == 1
        app = await mock_db.applications.find_one({})
        assert app["status"] == "Shortlisted" and app["recruiter_notes"] == "Strong referral"
        assert app["score_details"]["jd_match_score"] == 5.0

    async def test_new_application_gets_defaults(self, mock_db):
        await _candidate(mock_db)
        await resume._run_unified_verification("c1", JOB_ID)
        app = await mock_db.applications.find_one({})
        assert app["status"] == "Under Review" and app["recruiter_notes"] == "" and app["application_date"]
