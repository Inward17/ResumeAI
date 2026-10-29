"""
Job Routes - CRUD operations for job postings
"""
import asyncio
from datetime import datetime
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from app.auth import AuthUser, get_current_user
from app.database import db
from app.org import ensure_org

SHORTLISTED_STATUSES = ["Shortlisted", "Interview", "Offer"]
JobStatus = Literal["Active", "Draft", "Closed"]

router = APIRouter(prefix="/jobs", tags=["jobs"])


# Pydantic models
class JobCreate(BaseModel):
    job_title: str
    job_description: str
    required_skills: List[str]
    preferred_skills: Optional[List[str]] = []
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    is_active: bool = True
    # "Draft" jobs used to be saved as active (is_active was the only field)
    status: Optional[JobStatus] = None
    department: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)


class JobUpdate(BaseModel):
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    status: Optional[JobStatus] = None
    department: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)


class JobResponse(BaseModel):
    id: str
    job_title: str
    job_description: str
    required_skills: List[str]
    preferred_skills: List[str] = []
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    is_active: bool
    status: JobStatus = "Active"
    department: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posted_at: datetime
    total_candidates: int = 0
    screened: int = 0
    shortlisted: int = 0


def job_helper(job: dict) -> dict:
    """Convert MongoDB document to response format"""
    return {
        "id": str(job["_id"]),
        "job_title": job.get("job_title", ""),
        "job_description": job.get("job_description", ""),
        "required_skills": job.get("required_skills", []),
        "preferred_skills": job.get("preferred_skills", []),
        "experience_level": job.get("experience_level"),
        "employment_type": job.get("employment_type"),
        "location": job.get("location"),
        "is_active": job.get("is_active", True),
        # Jobs saved before "status" existed only have is_active
        "status": job.get("status") or ("Active" if job.get("is_active", True) else "Closed"),
        "department": job.get("department"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "posted_at": job.get("posted_at", datetime.utcnow()),
        "total_candidates": job.get("total_candidates", 0),
        "screened": job.get("screened", 0),
        "shortlisted": job.get("shortlisted", 0),
    }


async def _with_candidate_counts(jobs: List[dict]) -> List[dict]:
    """Fill total/screened/shortlisted from applications in one aggregation."""
    if not jobs:
        return jobs
    counts = {}
    async for row in db.applications.aggregate([
        {"$match": {"job_id": {"$in": [job["id"] for job in jobs]}}},
        {"$group": {
            "_id": "$job_id",
            "total": {"$sum": 1},
            "screened": {"$sum": {"$cond": [{"$ne": ["$status", "New"]}, 1, 0]}},
            "shortlisted": {"$sum": {"$cond": [{"$in": ["$status", SHORTLISTED_STATUSES]}, 1, 0]}},
        }},
    ]):
        counts[row["_id"]] = row
    for job in jobs:
        row = counts.get(job["id"], {})
        job["total_candidates"] = row.get("total", 0)
        job["screened"] = row.get("screened", 0)
        job["shortlisted"] = row.get("shortlisted", 0)
    return jobs


def _sync_status(data: dict) -> dict:
    """Keep ``status`` and the legacy ``is_active`` flag consistent."""
    if data.get("status"):
        data["is_active"] = data["status"] == "Active"
    elif "is_active" in data and data["is_active"] is not None:
        data["status"] = "Active" if data["is_active"] else "Closed"
    return data


async def _owned_job_filter(job_id: str, user: AuthUser) -> dict:
    """Jobs are shared by everyone in the caller's organization."""
    try:
        obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    return {"_id": obj_id, "org_id": await ensure_org(user)}


@router.get("", response_model=List[JobResponse])
async def get_jobs(user: AuthUser = Depends(get_current_user)):
    """Fetch the organization's jobs"""
    jobs = []
    async for job in db.jobs.find({"org_id": await ensure_org(user)}, {"jd_embedding": 0}).sort("posted_at", -1):
        jobs.append(job_helper(job))
    return await _with_candidate_counts(jobs)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user: AuthUser = Depends(get_current_user)):
    """Fetch a single job by ID"""
    job = await db.jobs.find_one(await _owned_job_filter(job_id, user))
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return (await _with_candidate_counts([job_helper(job)]))[0]


@router.post("", response_model=JobResponse)
async def create_job(job: JobCreate, user: AuthUser = Depends(get_current_user)):
    """Create a new job posting"""
    from app.services.embedding_service import generate_embedding
    
    job_data = _sync_status(job.model_dump())
    job_data["owner_uid"] = user.uid
    job_data["org_id"] = await ensure_org(user)
    job_data["posted_at"] = datetime.utcnow()
    job_data["total_candidates"] = 0
    job_data["screened"] = 0
    job_data["shortlisted"] = 0
    
    # Generate JD embedding for skills matching
    jd_text = f"{job.job_title} {job.job_description} " + \
              f"required skills: {', '.join(job.required_skills)} " + \
              f"preferred skills: {', '.join(job.preferred_skills or [])}"
    job_data["jd_embedding"] = await asyncio.to_thread(generate_embedding, jd_text)
    
    result = await db.jobs.insert_one(job_data)
    
    created_job = await db.jobs.find_one({"_id": result.inserted_id})
    return job_helper(created_job)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, job: JobUpdate, user: AuthUser = Depends(get_current_user)):
    """Update an existing job posting"""
    owned = await _owned_job_filter(job_id, user)
    obj_id = owned["_id"]
    
    # Get existing job
    existing_job = await db.jobs.find_one(owned)
    if not existing_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build update data (only non-None fields)
    update_data = _sync_status({k: v for k, v in job.model_dump().items() if v is not None})
    
    if update_data:
        await db.jobs.update_one({"_id": obj_id}, {"$set": update_data})
    
    updated_job = await db.jobs.find_one({"_id": obj_id})
    return (await _with_candidate_counts([job_helper(updated_job)]))[0]


@router.delete("/{job_id}")
async def delete_job(job_id: str, user: AuthUser = Depends(get_current_user)):
    """Delete a job posting"""
    result = await db.jobs.delete_one(await _owned_job_filter(job_id, user))
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted successfully"}
