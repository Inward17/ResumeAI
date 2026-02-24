import os
import asyncio
import uuid
import random
from bson import ObjectId
from typing import List
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from app.database import db
from app.services.parser import parse_resume
from app.services.unified_verification import unified_verification_service
from app.utils.file_utils import read_file


# Global semaphore to limit concurrent resume parsing to 1 at a time
# This prevents Gemini rate limits and "stuck" requests
parsing_semaphore = asyncio.Semaphore(1)


router = APIRouter(prefix="/jobs", tags=["resume"])

RESUMES_DIR = os.getenv("RESUMES_DIR", "resumes")
os.makedirs(RESUMES_DIR, exist_ok=True)


def extract_github_username(github_url: str) -> str | None:
    """Extract GitHub username from URL or return as-is if already username"""
    if not github_url:
        return None
    github_url = github_url.strip()
    # Handle github.com URLs
    if "github.com" in github_url:
        parts = github_url.rstrip("/").split("/")
        return parts[-1] if parts else None
    # Already a username
    return github_url


def extract_linkedin_url(linkedin: str) -> str | None:
    """Ensure LinkedIn is a full URL"""
    if not linkedin:
        return None
    linkedin = linkedin.strip()
    if linkedin.startswith("http"):
        return linkedin
    if "linkedin.com" in linkedin:
        return f"https://{linkedin}"
    return f"https://linkedin.com/in/{linkedin}"


async def _parse_and_store(filename: str, candidate_id: str):
    """Background task to parse resume and store in candidates collection"""
    try:
        filepath = os.path.join(RESUMES_DIR, filename)
        filepath = os.path.join(RESUMES_DIR, filename)
        
        # Read file in thread to avoid blocking event loop
        with open(filepath, "rb") as f:
            content = await asyncio.to_thread(f.read)
        
        text = await asyncio.to_thread(read_file, filename, content)
        if not text:
            raise ValueError("Empty file")
        
        # Serialize parsing to avoid rate limits/hanging
        async with parsing_semaphore:
            print(f"Parsing resume for {candidate_id}...")
            parsed = await parse_resume(text)
            print(f"Parsing completed for {candidate_id}")
        
        # Extract personal info for verification
        personal_info = parsed.get("personal_info", {})
        github_url = personal_info.get("github")
        linkedin_url = personal_info.get("linkedin")
        
        # Extract education and experience for verification
        education = parsed.get("education") or []
        experience = parsed.get("experience") or []
        
        # Extract company names from experience strings
        experience_companies = []
        for exp in experience:
            if isinstance(exp, str):
                # Try to extract company name (usually after "at" or before "|")
                if " at " in exp.lower():
                    company = exp.lower().split(" at ")[-1].split("|")[0].strip()
                    experience_companies.append(company)
                elif "|" in exp:
                    company = exp.split("|")[0].strip()
                    experience_companies.append(company)
                else:
                    experience_companies.append(exp.split(",")[0].strip())
        
        # Generate skills embedding for JD matching
        from app.services.embedding_service import generate_embedding
        skills_text = parsed.get("skills", "") or ""
        skills_embedding = generate_embedding(skills_text)
        
        # Store in candidates collection
        candidate_doc = {
            "candidate_id": candidate_id,
            "filename": filename,
            "uploaded_at": datetime.utcnow(),
            "parsed": parsed,
            "status": "parsed",
            "jd_match_score": None,
            "verification_score": None,
            "verification_evidence": None,
            # Store extracted identifiers for linking
            "github_username": extract_github_username(github_url),
            "linkedin_url": extract_linkedin_url(linkedin_url),
            # Store education and experience for verification
            "education": education,
            "experience_companies": experience_companies,
            # NEW: Extracted entity names for verification
            "universities": parsed.get("university") or [],
            "companies": parsed.get("company") or [],
            # NEW: Skills embedding for JD matching
            "skills_embedding": skills_embedding
        }
        await db.candidates.insert_one(candidate_doc)
        
        # Update task status
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "parsed", "parsed_at": datetime.utcnow()}}
        )
        
    except Exception as e:
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": str(e)}}
        )


async def _run_unified_verification(candidate_id: str, job_id: str):
    """Background task to run unified verification after parsing"""
    try:
        # Get candidate data
        candidate = await db.candidates.find_one({"candidate_id": candidate_id})
        if not candidate:
            print(f"Candidate {candidate_id} not found for verification")
            return
        
        github_username = candidate.get("github_username")
        linkedin_url = candidate.get("linkedin_url")
        parsed = candidate.get("parsed", {})
        
        # Build profile data for web search verification
        # Use LinkedIn-like structure for compatibility with verifier
        profile_data = None
        if parsed:
            profile_data = {
                "publicIdentifier": candidate_id,
                "educations": [{"title": edu} for edu in (parsed.get("education") or [])],
                "experiences": [{"subtitle": exp} for exp in (parsed.get("experience") or [])]
            }
        
        # Update task status
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "verifying", "verification_started_at": datetime.utcnow()}}
        )
        
        # Run verification
        if github_username or linkedin_url or profile_data:
            result = await unified_verification_service.run_unified_verification(
                candidate_id=candidate_id,
                github_username=github_username,
                linkedin_url=linkedin_url,
                profile_data=profile_data,
                parsed_resume=parsed,  # ← pass full parsed resume for project→repo matching
            )
            
            # Update candidate with verification score
            match_score = result.matchScore
            if match_score:
                await db.candidates.update_one(
                    {"candidate_id": candidate_id},
                    {"$set": {
                        "verification_score": match_score.overallCredibility,
                        "status": "verified"
                    }}
                )
            
            # Update task as done
            await db.tasks.update_one(
                {"task_id": candidate_id},
                {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"verified": True}}}
            )
        else:
            # No verification sources available
            await db.tasks.update_one(
                {"task_id": candidate_id},
                {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"verified": False, "reason": "No verification sources"}}}
            )
        
        # Create application record after verification
        await _create_application(candidate_id, job_id)
            
    except Exception as e:
        print(f"Verification failed for {candidate_id}: {e}")
        await db.tasks.update_one(
            {"task_id": candidate_id},
            {"$set": {"status": "verification_failed", "error": str(e)}}
        )
        # Still create application even if verification failed
        await _create_application(candidate_id, job_id)


async def _create_application(candidate_id: str, job_id: str):
    """Create application record linking candidate to job with scores"""
    try:
        # Get verification data for scores
        verification = await db.verification_data.find_one({"candidateId": candidate_id})
        
        # Calculate verification_bonus from verificationStatus
        verification_bonus = 0
        if verification and verification.get("verificationStatus"):
            status = verification["verificationStatus"]
            # +5 for each verified source
            if status.get("github") == "verified":
                verification_bonus += 5
            if status.get("linkedin") == "verified":
                verification_bonus += 5
            if status.get("webCheck") == "verified":
                verification_bonus += 5
        
        # Get GitHub verification score from githubData (0-100 scale)
        github_verification_score = 0
        if verification and verification.get("githubData"):
            github_verification_score = verification["githubData"].get("score", 0)
        
        # Calculate JD match score using vector similarity (0-5 marks)
        from app.services.jd_matching_service import calculate_jd_match, save_evaluation
        jd_match = await calculate_jd_match(candidate_id, job_id)
        
        # Save JD match evaluation to evaluations collection
        await save_evaluation(candidate_id, job_id, jd_match)
        
        # Use real scores or mock if not available
        match_score = verification.get("matchScore", {}) if verification else {}
        
        application_doc = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "application_date": datetime.utcnow(),
            "status": "Under Review",
            "score_details": {
                "overall_score": match_score.get("overallCredibility", random.randint(60, 90)),
                "skills_match_score": github_verification_score,  # GitHub score (0-100)
                "experience_match_score": match_score.get("experienceMatch", random.randint(20, 35)),
                "verification_bonus": verification_bonus,
                # JD match breakdown (vector similarity based)
                "jd_match": {
                    "resume_match": jd_match["resume_match"],       # 0-2 marks
                    "github_match": jd_match["github_match"],       # 0-3 marks
                    "total": jd_match["total"],                     # 0-5 marks
                },
                # Separate JD match total for easy access
                "jd_match_score": jd_match["total"]  # 0-5 marks
            },
            "recruiter_notes": ""
        }
        
        await db.applications.insert_one(application_doc)
        print(f"Created application for candidate {candidate_id} to job {job_id} with Skills: {github_verification_score}%, JD: {jd_match['total']}/5")
        
    except Exception as e:
        print(f"Failed to create application for {candidate_id}: {e}")


async def _parse_and_verify(filename: str, candidate_id: str, job_id: str):
    """Combined background task: parse resume, then run verification"""
    await _parse_and_store(filename, candidate_id)
    
    # Check if parsing succeeded before verification
    task = await db.tasks.find_one({"task_id": candidate_id})
    if task and task.get("status") != "failed":
        await _run_unified_verification(candidate_id, job_id)


@router.post("/{job_id}/upload")
async def upload_resumes(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Upload resumes for parsing and verification"""
    saved = []
    
    for file in files:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("pdf", "docx", "doc", "txt"):
            raise HTTPException(400, f"Unsupported file type: {ext}")
        
        # Generate unique candidate_id using UUID
        candidate_id = str(uuid.uuid4())
        unique_name = f"{candidate_id}_{file.filename}"
        dest = os.path.join(RESUMES_DIR, unique_name)
        
        # Save file
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Create task
        await db.tasks.insert_one({
            "task_id": candidate_id,
            "job_id": job_id,
            "filename": unique_name,
            "type": "parse_and_verify",
            "status": "queued",
            "created_at": datetime.utcnow()
        })
        
        # Schedule parsing + verification (now with job_id)
        background_tasks.add_task(_parse_and_verify, unique_name, candidate_id, job_id)
        saved.append({
            "filename": file.filename, 
            "stored_as": unique_name,
            "candidate_id": candidate_id
        })
    
    return {"status": "accepted", "saved": saved}


@router.put("/{job_id}/candidates/{candidate_id}/status")
async def update_candidate_status(job_id: str, candidate_id: str, status_update: dict):
    """Update candidate application status"""
    new_status = status_update.get("status")
    if not new_status:
        raise HTTPException(400, "Status is required")
        
    result = await db.applications.update_one(
        {"job_id": job_id, "candidate_id": candidate_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(404, "Application not found")
        
    return {"status": "success", "new_status": new_status}


@router.get("/{job_id}/candidates")
async def get_job_candidates(job_id: str):
    """Get all candidates for a job from applications collection"""
    applications = await db.applications.find({"job_id": job_id}).to_list(length=100)
    
    result = []
    for app in applications:
        candidate_id = app.get("candidate_id")
        
        # Get candidate data
        candidate = await db.candidates.find_one({"candidate_id": candidate_id})
        parsed = candidate.get("parsed", {}) if candidate else {}
        personal_info = parsed.get("personal_info", {})
        
        # Get verification data for additional info
        verification = await db.verification_data.find_one({"candidateId": candidate_id})
        
        # Get job for skills comparison
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        required_skills = job.get("required_skills", []) if job else []
        
        # Calculate real skill matches
        candidate_skills = parsed.get("skills", "")
        if isinstance(candidate_skills, list):
            candidate_skills = ", ".join(candidate_skills)
        candidate_skills = candidate_skills.lower() if candidate_skills else ""
        
        skill_matches = []
        for skill in required_skills:
            skill_lower = skill.lower()
            found = skill_lower in candidate_skills
            # Simple scoring: 10 if found, 0 if not (can be improved with fuzzy match)
            score = 10 if found else 0
            skill_matches.append({
                "skill": skill,
                "score": score,
                "found": found
            })

        result.append({
            "candidate_id": candidate_id,
            "name": personal_info.get("full_name", "Unknown"),
            "email": personal_info.get("email", ""),
            "phone": personal_info.get("phone", ""),
            "status": app.get("status", "Under Review"),
            "application_date": app.get("application_date"),
            "score_details": app.get("score_details", {}),
            "jd_match_score": app.get("score_details", {}).get("skills_match_score", 0),
            "verification_score": app.get("score_details", {}).get("overall_score", 0),
            "filename": candidate.get("filename") if candidate else None,
            "verification_status": verification.get("verificationStatus") if verification else None,
            "skill_matches": skill_matches  # NEW: Real skill matches
        })
    
    return {"job_id": job_id, "candidates": result}