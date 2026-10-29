"""
Standalone resume-processing worker.

Run extra workers next to (or instead of) the API process to process large
batches faster — all of them share the queue in the hosted database:

    cd backend
    RESUME_WORKERS=8 python -m app.worker

Set RESUME_WORKERS=0 on the API process to make it API-only.
"""
import asyncio
import logging
import signal

from dotenv import load_dotenv

load_dotenv()

from app.database import client, ensure_indexes, ping_database
from app.routes.resume import process_resume_task
from app.services.task_queue import RESUME_WORKERS, task_queue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main():
    if not await ping_database():
        raise SystemExit("Cannot reach MongoDB — check MONGO_URL")
    await ensure_indexes()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass

    task_queue.start(process_resume_task, max(RESUME_WORKERS, 1))
    try:
        await stop.wait()
    finally:
        await task_queue.stop()
        client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
