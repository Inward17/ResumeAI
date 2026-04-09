"""
Evaluation Routes — Store interview evaluation scores in the evaluations collection.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict

from app.database import db

router = APIRouter(prefix="/jobs", tags=["evaluations"])


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


@router.post("/{job_id}/candidates/{candidate_id}/evaluation")
async def submit_evaluation(job_id: str, candidate_id: str, evaluation: EvaluationSubmission):
    """
    Store the interviewer's evaluation of a candidate.
    Saves per-question keyword scores and the aggregate score.
    """
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

    print(f"[Evaluation] ✅ Stored evaluation for {candidate_id} → job {job_id}: {evaluation.total_score:.1f}%")

    return {
        "status": "success",
        "message": "Evaluation submitted",
        "total_score": evaluation.total_score,
    }


@router.get("/{job_id}/candidates/{candidate_id}/evaluation")
async def get_evaluation(job_id: str, candidate_id: str):
    """Retrieve a stored evaluation for a candidate+job pair."""
    doc = await db.evaluations.find_one(
        {"job_id": job_id, "candidate_id": candidate_id}
    )
    if not doc:
        raise HTTPException(404, "No evaluation found")

    doc.pop("_id", None)
    return {"status": "success", "evaluation": doc}
