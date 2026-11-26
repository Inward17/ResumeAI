"""On-demand AI review of a candidate's deployed projects.

POST starts a review in the background (one at a time per candidate, at most one
full run per candidate every 10 minutes); GET returns the discovered projects and
the review's progress and results. Results are stored on the candidate (projects
belong to the candidate, not the job); a new run replaces the previous one.
Evidence only: nothing here touches role match, credibility or any score.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthUser, get_current_user, require_job_action, require_job_owner
from app.database import db
from app.org import ensure_org
from app.services.quota import rate_limit, refund_quota, use_quota
from app.services.project_reviews import discovery, review, visit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["project-reviews"])

COOLDOWN = timedelta(minutes=10)
STALE = timedelta(minutes=15)  # a "running" review older than this was interrupted (restart, crash)
PROJECT_TIMEOUT_SECONDS = 240
AI_DOWN = "Review unavailable: the AI service is down"
_tasks = set()  # strong references so background runs aren't garbage-collected


def max_projects() -> int:
    return max(1, int(os.getenv("PROJECT_REVIEW_MAX_PROJECTS", "3")))


async def _context(job_id: str, candidate_id: str):
    if not await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 1}):
        raise HTTPException(404, "Candidate not found")
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    verification = await db.verification_data.find_one(
        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]},
        {"portfoliosData": 1, "githubData.github_v2_data.homepages": 1,
         "githubData.github_v2_data.resumeVerification.matches": 1})
    return candidate, verification


def _is_stale(state: dict) -> bool:
    started = state.get("started_at")
    return state.get("status") == "running" and isinstance(started, datetime) and datetime.utcnow() - started > STALE


def _public_state(state: dict | None, job_id: str) -> dict | None:
    if not state:
        return None
    # Job relevance was judged against the job the review was run from; never show it on another job
    other_job = state.get("job_id") != job_id
    projects = []
    for p in state.get("projects") or []:
        shot = p.get("screenshot")
        review_ = p.get("review")
        if other_job and isinstance(review_, dict):
            review_ = {k: v for k, v in review_.items() if k != "job_relevance"}
        projects.append({
            **{k: v for k, v in p.items() if k not in ("pages", "screenshot")},
            "review": review_,
            "pages": [{k: pg.get(k) for k in ("url", "title", "status_code", "failed")} for pg in p.get("pages") or []],
            "screenshot": f"data:image/jpeg;base64,{shot}" if shot else None,
        })
    status, error = state.get("status"), state.get("error")
    if _is_stale(state):
        status, error = "failed", "The review was interrupted. Run it again."
    return {"status": status, "error": error, "job_id": state.get("job_id"), "other_job": other_job,
            "requested_by": (state.get("requested_by") or {}).get("email"),
            "requested_at": state.get("requested_at"), "reviewed_at": state.get("reviewed_at"), "projects": projects}


@router.get("/{job_id}/candidates/{candidate_id}/project-reviews")
async def get_project_reviews(job_id: str, candidate_id: str, job: dict = Depends(require_job_owner)):
    candidate, verification = await _context(job_id, candidate_id)
    projects = discovery.all_projects(candidate, verification)
    selected = {p["id"] for p in discovery.select(projects, job, max_projects())}
    state = candidate.get("project_review")
    return {
        "firecrawl_configured": visit.configured(),
        "max_projects": max_projects(),
        "max_pages": visit.max_pages(),
        "projects": [{**p, "selected": p["id"] in selected} for p in projects],
        "review": _public_state(state, job_id),
        "discrepancies": review.discrepancies((state or {}).get("projects")),
    }


@router.post("/{job_id}/candidates/{candidate_id}/project-reviews", status_code=202)
async def start_project_reviews(job_id: str, candidate_id: str, retry: bool = False,
                                job: dict = Depends(require_job_action("ai.run")), user: AuthUser = Depends(get_current_user)):
    """Start a review. retry=true re-runs only the AI step for projects whose review failed because the
    AI was down, reusing the stored visit (no Firecrawl credits, no cooldown)."""
    rate_limit(user.uid, "ai")
    candidate, verification = await _context(job_id, candidate_id)
    now = datetime.utcnow()
    not_running = [{"project_review.status": {"$ne": "running"}},
                   {"project_review.status": "running", "project_review.started_at": {"$lt": now - STALE}}]

    if retry:
        update = {"project_review.status": "running", "project_review.started_at": now, "project_review.error": None}
        claim = {"candidate_id": candidate_id, "project_review.projects.review_status": "ai_unavailable", "$or": not_running}
    else:
        if not visit.configured():
            raise HTTPException(503, "Firecrawl not configured, so deployed projects can't be visited.")
        selected = discovery.select(discovery.all_projects(candidate, verification), job, max_projects())
        if not selected:
            raise HTTPException(400, "No deployed project links were found for this candidate.")
        update = {"project_review": {
            "status": "running", "job_id": job_id, "requested_by": {"uid": user.uid, "email": user.email},
            "requested_at": now, "started_at": now, "reviewed_at": None, "error": None,
            "projects": [{**p, "state": "queued"} for p in selected]}}
        claim = {"candidate_id": candidate_id, "$or": [
            {"project_review.status": {"$exists": False}},
            {"project_review.status": {"$ne": "running"}, "project_review.requested_at": {"$lt": now - COOLDOWN}},
            not_running[1]]}

    # One AI call per project reviewed. Charged before the claim (so an over-quota request never
    # claims), and given back if the claim is refused (already running, cooldown, nothing to retry).
    reviewed = max(1, len([p for p in (candidate.get("project_review") or {}).get("projects") or []
                           if p.get("review_status") == "ai_unavailable"])
                   if retry else len(selected))
    org_id = await ensure_org(user)
    await use_quota(org_id, "ai_call", reviewed, feature="project_reviews")

    if not await db.candidates.find_one_and_update(claim, {"$set": update}):
        await refund_quota(org_id, "ai_call", reviewed, feature="project_reviews")
        state = (await db.candidates.find_one({"candidate_id": candidate_id}, {"project_review": 1}) or {}).get("project_review") or {}
        if state.get("status") == "running" and not _is_stale(state):
            raise HTTPException(409, "A project review is already running for this candidate.")
        if retry:
            raise HTTPException(400, "There is no review waiting for the AI to retry.")
        wait = COOLDOWN - (now - state.get("requested_at", now))
        raise HTTPException(429, f"Projects were reviewed moments ago. Try again in {max(1, round(wait.total_seconds() / 60))} min.")

    task = asyncio.create_task(run_review(candidate_id, dict(job), retry=retry))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"status": "running"}


# ── Background run ─────────────────────────────────────────────────

async def _set(candidate_id: str, i: int, **fields):
    await db.candidates.update_one({"candidate_id": candidate_id},
                                   {"$set": {f"project_review.projects.{i}.{k}": v for k, v in fields.items()}})


async def _review_one(candidate_id: str, i: int, project: dict, candidate: dict, job: dict, retry: bool,
                      client: httpx.AsyncClient):
    if not retry:
        await _set(candidate_id, i, state="visiting")
        project = {**project, **await visit.visit(project["url"], client)}
        await _set(candidate_id, i, **{k: project[k] for k in ("site_status", "site_note", "pages", "screenshot", "screenshot_note")})
    if project.get("site_status") != "live":
        await _set(candidate_id, i, state="done", review=None, review_status="skipped",
                   review_note="Not reviewed: " + (project.get("site_note") or "the site could not be visited"))
        return
    await _set(candidate_id, i, state="reviewing")
    try:
        result = await review.review_project(project, project.get("pages") or [], project.get("screenshot"), candidate, job, client)
        await _set(candidate_id, i, state="done", review=result, review_status="done", review_note=None)
    except review.AIUnavailable:
        await _set(candidate_id, i, state="done", review=None, review_status="ai_unavailable", review_note=AI_DOWN)


async def run_review(candidate_id: str, job: dict, retry: bool = False) -> None:
    """Visit and review the claimed projects; failures are recorded per project, never raised."""
    try:
        candidate = await db.candidates.find_one({"candidate_id": candidate_id})
        projects = ((candidate or {}).get("project_review") or {}).get("projects") or []

        async def one(i, p, client):
            try:
                await asyncio.wait_for(_review_one(candidate_id, i, p, candidate, job, retry, client), PROJECT_TIMEOUT_SECONDS)
            except Exception as e:
                logger.warning("Project review failed for candidate %s: %s", candidate_id, type(e).__name__)
                await _set(candidate_id, i, state="failed",
                           review_note="Timed out" if isinstance(e, asyncio.TimeoutError) else "The review failed")

        async with httpx.AsyncClient(follow_redirects=False) as client:
            await asyncio.gather(*(one(i, p, client) for i, p in enumerate(projects)
                                   if not retry or p.get("review_status") == "ai_unavailable"))
        await db.candidates.update_one({"candidate_id": candidate_id}, {"$set": {
            "project_review.status": "done", "project_review.reviewed_at": datetime.utcnow()}})
        # Cached interview questions predate these results: regenerate them on next open.
        # Saved evaluations keep their own copy of the questions.
        await db.applications.update_many({"candidate_id": candidate_id, "interview_questions": {"$exists": True}},
                                          {"$unset": {"interview_questions": ""}})
    except Exception as e:
        logger.warning("Project review run failed for candidate %s: %s", candidate_id, type(e).__name__)
        await db.candidates.update_one({"candidate_id": candidate_id}, {"$set": {
            "project_review.status": "failed", "project_review.error": "The review stopped unexpectedly. Run it again."}})
