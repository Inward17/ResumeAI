"""
Job Routes - CRUD operations for job postings
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId

from app.database import db

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


class JobUpdate(BaseModel):
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


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
        "posted_at": job.get("posted_at", datetime.utcnow()),
        "total_candidates": job.get("total_candidates", 0),
        "screened": job.get("screened", 0),
        "shortlisted": job.get("shortlisted", 0),
    }


@router.get("", response_model=List[JobResponse])
async def get_jobs():
    """Fetch all jobs"""
    jobs = []
    async for job in db.jobs.find().sort("posted_at", -1):
        jobs.append(job_helper(job))
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Fetch a single job by ID"""
    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job_helper(job)


@router.post("", response_model=JobResponse)
async def create_job(job: JobCreate):
    """Create a new job posting"""
    from app.services.embedding_service import generate_embedding
    
    job_data = job.model_dump()
    job_data["posted_at"] = datetime.utcnow()
    job_data["total_candidates"] = 0
    job_data["screened"] = 0
    job_data["shortlisted"] = 0
    
    # Generate JD embedding for skills matching
    jd_text = f"{job.job_title} {job.job_description} " + \
              f"required skills: {', '.join(job.required_skills)} " + \
              f"preferred skills: {', '.join(job.preferred_skills or [])}"
    job_data["jd_embedding"] = generate_embedding(jd_text)
    
    result = await db.jobs.insert_one(job_data)
    
    created_job = await db.jobs.find_one({"_id": result.inserted_id})
    return job_helper(created_job)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, job: JobUpdate):
    """Update an existing job posting"""
    try:
        obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    # Get existing job
    existing_job = await db.jobs.find_one({"_id": obj_id})
    if not existing_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Build update data (only non-None fields)
    update_data = {k: v for k, v in job.model_dump().items() if v is not None}
    
    if update_data:
        await db.jobs.update_one({"_id": obj_id}, {"$set": update_data})
    
    updated_job = await db.jobs.find_one({"_id": obj_id})
    return job_helper(updated_job)


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete a job posting"""
    try:
        obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    result = await db.jobs.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"message": "Job deleted successfully"}
