"""
Tests for the MongoDB-backed resume processing queue (app/services/task_queue.py).
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services import task_queue as tq


async def _insert_task(db, task_id, status="queued", created_at=None, **fields):
    await db.tasks.insert_one({
        "task_id": task_id, "job_id": "job-1", "filename": f"{task_id}.pdf",
        "status": status, "attempts": 0, "created_at": created_at or datetime.utcnow(), **fields,
    })


async def _wait_until(predicate, timeout=5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if await predicate():
            return True
        await asyncio.sleep(0.02)
    return False


class TestTaskQueue:
    async def test_processes_tasks_concurrently(self, mock_db):
        for i in range(20):
            await _insert_task(mock_db, f"t{i}")

        running = 0
        peak = 0

        async def handler(task):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            await mock_db.tasks.update_one({"task_id": task["task_id"]}, {"$set": {"status": "done"}})

        queue = tq.TaskQueue()
        queue.start(handler, concurrency=5)
        try:
            assert await _wait_until(lambda: _count(mock_db, "done", 20))
        finally:
            await queue.stop()
        assert peak == 5  # ran in parallel, but never above the limit

    async def test_each_task_claimed_once_across_workers(self, mock_db):
        for i in range(30):
            await _insert_task(mock_db, f"t{i}")
        seen = []

        async def handler(task):
            seen.append(task["task_id"])
            await asyncio.sleep(0.01)
            await mock_db.tasks.update_one({"task_id": task["task_id"]}, {"$set": {"status": "done"}})

        queues = [tq.TaskQueue() for _ in range(3)]  # e.g. three backend processes
        for q in queues:
            q.start(handler, concurrency=4)
        try:
            assert await _wait_until(lambda: _count(mock_db, "done", 30))
        finally:
            for q in queues:
                await q.stop()
        assert sorted(seen) == sorted(f"t{i}" for i in range(30))

    async def test_claim_marks_task_processing(self, mock_db):
        await _insert_task(mock_db, "t1")
        queue = tq.TaskQueue()
        task = await queue._claim()
        assert task["status"] == "processing"
        assert task["attempts"] == 1
        assert task["worker_id"] == queue.worker_id
        assert await queue._claim() is None

    async def test_handler_crash_marks_task_failed(self, mock_db):
        await _insert_task(mock_db, "boom")

        async def handler(task):
            raise RuntimeError("kaboom")

        queue = tq.TaskQueue()
        queue.start(handler, concurrency=1)
        try:
            assert await _wait_until(lambda: _count(mock_db, "failed", 1))
        finally:
            await queue.stop()
        task = await mock_db.tasks.find_one({"task_id": "boom"})
        assert "kaboom" in task["error"]

    async def test_notify_wakes_idle_dispatcher(self, mock_db):
        handled = asyncio.Event()

        async def handler(task):
            handled.set()

        with patch.object(tq, "TASK_POLL_SECONDS", 30):
            queue = tq.TaskQueue()
            queue.start(handler, concurrency=1)
            try:
                await asyncio.sleep(0.05)  # dispatcher is now idle-waiting
                await _insert_task(mock_db, "late")
                queue.notify()
                await asyncio.wait_for(handled.wait(), timeout=2)
            finally:
                await queue.stop()


class TestRecoverStaleTasks:
    async def test_dead_worker_task_is_requeued(self, mock_db):
        old = datetime.utcnow() - timedelta(seconds=tq.TASK_STALE_SECONDS + 60)
        await _insert_task(mock_db, "stale", status="verifying", attempts=1, heartbeat_at=old)
        await _insert_task(mock_db, "alive", status="verifying", attempts=1, heartbeat_at=datetime.utcnow())
        await tq.recover_stale_tasks()
        assert (await mock_db.tasks.find_one({"task_id": "stale"}))["status"] == "queued"
        assert (await mock_db.tasks.find_one({"task_id": "alive"}))["status"] == "verifying"

    async def test_task_failing_repeatedly_is_given_up(self, mock_db):
        old = datetime.utcnow() - timedelta(seconds=tq.TASK_STALE_SECONDS + 60)
        await _insert_task(mock_db, "cursed", status="processing",
                           attempts=tq.TASK_MAX_ATTEMPTS, heartbeat_at=old)
        await tq.recover_stale_tasks()
        task = await mock_db.tasks.find_one({"task_id": "cursed"})
        assert task["status"] == "failed"

    async def test_legacy_and_expired_tasks_are_failed_not_rerun(self, mock_db):
        long_ago = datetime.utcnow() - timedelta(hours=tq.TASK_MAX_QUEUE_AGE_HOURS + 1)
        await _insert_task(mock_db, "legacy", status="parsed", created_at=long_ago)  # no heartbeat
        await _insert_task(mock_db, "ancient", status="queued", created_at=long_ago)
        await _insert_task(mock_db, "fresh", status="queued")
        await tq.recover_stale_tasks()
        assert (await mock_db.tasks.find_one({"task_id": "legacy"}))["status"] == "failed"
        assert (await mock_db.tasks.find_one({"task_id": "ancient"}))["status"] == "failed"
        assert (await mock_db.tasks.find_one({"task_id": "fresh"}))["status"] == "queued"


async def _count(db, status, expected):
    return await db.tasks.count_documents({"status": status}) == expected


class TestBulkUploadEndToEnd:
    async def test_100_resumes_all_processed(self, client, mock_db, owned_job_id, sample_parsed_resume):
        """Upload 100 resumes through the API and let the real queue + handler process them
        (Gemini, embeddings and external verification are mocked)."""
        from unittest.mock import AsyncMock, MagicMock
        from app.routes.resume import process_resume_task

        files = [("files", (f"resume{i}.txt", f"Resume number {i}".encode(), "text/plain")) for i in range(100)]
        resp = await client.post(f"/api/v1/jobs/{owned_job_id}/upload", files=files)
        assert resp.status_code == 200

        parse_calls = 0

        async def fake_parse(text):
            nonlocal parse_calls
            parse_calls += 1
            await asyncio.sleep(0.01)
            parsed = {**sample_parsed_resume, "personal_info": dict(sample_parsed_resume["personal_info"])}
            # unique people, so deduplication doesn't merge them
            parsed["personal_info"]["phone_number"] = text
            return parsed

        verification = MagicMock()
        verification.matchScore.overallCredibility = 70
        verification.to_mongo_dict.return_value = {"matchScore": {"overallCredibility": 70}}

        with patch("app.routes.resume.parse_resume", side_effect=fake_parse), \
             patch("app.services.embedding_service.generate_embedding", return_value=[0.0] * 384), \
             patch("app.routes.resume.unified_verification_service.run_unified_verification",
                   new=AsyncMock(return_value=verification)), \
             patch("app.routes.resume.run_unified_skill_scoring",
                   new=AsyncMock(return_value={"skill_scores": [], "jd_match_score": 5.0})):
            queue = tq.TaskQueue()
            queue.start(process_resume_task, concurrency=8)
            try:
                assert await _wait_until(lambda: _count(mock_db, "done", 100), timeout=20)
            finally:
                await queue.stop()

        assert parse_calls == 100
        assert await mock_db.candidates.count_documents({"owner_uid": "test-user"}) == 100
        resp = await client.get(f"/api/v1/jobs/{owned_job_id}/candidates")
        assert len(resp.json()["candidates"]) == 100
        progress = (await client.get(f"/api/v1/jobs/{owned_job_id}/tasks")).json()["counts"]
        assert progress["done"] == 100 and progress["queued"] == 0
