import os
import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from app.database import db
from app.services.parser import parse_resume
from app.utils.file_utils import read_file


router = APIRouter(prefix="/jobs", tags=["resume"])

RESUMES_DIR = os.getenv("RESUMES_DIR", "resumes")
os.makedirs(RESUMES_DIR, exist_ok=True)


async def _parse_and_store(filename: str, candidate_id: str):
    """Background task to parse resume"""
    try:
        filepath = os.path.join(RESUMES_DIR, filename)
        with open(filepath, "rb") as f:
            content = f.read()
        
        text = read_file(filename, content)
        if not text:
            raise ValueError("Empty file")
        
        parsed = await parse_resume(text)
        
        # Store in DB
        candidate_doc = {
            "candidate_id": candidate_id,
            "filename": filename,
            "uploaded_at": datetime.utcnow(),
            "parsed": parsed,
            "status": "parsed",
            "jd_match_score": None,
            "verification_score": None,
            "verification_evidence": None
        }
        await db.candidates.insert_one(candidate_doc)
        
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"parsed": True}}}
        )
    except Exception as e:
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": str(e)}}
        )


@router.post("/{job_id}/upload")
async def upload_resumes(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Upload resumes for parsing"""
    saved = []
    
    for file in files:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("pdf", "docx", "doc", "txt"):
            raise HTTPException(400, f"Unsupported file type: {ext}")
        
        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        dest = os.path.join(RESUMES_DIR, unique_name)
        
        # Save file
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create task
        await db.tasks.insert_one({
            "task_id": unique_name,
            "job_id": job_id,
            "filename": unique_name,
            "type": "parse",
            "status": "queued",
            "created_at": datetime.utcnow()
        })
        
        # Schedule parsing
        background_tasks.add_task(_parse_and_store, unique_name, unique_name)
        saved.append({"filename": file.filename, "stored_as": unique_name})
    
    return {"status": "accepted", "saved": saved}