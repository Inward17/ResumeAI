"""
Every change of an application's status goes through here, so the Reports page
can measure time in stage: each change appends {status, at, by} to
``applications.status_history`` (the newest HISTORY_LIMIT entries are kept).

Applications created before this existed have no history; reports fall back to
their timestamps and say the data is partial.
"""
from datetime import datetime

from app.database import db

HISTORY_LIMIT = 50


def history_entry(status: str, by: str | None, at: datetime | None = None) -> dict:
    return {"status": status, "at": at or datetime.utcnow(), "by": by}


def push_entry(entry: dict) -> dict:
    """The $push clause that appends ``entry`` and keeps the history bounded."""
    return {"status_history": {"$each": [entry], "$slice": -HISTORY_LIMIT}}


async def set_status(job_id: str, candidate_id: str, status: str, by: str | None, only_from: list | None = None) -> tuple[bool, bool]:
    """Set the application's status and record the change. Returns (found, changed).

    An unchanged status is not recorded again. ``only_from`` limits the change to
    applications currently in one of those statuses.
    """
    now = datetime.utcnow()
    current = {"$nin": [status]} if only_from is None else {"$in": [s for s in only_from if s != status]}
    result = await db.applications.update_one(
        {"job_id": job_id, "candidate_id": candidate_id, "status": current},
        {"$set": {"status": status, "updated_at": now}, "$push": push_entry(history_entry(status, by, now))},
    )
    if result.modified_count:
        return True, True
    found = await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 1})
    return bool(found), False
