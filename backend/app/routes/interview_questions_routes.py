"""
Interview Questions Routes — API endpoint for generating AI-powered interview questions.
Uses Groq API, caches results in the applications collection.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from app.database import db
from app.services.interview_questions_service import generate_interview_questions

router = APIRouter(prefix="/jobs", tags=["interview-questions"])


@router.get("/{job_id}/candidates/{candidate_id}/interview-questions")
async def get_interview_questions(job_id: str, candidate_id: str):
    """
    Get AI-generated interview questions for a candidate + job pair.
    Generates via Groq on first call, then caches in applications collection.
    """

    # ── 1. Check cache ───────────────────────────────────────────────────
    application = await db.applications.find_one({
        "job_id": job_id,
        "candidate_id": candidate_id,
    })

    if application:
        cached = application.get("interview_questions")
        if cached:
            return {"status": "success", "questions": cached, "cached": True}

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
    print(f"[InterviewQ] Generating questions for candidate={candidate_id}, job={job_id}...")
    questions = await generate_interview_questions(
        job=dict(job),
        candidate=dict(candidate),
        verification=dict(verification) if verification else None,
    )

    if questions:
        # ── 4. Cache in applications collection (upsert) ─────────────────
        await db.applications.update_one(
            {"job_id": job_id, "candidate_id": candidate_id},
            {"$set": {"interview_questions": questions}},
            upsert=True,
        )
        print(f"[InterviewQ] ✅ Cached {len(questions)} questions for {candidate_id}")
        return {"status": "success", "questions": questions, "cached": False}
    else:
        # Groq failed — return a fallback set
        fallback = [
            {
                "id": 1,
                "question": "Tell us about your most challenging technical project and how you overcame the key obstacles.",
                "tags": ["Problem Solving", "Technical Depth", "Resilience"],
            },
            {
                "id": 2,
                "question": "How do you approach learning a new technology or framework when joining a new team?",
                "tags": ["Learning Agility", "Adaptability", "Self-Motivation"],
            },
            {
                "id": 3,
                "question": "Describe a time you had to make a trade-off between code quality and delivery speed.",
                "tags": ["Pragmatism", "Code Quality", "Time Management"],
            },
        ]
        return {"status": "fallback", "questions": fallback, "cached": False}
