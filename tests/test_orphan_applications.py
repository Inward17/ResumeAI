"""
Issue #25: deleting a job while its resumes are still being screened must not
leave applications pointing at the deleted job (they 404 for good).
"""
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.routes import resume
from tests.conftest import create_owned_job

SCORING = {"skill_scores": [], "jd_match_score": 5.0}


@pytest.fixture(autouse=True)
def _scoring():
    with patch.object(resume, "run_unified_skill_scoring", AsyncMock(return_value=SCORING)):
        yield


async def _parsed_task(mock_db, job_id):
    await mock_db.candidates.insert_one({"candidate_id": "c1", "parsed": {}})
    await mock_db.tasks.insert_one({"task_id": "c1", "job_id": job_id, "status": "verifying"})


class TestJobDeletedDuringScreening:
    async def test_no_application_when_the_job_is_gone(self, mock_db):
        job_id = str(ObjectId())
        await _parsed_task(mock_db, job_id)
        with pytest.raises(resume.JobDeleted):
            await resume._create_application("c1", job_id)
        assert await mock_db.applications.count_documents({}) == 0

    async def test_job_deleted_while_scoring_leaves_no_application(self, mock_db):
        job_id = str(ObjectId())
        await mock_db.jobs.insert_one({"_id": ObjectId(job_id), "required_skills": ["Python"]})
        await _parsed_task(mock_db, job_id)

        async def delete_job_midway(**kwargs):
            # The recruiter deletes the job after the worker read it, before it saves
            await mock_db.jobs.delete_one({"_id": ObjectId(job_id)})
            await mock_db.applications.delete_many({"job_id": job_id})
            return SCORING

        with patch.object(resume, "run_unified_skill_scoring", AsyncMock(side_effect=delete_job_midway)):
            with pytest.raises(resume.JobDeleted):
                await resume._create_application("c1", job_id)
        assert await mock_db.applications.count_documents({}) == 0

    async def test_worker_finishing_after_delete_saves_nothing(self, mock_db):
        job_id = str(ObjectId())  # never existed / already deleted
        await _parsed_task(mock_db, job_id)
        await resume._run_unified_verification("c1", job_id)
        assert await mock_db.applications.count_documents({}) == 0
        # The task isn't reported as a save failure (it was deleted with the job)
        assert (await mock_db.tasks.find_one({"task_id": "c1"}))["status"] == "verifying"


class TestDeleteJobRemovesEveryTask:
    async def test_running_and_finished_tasks_go_with_the_job(self, client, mock_db):
        job_id = await create_owned_job(mock_db)
        await mock_db.tasks.insert_many([
            {"task_id": t, "job_id": job_id, "status": s}
            for t, s in (("t1", "queued"), ("t2", "processing"), ("t3", "parsed"),
                         ("t4", "verifying"), ("t5", "done"), ("t6", "cover_letter_pending"))
        ])
        await mock_db.tasks.insert_one({"task_id": "other", "job_id": "another-job", "status": "processing"})

        assert (await client.delete(f"/api/jobs/{job_id}")).status_code == 200
        assert await mock_db.tasks.count_documents({"job_id": job_id}) == 0
        assert await mock_db.tasks.count_documents({"task_id": "other"}) == 1
