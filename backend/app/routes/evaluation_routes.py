"""
Evaluation Routes — Store interview evaluation scores in the evaluations collection.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from app.auth import AuthUser, get_current_user, require_job_owner
from app.services.status_history import set_status
from pydantic import BaseModel
from typing import List, Dict

from app.database import db

router = APIRouter(prefix="/jobs", tags=["evaluations"])


async def _require_application(job_id: str, candidate_id: str) -> None:
    """404 unless the candidate applied to this job (the job's workspace is checked by require_job_owner)."""
    if not await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 1}):
        raise HTTPException(404, "Candidate not found")

# Statuses (old spellings included) that move to "Interview" once an evaluation is submitted
EARLY_STATUSES = ["Under Review", "Shortlisted", "New", "Reviewing", "Pending Review", "new", "shortlisted", None]


class QuestionEvaluation(BaseModel):
    question_id: int
    question: str
    total_tags: int
    selected_tags: List[str]
    score: float  # selected / total


class EvaluationSubmission(BaseModel):
    candidate_name: str = ""
    job_title: str = ""
    questions: List[QuestionEvaluation]
    total_score: float  # aggregate percentage
    total_selected: int
    total_possible: int


@router.post("/{job_id}/candidates/{candidate_id}/evaluation", dependencies=[Depends(require_job_owner)])
async def submit_evaluation(job_id: str, candidate_id: str, evaluation: EvaluationSubmission,
                            user: AuthUser = Depends(get_current_user)):
    """
    Store the interviewer's evaluation of a candidate.
    Saves per-question keyword scores and the aggregate score.
    """
    await _require_application(job_id, candidate_id)
    doc = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "candidate_name": evaluation.candidate_name,
        "job_title": evaluation.job_title,
        "questions": [q.model_dump() for q in evaluation.questions],
        "total_score": evaluation.total_score,
        "total_selected": evaluation.total_selected,
        "total_possible": evaluation.total_possible,
        "submitted_at": datetime.utcnow(),
    }

    # Upsert: one evaluation per candidate+job pair
    await db.evaluations.update_one(
        {"job_id": job_id, "candidate_id": candidate_id},
        {"$set": doc},
        upsert=True,
    )

    # An interviewed candidate is at the Interview stage; later stages are left alone
    _, moved = await set_status(job_id, candidate_id, "Interview", user.uid, only_from=EARLY_STATUSES)

    print(f"[Evaluation] ✅ Stored evaluation for {candidate_id} → job {job_id}: {evaluation.total_score:.1f}%")

    return {
        "status": "success",
        "message": "Evaluation submitted",
        "total_score": evaluation.total_score,
        "candidate_status": "Interview" if moved else None,
    }


@router.get("/{job_id}/candidates/{candidate_id}/evaluation", dependencies=[Depends(require_job_owner)])
async def get_evaluation(job_id: str, candidate_id: str):
    """Retrieve a stored evaluation for a candidate+job pair."""
    await _require_application(job_id, candidate_id)
    doc = await db.evaluations.find_one(
        {"job_id": job_id, "candidate_id": candidate_id}
    )
    if not doc:
        raise HTTPException(404, "No evaluation found")

    doc.pop("_id", None)
    return {"status": "success", "evaluation": doc}
