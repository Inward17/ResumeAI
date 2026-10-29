"""
Durable resume-processing queue backed by the MongoDB ``tasks`` collection.

Why: FastAPI ``BackgroundTasks`` run *sequentially* inside the request process,
so a batch of 100 resumes was processed one after another (parse + full
verification each) and anything still queued was lost on a restart or reload.

How it works:
  * The upload endpoint only stores the file and inserts a task with
    ``status="queued"``.
  * A dispatcher claims queued tasks atomically (``find_one_and_update``) and
    runs up to ``RESUME_WORKERS`` of them concurrently.
  * Running tasks send a heartbeat; tasks whose worker died (no heartbeat for
    ``TASK_STALE_SECONDS``) are re-queued, up to ``TASK_MAX_ATTEMPTS`` times.

Because claiming is atomic, any number of backend processes (or dedicated
``python -m app.worker`` processes) can share one hosted database safely.
"""
import os
import uuid
import socket
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

from pymongo import ReturnDocument

from app.database import db

logger = logging.getLogger(__name__)

RESUME_WORKERS = int(os.getenv("RESUME_WORKERS", "8"))
TASK_STALE_SECONDS = int(os.getenv("TASK_STALE_SECONDS", "300"))
TASK_HEARTBEAT_SECONDS = int(os.getenv("TASK_HEARTBEAT_SECONDS", "30"))
TASK_MAX_ATTEMPTS = int(os.getenv("TASK_MAX_ATTEMPTS", "3"))
TASK_POLL_SECONDS = float(os.getenv("TASK_POLL_SECONDS", "2"))
TASK_MAX_QUEUE_AGE_HOURS = int(os.getenv("TASK_MAX_QUEUE_AGE_HOURS", "24"))

# Statuses written while a task is being worked on (see app/routes/resume.py).
IN_PROGRESS_STATUSES = ["processing", "parsed", "verifying"]
TERMINAL_STATUSES = ["done", "failed", "verification_failed"]

TaskHandler = Callable[[dict], Awaitable[None]]


class TaskQueue:
    def __init__(self):
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._handler: Optional[TaskHandler] = None
        self._slots: Optional[asyncio.Semaphore] = None
        self._wakeup: Optional[asyncio.Event] = None
        self._dispatcher: Optional[asyncio.Task] = None
        self._running: set = set()

    @property
    def started(self) -> bool:
        return self._dispatcher is not None

    def start(self, handler: TaskHandler, concurrency: int = RESUME_WORKERS):
        if self.started or concurrency <= 0:
            return
        self._handler = handler
        self._slots = asyncio.Semaphore(concurrency)
        self._wakeup = asyncio.Event()
        self._dispatcher = asyncio.create_task(self._dispatch_loop())
        logger.info("Task queue started: worker=%s concurrency=%d", self.worker_id, concurrency)

    async def stop(self):
        if not self.started:
            return
        self._dispatcher.cancel()
        for task in list(self._running):
            task.cancel()
        await asyncio.gather(self._dispatcher, *self._running, return_exceptions=True)
        self._dispatcher = None
        # Tasks interrupted here keep their in-progress status and are re-queued
        # by recover_stale_tasks() once their heartbeat expires.
        logger.info("Task queue stopped: worker=%s", self.worker_id)

    def notify(self):
        """Wake the dispatcher right away (called after new tasks are inserted)."""
        if self._wakeup is not None:
            self._wakeup.set()

    async def _dispatch_loop(self):
        last_recovery = datetime.min
        while True:
            try:
                if (datetime.utcnow() - last_recovery).total_seconds() >= TASK_HEARTBEAT_SECONDS:
                    await recover_stale_tasks()
                    last_recovery = datetime.utcnow()

                await self._slots.acquire()
                self._wakeup.clear()
                task = await self._claim()
                if task is None:
                    self._slots.release()
                    try:
                        await asyncio.wait_for(self._wakeup.wait(), timeout=TASK_POLL_SECONDS)
                    except asyncio.TimeoutError:
                        pass
                    continue

                runner = asyncio.create_task(self._run(task))
                self._running.add(runner)
                runner.add_done_callback(self._running.discard)
            except asyncio.CancelledError:
                raise
            except Exception:
                # e.g. the database is briefly unreachable — back off and retry.
                logger.exception("Task dispatcher error")
                await asyncio.sleep(TASK_POLL_SECONDS)

    async def _claim(self) -> Optional[dict]:
        now = datetime.utcnow()
        return await db.tasks.find_one_and_update(
            {"status": "queued"},
            {
                "$set": {"status": "processing", "worker_id": self.worker_id,
                         "started_at": now, "heartbeat_at": now},
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    async def _run(self, task: dict):
        task_id = task["task_id"]
        heartbeat = asyncio.create_task(self._heartbeat(task_id))
        try:
            await self._handler(task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Task %s crashed", task_id)
            await db.tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": str(exc)}},
            )
        finally:
            heartbeat.cancel()
            self._slots.release()

    async def _heartbeat(self, task_id: str):
        while True:
            await asyncio.sleep(TASK_HEARTBEAT_SECONDS)
            try:
                await db.tasks.update_one(
                    {"task_id": task_id, "worker_id": self.worker_id},
                    {"$set": {"heartbeat_at": datetime.utcnow()}},
                )
            except Exception:
                logger.warning("Heartbeat failed for task %s", task_id, exc_info=True)


async def recover_stale_tasks():
    """Re-queue tasks whose worker stopped sending heartbeats (crash, restart, deploy)."""
    cutoff = datetime.utcnow() - timedelta(seconds=TASK_STALE_SECONDS)
    stale = {"status": {"$in": IN_PROGRESS_STATUSES}, "heartbeat_at": {"$lt": cutoff}}

    exhausted = await db.tasks.update_many(
        {**stale, "attempts": {"$gte": TASK_MAX_ATTEMPTS}},
        {"$set": {"status": "failed", "completed_at": datetime.utcnow(),
                  "error": f"Worker stopped responding {TASK_MAX_ATTEMPTS} times"}},
    )
    requeued = await db.tasks.update_many(
        {**stale, "attempts": {"$lt": TASK_MAX_ATTEMPTS}},
        {"$set": {"status": "queued"}, "$unset": {"worker_id": ""}},
    )
    # Tasks left behind by the old BackgroundTasks code (no heartbeat) or
    # queued so long ago that re-running them would surprise the user.
    expired = await db.tasks.update_many(
        {"$or": [
            {"status": {"$in": IN_PROGRESS_STATUSES}, "heartbeat_at": {"$exists": False},
             "created_at": {"$lt": cutoff}},
            {"status": "queued",
             "created_at": {"$lt": datetime.utcnow() - timedelta(hours=TASK_MAX_QUEUE_AGE_HOURS)}},
        ]},
        {"$set": {"status": "failed", "completed_at": datetime.utcnow(),
                  "error": "Processing was interrupted; please re-upload this resume"}},
    )
    if exhausted.modified_count or requeued.modified_count or expired.modified_count:
        logger.warning(
            "Recovered stale tasks: requeued=%d failed=%d expired=%d",
            requeued.modified_count, exhausted.modified_count, expired.modified_count,
        )


task_queue = TaskQueue()
