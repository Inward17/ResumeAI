import os
import asyncio
import uuid
from bson import ObjectId
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from app.database import db
from app.services.parser import parse_resume
from app.services.unified_verification import unified_verification_service
from app.utils.file_utils import read_file
from app.services.skill_matching.pipeline import run_unified_skill_scoring


# Global semaphore to limit concurrent resume parsing to 1 at a time
# This prevents Gemini rate limits and "stuck" requests
parsing_semaphore = asyncio.Semaphore(1)


router = APIRouter(prefix="/jobs", tags=["resume"])


def compute_skill_matches(
    required_skills: List[str],
    parsed: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Compute a stable 0–10 score for each required skill against the full
    parsed resume.  Checks multiple sections with decreasing weights so the
    score reflects *where* the skill appears, not just whether it exists.

    Score table:
      10 — exact match in skills section
       8 — fuzzy match (≥85%) in skills section (handles "ReactJS" vs "React")
       7 — exact match in experience text
       6 — exact match in project descriptions / names
       4 — fuzzy match (≥75%) anywhere in the resume
       0 — not found

    This function is pure and stateless — no DB or network access.
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        # Graceful degradation: binary scoring if rapidfuzz unavailable
        fuzz = None

    # ── Build searchable text from each resume section ───────────────────
    raw_skills = parsed.get("skills", "") or ""
    if isinstance(raw_skills, list):
        raw_skills = ", ".join(raw_skills)
    skills_text = raw_skills.lower()

    exp_entries = parsed.get("experience", []) or []
    if isinstance(exp_entries, list):
        exp_text = " ".join(
            str(e) if isinstance(e, str)
            else f"{e.get('title','')} {e.get('company','')} {e.get('description','')}"
            for e in exp_entries
        ).lower()
    else:
        exp_text = str(exp_entries).lower()

    proj_entries = parsed.get("projects", []) or []
    if isinstance(proj_entries, list):
        proj_text = " ".join(
            f"{p.get('name','')} {p.get('description','')} {' '.join(p.get('technologies',[]) or [])}"
            if isinstance(p, dict) else str(p)
            for p in proj_entries
        ).lower()
    else:
        proj_text = str(proj_entries).lower()

    full_text = f"{skills_text} {exp_text} {proj_text}"

    results = []
    for skill in required_skills:
        skill_lower = skill.lower()

        # ── Priority 1: exact in skills section ──────────────────────────
        if skill_lower in skills_text:
            results.append({"skill": skill, "score": 10, "found": True,
                            "match_location": "skills_section"})
            continue

        # ── Priority 2: fuzzy in skills section ──────────────────────────
        if fuzz and fuzz.partial_ratio(skill_lower, skills_text) >= 85:
            results.append({"skill": skill, "score": 8, "found": True,
                            "match_location": "skills_section_fuzzy"})
            continue

        # ── Priority 3: exact in experience ──────────────────────────────
        if skill_lower in exp_text:
            results.append({"skill": skill, "score": 7, "found": True,
                            "match_location": "experience"})
            continue

        # ── Priority 4: exact in projects ─────────────────────────────────
        if skill_lower in proj_text:
            results.append({"skill": skill, "score": 6, "found": True,
                            "match_location": "projects"})
            continue

        # ── Priority 5: fuzzy anywhere ────────────────────────────────────
        if fuzz and fuzz.partial_ratio(skill_lower, full_text) >= 75:
            results.append({"skill": skill, "score": 4, "found": True,
                            "match_location": "fuzzy_anywhere"})
            continue

        # ── Not found ────────────────────────────────────────────────────
        results.append({"skill": skill, "score": 0, "found": False,
                        "match_location": "not_found"})

    return results

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


def extract_pdf_hyperlinks(filepath: str) -> dict:
    """Extract GitHub and LinkedIn URLs from PDF hyperlink annotations.

    Many resumes embed URLs as clickable hyperlinks rather than visible text.
    pdfminer can read PDF annotations to find these embedded URIs.
    """
    result = {"github": None, "linkedin": None}
    try:
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfparser import PDFParser
        from pdfminer.pdfdocument import PDFDocument

        with open(filepath, "rb") as f:
            parser = PDFParser(f)
            doc = PDFDocument(parser)
            for page in PDFPage.create_pages(doc):
                if page.annots:
                    annots = page.annots
                    if hasattr(annots, 'resolve'):
                        annots = annots.resolve()
                    if not isinstance(annots, list):
                        continue
                    for annot_ref in annots:
                        try:
                            annot = annot_ref.resolve() if hasattr(annot_ref, 'resolve') else annot_ref
                            if not isinstance(annot, dict):
                                continue
                            uri_obj = annot.get("A", {})
                            if hasattr(uri_obj, 'resolve'):
                                uri_obj = uri_obj.resolve()
                            uri = uri_obj.get("URI") if isinstance(uri_obj, dict) else None
                            if uri:
                                if isinstance(uri, bytes):
                                    uri = uri.decode("utf-8", errors="ignore")
                                uri_lower = uri.lower()
                                if "github.com" in uri_lower and not result["github"]:
                                    # Skip org/repo URLs — only keep profile URLs
                                    parts = uri.rstrip("/").split("/")
                                    if len(parts) <= 4:  # https://github.com/username
                                        result["github"] = uri
                                elif "linkedin.com" in uri_lower and not result["linkedin"]:
                                    result["linkedin"] = uri
                        except Exception:
                            continue
    except Exception as e:
        print(f"[PARSE] Hyperlink extraction warning: {e}")
    return result


async def _parse_and_store(filename: str, task_id: str) -> str:
    """Background task to parse resume and store in candidates collection. Returns the resolved candidate ID."""
    candidate_id = task_id
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
        
        # Validate URLs — parser sometimes extracts display text (e.g. "GitHub") not actual URLs
        github_valid = github_url and "github.com" in github_url.lower()
        linkedin_valid = linkedin_url and "linkedin.com" in linkedin_url.lower()
        
        # Fallback: extract URLs from PDF hyperlinks if not found or invalid
        if (not github_valid or not linkedin_valid) and filepath.lower().endswith(".pdf"):
            hyperlinks = await asyncio.to_thread(extract_pdf_hyperlinks, filepath)
            if not github_valid and hyperlinks.get("github"):
                github_url = hyperlinks["github"]
                personal_info["github"] = github_url
                parsed["personal_info"] = personal_info
                print(f"[PARSE] Found GitHub URL from PDF hyperlink: {github_url}")
            elif not github_valid and github_url:
                # Parser returned display text like "GitHub" — clear it
                print(f"[PARSE] Clearing invalid github value: '{github_url}' (not a URL)")
                github_url = None
                personal_info["github"] = None
            if not linkedin_valid and hyperlinks.get("linkedin"):
                linkedin_url = hyperlinks["linkedin"]
                personal_info["linkedin"] = linkedin_url
                parsed["personal_info"] = personal_info
                print(f"[PARSE] Found LinkedIn URL from PDF hyperlink: {linkedin_url}")
            elif not linkedin_valid and linkedin_url:
                print(f"[PARSE] Clearing invalid linkedin value: '{linkedin_url}' (not a URL)")
                linkedin_url = None
                personal_info["linkedin"] = None
        
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
        
        # TASK 1: DEDUPLICATION CHECK
        full_name = personal_info.get("full_name")
        phone_number = personal_info.get("phone_number")
        
        if full_name and phone_number:
            existing_candidate = await db.candidates.find_one({
                "parsed.personal_info.full_name": full_name,
                "parsed.personal_info.phone_number": phone_number
            })
            if existing_candidate:
                print(f"Candidate match found! Reusing candidate_id: {existing_candidate['candidate_id']}")
                real_candidate_id = existing_candidate["candidate_id"]
                
                # Update task with resolved candidate ID so other operations can track it
                await db.tasks.update_one(
                    {"task_id": task_id},
                    {"$set": {"status": "parsed", "parsed_at": datetime.utcnow(), "resolved_candidate_id": real_candidate_id}}
                )
                
                # Optionally update the existing candidate doc with the new parsed resume (fresh snapshot)
                await db.candidates.update_one(
                    {"candidate_id": real_candidate_id},
                    {"$set": {
                        "filename": filename,
                        "uploaded_at": datetime.utcnow(),
                        "parsed": parsed,
                        "github_username": extract_github_username(github_url),
                        "linkedin_url": extract_linkedin_url(linkedin_url),
                        "education": education,
                        "experience_companies": experience_companies,
                        "universities": parsed.get("university") or [],
                        "companies": parsed.get("company") or [],
                        "skills_embedding": skills_embedding
                    }}
                )
                return real_candidate_id
        
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
            {"task_id": task_id},
            {"$set": {"status": "parsed", "parsed_at": datetime.utcnow(), "resolved_candidate_id": candidate_id}}
        )
        return candidate_id
        
    except Exception as e:
        print(f"[PARSE] ❌ FAILED for {task_id}: {e}")
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": str(e)}}
        )


async def _run_unified_verification(candidate_id: str, job_id: str, task_id: str = None):
    """Background task to run unified verification after parsing"""
    if not task_id:
        task_id = candidate_id

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
            {"task_id": task_id},
            {"$set": {"status": "verifying", "verification_started_at": datetime.utcnow()}}
        )
        
        # Run verification
        if github_username or linkedin_url or profile_data:
            use_agent = os.environ.get("USE_AGENT_SYSTEM", "false").lower() == "true"
            dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
            
            result = None
            agent_result = None
            verification_dict = None

            if use_agent:
                from app.agent.core.agent_loop import run as run_agent_loop
                
                if dual_run:
                    # Shadow Mode: Run both concurrently
                    print(f"Shadow Mode active: Running V2 + Agentic Loop for {candidate_id}")
                    legacy_task = unified_verification_service.run_unified_verification(
                        candidate_id=candidate_id,
                        github_username=github_username,
                        linkedin_url=linkedin_url,
                        profile_data=profile_data,
                        parsed_resume=parsed,
                    )
                    agent_task = run_agent_loop(candidate_id, job_id)
                    
                    gather_result = await asyncio.gather(legacy_task, agent_task, return_exceptions=True)
                    result = gather_result[0]
                    agent_result = gather_result[1]
                    
                    if isinstance(result, Exception):
                        raise result
                    if isinstance(agent_result, Exception):
                        print(f"Agent Loop Failed: {agent_result}")
                else:
                    # Agent ONLY Mode — agent is already awaited, so scoring data is in DB by the time we continue
                    print(f"Agentic Mode active: Running only Agent Loop for {candidate_id}")
                    agent_result = await run_agent_loop(candidate_id, job_id)
                    # Agent writes to verification_data (or verification_data_agent if dual_run).
                    # Read it back so _create_application gets real scores.
                    agent_verif_col = "verification_data_agent" if dual_run else "verification_data"
                    agent_verif_doc = await db[agent_verif_col].find_one(
                        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
                    )
                    if agent_verif_doc:
                        verification_dict = dict(agent_verif_doc)
                        print(f"[AGENT] Read back verification_data for {candidate_id}: overallCredibility={verification_dict.get('matchScore', {}).get('overallCredibility', 0)}")
                        # Update candidate status from agent scores
                        agent_match = verification_dict.get("matchScore", {})
                        if agent_match.get("overallCredibility", 0) > 0:
                            await db.candidates.update_one(
                                {"candidate_id": candidate_id},
                                {"$set": {
                                    "verification_score": agent_match["overallCredibility"],
                                    "status": "verified"
                                }}
                            )
                    else:
                        print(f"[AGENT] No verification_data found after agent run for {candidate_id}")
                    result = None  # skip legacy Pydantic conversion below
            else:
                # Normal Mode
                print(f"[VERIFY] Legacy mode: running verification for {candidate_id}")
                result = await unified_verification_service.run_unified_verification(
                    candidate_id=candidate_id,
                    github_username=github_username,
                    linkedin_url=linkedin_url,
                    profile_data=profile_data,
                    parsed_resume=parsed,
                )
                print(f"[VERIFY] Legacy verification complete for {candidate_id}")
            
            # Convert result to dict for passing to _create_application
            # (only if agent path didn't already set verification_dict above)
            if result is not None:
                match_score = getattr(result, "matchScore", None)
                if match_score:
                    await db.candidates.update_one(
                        {"candidate_id": candidate_id},
                        {"$set": {
                            "verification_score": match_score.overallCredibility,
                            "status": "verified"
                        }}
                    )
                    print(f"[VERIFY] Candidate {candidate_id} updated: overallCredibility={match_score.overallCredibility}")
                # Convert Pydantic model to dict for _create_application
                try:
                    verification_dict = result.to_mongo_dict()
                except Exception:
                    verification_dict = result.model_dump() if hasattr(result, 'model_dump') else None
            
            # Update task as done
            await db.tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"verified": True}}}
            )
        else:
            verification_dict = None
            # No verification sources available
            print(f"[VERIFY] No verification sources for {candidate_id} (no github/linkedin/profile)")
            await db.tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"verified": False, "reason": "No verification sources"}}}
            )
        
        # Create application record AFTER verification/agent has fully resolved
        # Pass verification_dict directly so _create_application doesn't re-query DB
        await _create_application(candidate_id, job_id, verification_data=verification_dict)
            
    except Exception as e:
        print(f"[VERIFY] Verification failed for {candidate_id}: {e}")
        import traceback
        traceback.print_exc()
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "verification_failed", "error": str(e)}}
        )
        # Still create application even if verification failed (will query DB as fallback)
        await _create_application(candidate_id, job_id, verification_data=None)


async def _create_application(candidate_id: str, job_id: str, verification_data: dict = None):
    """Create application record linking candidate to job with scores.
    
    Args:
        candidate_id: The candidate's unique ID
        job_id: The job's ObjectId string
        verification_data: Pre-computed verification dict (from VerificationDataModel.to_mongo_dict()).
                          If provided, used directly instead of re-querying MongoDB.
                          If None, falls back to querying the verification_data collection.
    """
    try:
        # ── Step 1: Get verification data ──────────────────────────────────
        verification = verification_data  # Use passed-in data if available
        
        if verification is None:
            # Fallback: query MongoDB (used when called from exception handler)
            import os
            dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
            query = {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
            
            if dual_run:
                v_legacy = await db.verification_data.find_one(query)
                v_agent  = await db.verification_data_agent.find_one(query)
                if v_legacy and v_legacy.get("matchScore"):
                    verification = v_legacy
                elif v_agent and v_agent.get("matchScore"):
                    verification = v_agent
                else:
                    verification = v_legacy or v_agent
            else:
                verification = await db.verification_data.find_one(query)
            
            print(f"[APP] DB fallback query for {candidate_id}: found={'yes' if verification else 'NO'}")
        else:
            print(f"[APP] Using pre-computed verification data for {candidate_id}")
        
        # ── Step 2: Extract verification scores ───────────────────────────
        verification_bonus = 0
        if verification and verification.get("verificationStatus"):
            status = verification["verificationStatus"]
            if status.get("github") == "verified":
                verification_bonus += 5
            if status.get("linkedin") == "verified":
                verification_bonus += 5
            if status.get("webCheck") == "verified":
                verification_bonus += 5
        
        github_verification_score = 0
        github_v2_data: Dict[str, Any] = {}
        if verification and verification.get("githubData"):
            github_data = verification["githubData"]
            github_verification_score = github_data.get("score", 0) or github_data.get("score100", 0)
            github_v2_data = github_data.get("github_v2_data") or {}

        match_score = verification.get("matchScore", {}) if verification else {}
        overall_credibility = match_score.get("overallCredibility", 0)
        
        print(
            f"[APP] Scores for {candidate_id}: "
            f"overallCredibility={overall_credibility}, "
            f"github={github_verification_score}, "
            f"bonus={verification_bonus}, "
            f"source={'verified' if match_score else 'unverified'}"
        )

        # ── Step 3: Load candidate resume + job requirements ──────────────
        candidate_doc = await db.candidates.find_one({"candidate_id": candidate_id})
        parsed_resume = candidate_doc.get("parsed", {}) if candidate_doc else {}
        job_doc = await db.jobs.find_one({"_id": ObjectId(job_id)})
        required_skills = job_doc.get("required_skills", []) if job_doc else []
        preferred_skills = job_doc.get("preferred_skills", []) if job_doc else []

        # ── Step 4: Unified skill evidence scoring ────────────────────────
        scoring_result = await run_unified_skill_scoring(
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            parsed=parsed_resume,
            github_v2_data=github_v2_data,
        )
        skill_scores = scoring_result["skill_scores"]
        jd_match_score = scoring_result["jd_match_score"]

        # FALLBACK: If embedding pipeline returned 0, use fuzzy keyword matcher
        all_skills = required_skills + preferred_skills
        if jd_match_score == 0.0 and len(all_skills) > 0:
            fallback_results = compute_skill_matches(all_skills, parsed_resume)
            skill_scores = fallback_results
            jd_match_score = round(sum(s["score"] for s in fallback_results) / len(all_skills), 2) if fallback_results else 0.0

        # ── Step 5: Build application document ────────────────────────────
        application_doc = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "application_date": datetime.utcnow(),
            "status": "Under Review",
            "score_details": {
                "overall_score": overall_credibility,
                "skills_match_score": github_verification_score,
                "experience_match_score": match_score.get("experienceMatch", 0),
                "verification_bonus": verification_bonus,
                "score_source": "verified" if match_score else "unverified",
                "jd_match_score": jd_match_score,
                "skill_matches": skill_scores,
            },
            "recruiter_notes": ""
        }

        # ── Step 6: Upsert application ────────────────────────────────────
        existing_app = await db.applications.find_one({"candidate_id": candidate_id, "job_id": job_id})
        if existing_app:
            await db.applications.update_one(
                {"candidate_id": candidate_id, "job_id": job_id},
                {"$set": {
                    "score_details": application_doc["score_details"],
                    "updated_at": datetime.utcnow(),
                }}
            )
            print(
                f"[APP] UPDATED application {candidate_id} → job {job_id} "
                f"| overall={overall_credibility} | github={github_verification_score}% "
                f"| bonus={verification_bonus} | jd_match={jd_match_score:.2f}/10 | source={'verified' if match_score else 'unverified'}"
            )
        else:
            await db.applications.insert_one(application_doc)
            print(
                f"[APP] CREATED application {candidate_id} → job {job_id} "
                f"| overall={overall_credibility} | github={github_verification_score}% "
                f"| bonus={verification_bonus} | jd_match={jd_match_score:.2f}/10 | source={'verified' if match_score else 'unverified'}"
            )

        try:
            from app.services.metrics_service import upsert_metrics_for_application

            await upsert_metrics_for_application(
                candidate_id=candidate_id,
                job_id=job_id,
                candidate_doc=candidate_doc,
                application_doc=application_doc,
                job_doc=job_doc,
                verification_doc=verification,
                db_client=db,
            )
        except Exception as metrics_exc:
            print(f"[APP] Metrics upsert failed for {candidate_id}: {metrics_exc}")
    except Exception as e:
        print(f"[APP] FAILED to create application for {candidate_id}: {e}")
        import traceback
        traceback.print_exc()


async def _parse_and_verify(filename: str, task_id: str, job_id: str):
    """Combined background task: parse resume, then run verification"""
    real_candidate_id = await _parse_and_store(filename, task_id)
    
    # Check if parsing succeeded before verification
    task = await db.tasks.find_one({"task_id": task_id})
    if task and task.get("status") != "failed":
        await _run_unified_verification(real_candidate_id, job_id, task_id)


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
        import os
        dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
        vquery = {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
        verification = None
        if dual_run:
            v_legacy = await db.verification_data.find_one(vquery)
            v_agent  = await db.verification_data_agent.find_one(vquery)
            if v_legacy and v_legacy.get("matchScore"):
                verification = v_legacy
            elif v_agent and v_agent.get("matchScore"):
                verification = v_agent
            else:
                verification = v_legacy or v_agent
        else:
            verification = await db.verification_data.find_one(vquery)
        
        # Read stored skill_matches from application document (computed at upload time)
        skill_matches = app.get("score_details", {}).get("skill_matches", [])

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
