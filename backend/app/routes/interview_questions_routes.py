"""
Interview Questions Routes — API endpoint for generating AI-powered interview questions.
Uses Groq API, caches results in the applications collection.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthUser, get_current_user, require_job_owner
from app.org import ensure_org
from app.services.quota import rate_limit, use_quota
from bson import ObjectId

from app.database import db
from app.services.interview_questions_service import generate_interview_questions

router = APIRouter(prefix="/jobs", tags=["interview-questions"])


@router.get("/{job_id}/candidates/{candidate_id}/interview-questions", dependencies=[Depends(require_job_owner)])
async def get_interview_questions(job_id: str, candidate_id: str, regenerate: bool = False,
                                  user: AuthUser = Depends(get_current_user)):
    """
    Get AI-generated interview questions for a candidate + job pair.
    Generates via Groq on first call, then caches in applications collection.

    Cached questions are "stale" when the cover letter analysis changed since they
    were generated; they are only regenerated when the caller asks (regenerate=true).
    """
    rate_limit(user.uid, "ai")

    # ── 1. Check cache ───────────────────────────────────────────────────
    application = await db.applications.find_one({
        "job_id": job_id,
        "candidate_id": candidate_id,
    })

    # Only candidates who applied to this job; 404 so other workspaces' ids aren't revealed
    if not application:
        raise HTTPException(404, "Candidate not found")
    letter = application.get("cover_letter") or {}
    letter_at = letter.get("analyzed_at") if letter.get("analysis_status") == "done" else None
    cached = application.get("interview_questions")
    if cached and not regenerate:
        stale = application.get("interview_questions_cover_letter_at") != letter_at
        return {"status": "success", "questions": cached, "cached": True, "stale": stale}

    # ── 2. Fetch context data ────────────────────────────────────────────
    # Job
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(400, "Invalid job ID")
    if not job:
        raise HTTPException(404, "Job not found")

    # Candidate
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    # Verification data (optional — may not exist)
    verification = await db.verification_data.find_one({
        "$or": [
            {"candidateId": candidate_id},
            {"candidate_id": candidate_id},
        ]
    })

    # ── 3. Generate questions via Groq ───────────────────────────────────
    # Only uncached requests reach Groq, so only they count against the daily quota
    await use_quota(await ensure_org(user), "ai_call", feature="interview_questions")
    print(f"[InterviewQ] Generating questions for candidate={candidate_id}, job={job_id}...")
    questions = await generate_interview_questions(
        job=dict(job),
        candidate=dict(candidate),
        verification=dict(verification) if verification else None,
        cover_letter=letter.get("analysis") if letter_at else None,
    )

    if questions:
        # ── 4. Cache on the existing application (never create one) ──────
        await db.applications.update_one(
            {"_id": application["_id"]},
            {"$set": {"interview_questions": questions, "interview_questions_cover_letter_at": letter_at}},
        )
        print(f"[InterviewQ] ✅ Cached {len(questions)} questions for {candidate_id}")
        return {"status": "success", "questions": questions, "cached": False, "stale": False}
    # No made-up fallback: the interviewer should know the AI part isn't working
    raise HTTPException(503, "The AI service is down, so interview questions can't be generated right now. Try again later.")
