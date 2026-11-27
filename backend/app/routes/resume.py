import os
import re
import traceback
import asyncio
import uuid
from bson import ObjectId
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from app.auth import AuthUser, get_current_user, require_job_action, require_job_owner
from app.database import db
from app.services.parser import parse_resume
from app.services.unified_verification import unified_verification_service
from app.services.coding_profiles import detect_claims, extract_coding_profiles, profile_url
from app.services import portfolios as portfolio_checks
from app.services.project_reviews import from_resume as project_links_from_resume
from app.utils.file_utils import read_file, content_matches_type
from app.services.quota import rate_limit, use_quota
from app.org import ensure_org
from app.services.skill_matching.pipeline import run_unified_skill_scoring
from app.services.task_queue import task_queue, TERMINAL_STATUSES
from app.services import cover_letter_service
from app.services import provider_keys

# Gemini concurrency, retries and rate-limit backoff are handled in
# app.services.parser; the number of resumes processed at once is set by
# RESUME_WORKERS in app.services.task_queue.

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_FILES_PER_UPLOAD = int(os.getenv("MAX_FILES_PER_UPLOAD", "50"))
TEXT_EXTRACT_TIMEOUT_SECONDS = int(os.getenv("TEXT_EXTRACT_TIMEOUT_SECONDS", "60"))

# The one list of application statuses shared with the frontend
CANDIDATE_STATUSES = ["Under Review", "Shortlisted", "Interview", "Offer", "Hired", "Rejected"]
_STATUS_LOOKUP = {s.lower(): s for s in CANDIDATE_STATUSES}
# Values written by older UI versions
_STATUS_LOOKUP.update({"new": "Under Review", "reviewing": "Under Review", "pending review": "Under Review"})


def normalize_status(status) -> str | None:
    """Canonical status for any accepted spelling, or None if unknown."""
    if not isinstance(status, str):
        return None
    return _STATUS_LOOKUP.get(status.strip().lower())


def _split_skills(skills) -> List[str]:
    if isinstance(skills, list):
        items = skills
    elif isinstance(skills, str):
        items = skills.split(",")
    else:
        return []
    return list(dict.fromkeys(s.strip() for s in items if isinstance(s, str) and s.strip()))


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


from urllib.parse import urlparse

_GITHUB_USER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_LINKEDIN_SLUG = re.compile(r"[A-Za-z0-9_-]{1,100}")


def extract_github_username(github_url: str) -> str | None:
    """GitHub username from a github.com URL or a bare username; None if it isn't valid.

    The username ends up in GitHub API paths, so only GitHub's own username
    characters are accepted.
    """
    if not github_url:
        return None
    github_url = github_url.strip()
    if "github.com" in github_url.lower():
        if "://" not in github_url:
            github_url = "https://" + github_url
        parsed = urlparse(github_url)
        if (parsed.hostname or "") not in ("github.com", "www.github.com"):
            return None
        github_url = parsed.path.strip("/").split("/")[0]
    return github_url if _GITHUB_USER.fullmatch(github_url) else None


def extract_linkedin_url(linkedin: str) -> str | None:
    """https URL on linkedin.com (or a subdomain), else None.

    The dossier links to it, so it must not point anywhere else.
    """
    if not linkedin:
        return None
    linkedin = linkedin.strip()
    if "://" not in linkedin:
        if "linkedin.com" in linkedin.lower():
            linkedin = "https://" + linkedin
        elif _LINKEDIN_SLUG.fullmatch(linkedin):
            return f"https://linkedin.com/in/{linkedin}"
        else:
            return None
    parsed = urlparse(linkedin)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() not in ("http", "https") or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return None
    # Plain http links are upgraded so the dossier only ever links over https
    return parsed._replace(scheme="https").geturl()


def extract_pdf_hyperlinks(filepath: str) -> dict:
    """Extract GitHub and LinkedIn URLs from PDF hyperlink annotations.

    Many resumes embed URLs as clickable hyperlinks rather than visible text.
    pdfminer can read PDF annotations to find these embedded URIs.
    "uris" holds every link target (used to find coding-profile handles).
    """
    result = {"github": None, "linkedin": None, "uris": []}
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
                                if len(result["uris"]) < 200:
                                    result["uris"].append(uri)
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


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


async def _parse_and_store(filename: str, task_id: str, owner_uid: str | None = None, org_id: str | None = None,
                           text: str | None = None) -> str:
    """Background task to parse resume and store in candidates collection. Returns the resolved candidate ID.

    org_id is the workspace of the job the resume was uploaded to; duplicates are matched within it.
    text, when given, is the resume part of a combined cover letter + resume PDF.
    """
    candidate_id = task_id
    try:
        filepath = os.path.join(RESUMES_DIR, filename)
        
        # Open and read in a thread to avoid blocking the event loop
        content = await asyncio.to_thread(_read_bytes, filepath)
        
        if text is None:
            # ponytail: on timeout the extraction thread can't be killed and runs on
            # in the background; move parsing to a subprocess if that ever bites.
            text = await asyncio.wait_for(asyncio.to_thread(read_file, filename, content), TEXT_EXTRACT_TIMEOUT_SECONDS)
        if not text:
            raise ValueError("Empty file")
        
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
        
        is_pdf = filepath.lower().endswith(".pdf")
        hyperlinks = await asyncio.to_thread(extract_pdf_hyperlinks, filepath) if is_pdf else {}
        # Competitive-programming handles and claims, from the text and link targets
        coding_profiles = extract_coding_profiles([text, *hyperlinks.get("uris", [])])
        coding_claims = detect_claims(text) if coding_profiles else []
        # Behance, Dribbble, Kaggle, Stack Overflow and one personal website
        portfolios = portfolio_checks.extract_portfolios(
            [text, *hyperlinks.get("uris", [])], name=personal_info.get("full_name"))
        portfolio_claims = portfolio_checks.detect_claims(text) if portfolios else []
        # Deployed project links and the resume line that mentions them (reviewed on demand)
        project_links = project_links_from_resume(text, hyperlinks.get("uris", []), parsed, portfolios.get("website"))

        # Fallback: extract URLs from PDF hyperlinks if not found or invalid
        if (not github_valid or not linkedin_valid) and is_pdf:
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
        # CPU-bound — keep it off the event loop so other workers keep running
        skills_embedding = await asyncio.to_thread(generate_embedding, skills_text)
        
        # TASK 1: DEDUPLICATION CHECK
        full_name = personal_info.get("full_name")
        phone_number = personal_info.get("phone_number")
        
        if full_name and phone_number and org_id:
            # Dedupe within the workspace, so teammates share one candidate record
            # and another workspace's candidate is never reused. Candidates saved
            # before org_id was stored only match their own uploader's.
            existing_candidate = await db.candidates.find_one({
                "parsed.personal_info.full_name": full_name,
                "parsed.personal_info.phone_number": phone_number,
                "candidate_id": {"$ne": candidate_id},
                "$or": [
                    {"org_id": org_id},
                    {"org_id": {"$exists": False}, "owner_uid": owner_uid},
                ],
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
                        "org_id": org_id,
                        "filename": filename,
                        "uploaded_at": datetime.utcnow(),
                        "parsed": parsed,
                        "github_username": extract_github_username(github_url),
                        "linkedin_url": extract_linkedin_url(linkedin_url),
                        "coding_profiles": coding_profiles,
                        "coding_claims": coding_claims,
                        "portfolios": portfolios,
                        "portfolio_claims": portfolio_claims,
                        "project_links": project_links,
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
            "owner_uid": owner_uid,
            "org_id": org_id,
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
            # {platform: handle} for LeetCode, Codeforces, etc., and the resume's claims about them
            "coding_profiles": coding_profiles,
            "coding_claims": coding_claims,
            # {platform: handle} for Behance, Dribbble, Kaggle, Stack Overflow, plus "website": url
            "portfolios": portfolios,
            "portfolio_claims": portfolio_claims,
            "project_links": project_links,
            # Store education and experience for verification
            "education": education,
            "experience_companies": experience_companies,
            # NEW: Extracted entity names for verification
            "universities": parsed.get("university") or [],
            "companies": parsed.get("company") or [],
            # NEW: Skills embedding for JD matching
            "skills_embedding": skills_embedding
        }
        # Upsert so a task re-run after a worker crash doesn't create a duplicate
        await db.candidates.update_one(
            {"candidate_id": candidate_id}, {"$set": candidate_doc}, upsert=True
        )
        
        # Update task status
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "parsed", "parsed_at": datetime.utcnow(), "resolved_candidate_id": candidate_id}}
        )
        return candidate_id
        
    except Exception as e:
        print(f"[PARSE] ❌ FAILED for {task_id}: {e!r}")
        traceback.print_exc()
        # The tasks API returns this, so no raw exception text (it can hold provider URLs and request details)
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": _parse_error_message(e)}}
        )


def _parse_error_message(e: Exception) -> str:
    if isinstance(e, asyncio.TimeoutError):
        hint = "Reading the file took too long; it may be damaged or very large"
    elif str(e) == "Empty file":
        hint = "No text could be read from the file; scanned images aren't supported"
    else:
        hint = "Check the file opens normally"
    return f"Could not parse this resume ({type(e).__name__}). {hint}, then re-upload it."


def _remove_stored_file(filename: str | None):
    """Delete an uploaded resume from RESUMES_DIR; a missing file is fine."""
    if not filename:
        return
    try:
        os.remove(os.path.join(RESUMES_DIR, os.path.basename(filename)))
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[PARSE] Could not delete {filename}: {e!r}")


async def delete_task_files(query: dict):
    """Delete the stored resume files of the tasks matching ``query``."""
    async for task in db.tasks.find(query, {"filename": 1}):
        await asyncio.to_thread(_remove_stored_file, task.get("filename"))


_INSTITUTION_WORDS = ("university", "institute", "college", "school", "academy", "polytechnic")
_INSTITUTION_ACRONYMS = {"iit", "nit", "iiit", "bits", "mit"}


def _institution_from_education(line: str) -> str | None:
    """Pick the institution out of a free-text education line."""
    for part in line.replace("|", ",").split(","):
        part = re.sub(r"\s*\(.*?\)", "", part).strip()
        lower = part.lower()
        if any(w in lower for w in _INSTITUTION_WORDS) or _INSTITUTION_ACRONYMS & set(re.findall(r"[a-z]+", lower)):
            # Drop a leading "B.Tech in CS from ..." style prefix
            return part.split(" from ")[-1].split(" at ")[-1].strip()
    return None


def _verification_entities(parsed: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """Universities and companies to verify, preferring the parser's clean lists."""
    universities = [u.strip() for u in parsed.get("university") or [] if isinstance(u, str) and u.strip()]
    if not universities:
        universities = [i for i in (_institution_from_education(e) for e in parsed.get("education") or []
                                    if isinstance(e, str)) if i]

    companies = [c.strip() for c in parsed.get("company") or [] if isinstance(c, str) and c.strip()]
    if not companies:
        for exp in parsed.get("experience") or []:
            if isinstance(exp, str) and " at " in exp:
                company = exp.split(" at ", 1)[1].split("(")[0].split("|")[0].split(" - ")[0].strip()
                if company:
                    companies.append(company)

    # Keep order, drop duplicates
    return list(dict.fromkeys(universities)), list(dict.fromkeys(companies))


async def _run_unified_verification(candidate_id: str, job_id: str, task_id: str = None):
    """Background task to run unified verification after parsing"""
    if not task_id:
        task_id = candidate_id

    verification_dict = None
    verification_error = None
    task_result = {"verified": False, "reason": "No verification sources"}

    try:
        # Get candidate data
        candidate = await db.candidates.find_one({"candidate_id": candidate_id})
        if not candidate:
            print(f"Candidate {candidate_id} not found for verification")
            await db.tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "failed", "completed_at": datetime.utcnow(),
                          "error": "The parsed candidate could not be found. Re-upload the resume to retry."}}
            )
            return
        
        github_username = candidate.get("github_username")
        linkedin_url = candidate.get("linkedin_url")
        coding_profiles = candidate.get("coding_profiles") or {}
        portfolios = candidate.get("portfolios") or {}
        parsed = candidate.get("parsed", {})
        
        # Build profile data for web search verification
        # Use LinkedIn-like structure for compatibility with verifier.
        # Search the institution/company names, not whole resume lines
        # ("B.Tech in CS, IIT Delhi, 2021" used to be searched as "B.Tech in CS").
        profile_data = None
        if parsed:
            universities, companies = _verification_entities(parsed)
            if universities or companies:
                profile_data = {
                    "publicIdentifier": candidate_id,
                    "educations": [{"schoolName": u} for u in universities],
                    "experiences": [{"companyName": c} for c in companies],
                }
        
        # Update task status
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "verifying", "verification_started_at": datetime.utcnow()}}
        )
        
        # Run verification
        if github_username or linkedin_url or profile_data or coding_profiles or portfolios:
            print(f"[VERIFY] Running verification for {candidate_id}")
            result = await unified_verification_service.run_unified_verification(
                candidate_id=candidate_id,
                github_username=github_username,
                linkedin_url=linkedin_url,
                profile_data=profile_data,
                parsed_resume=parsed,
                coding_profiles=coding_profiles,
                coding_claims=candidate.get("coding_claims") or [],
                portfolios=portfolios,
                portfolio_claims=candidate.get("portfolio_claims") or [],
            )
            print(f"[VERIFY] Verification complete for {candidate_id}")

            # Convert result to dict for passing to _create_application
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
            
            task_result = {"verified": True}
        else:
            # No verification sources available
            print(f"[VERIFY] No verification sources for {candidate_id} (no github/linkedin/profile)")

    except Exception as e:
        print(f"[VERIFY] Verification failed for {candidate_id}: {e}")
        traceback.print_exc()
        # str(e) is empty for exceptions like TimeoutError()
        verification_error = str(e) or type(e).__name__
        # The application is still created, with scores re-read from the DB
        verification_dict = None

    # Create application record AFTER verification has fully resolved.
    # The task only reports success once the candidate is saved to the job's pipeline.
    try:
        await _create_application(candidate_id, job_id, verification_data=verification_dict)
    except JobDeleted:
        # The job was deleted while this resume was screened (its tasks went with it)
        print(f"[APP] Job {job_id} was deleted; {candidate_id} not added to it")
        return
    except Exception as e:
        print(f"[APP] FAILED to save application for {candidate_id}: {e}")
        traceback.print_exc()
        # Exception type only: the task's error is returned by the API, and driver
        # messages can contain database hosts
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "failed", "completed_at": datetime.utcnow(),
                      "error": f"Could not save this candidate to the job ({type(e).__name__}). Re-upload the resume to retry."}}
        )
        return

    if verification_error is not None:
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "verification_failed", "completed_at": datetime.utcnow(), "error": verification_error}}
        )
    else:
        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": task_result}}
        )


class JobDeleted(Exception):
    """The job was deleted while its resume was being screened."""


async def _create_application(candidate_id: str, job_id: str, verification_data: dict = None):
    """Create application record linking candidate to job with scores.

    Raises JobDeleted, and leaves no application behind, when the job no longer exists.

    Args:
        candidate_id: The candidate's unique ID
        job_id: The job's ObjectId string
        verification_data: Pre-computed verification dict (from VerificationDataModel.to_mongo_dict()).
                          If provided, used directly instead of re-querying MongoDB.
                          If None, falls back to querying the verification_data collection.

    Raises on any scoring or database failure: the caller decides how the task ends,
    so a candidate is never reported as processed without being saved to the job.
    """
    # ── Step 1: Get verification data ──────────────────────────────────
    verification = verification_data  # Use passed-in data if available
    
    if verification is None:
        # Fallback: query MongoDB (used when called from exception handler)
        query = {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
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
    if not job_doc:
        raise JobDeleted(job_id)
    required_skills = job_doc.get("required_skills", [])
    preferred_skills = job_doc.get("preferred_skills", [])

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

    # ── Step 5: Save the application ──────────────────────────────────
    score_details = {
        "overall_score": overall_credibility,
        "skills_match_score": github_verification_score,
        "experience_match_score": match_score.get("experienceMatch", 0),
        "verification_bonus": verification_bonus,
        "score_source": "verified" if match_score else "unverified",
        "jd_match_score": jd_match_score,
        "skill_matches": skill_scores,
    }
    now = datetime.utcnow()
    # One atomic upsert, safe to retry: scores refresh, but the recruiter's
    # status and notes on an existing application are left alone
    result = await db.applications.update_one(
        {"candidate_id": candidate_id, "job_id": job_id},
        {
            "$set": {"score_details": score_details, "updated_at": now},
            "$setOnInsert": {"application_date": now, "status": "Under Review", "recruiter_notes": ""},
        },
        upsert=True,
    )
    # The job may have been deleted while scoring ran, after its applications were
    # cleared: don't leave one pointing at it (it would 404 for good)
    if not await db.jobs.find_one({"_id": ObjectId(job_id)}, {"_id": 1}):
        await db.applications.delete_one({"candidate_id": candidate_id, "job_id": job_id})
        raise JobDeleted(job_id)
    print(
        f"[APP] {'CREATED' if result.upserted_id else 'UPDATED'} application {candidate_id} → job {job_id} "
        f"| overall={overall_credibility} | github={github_verification_score}% "
        f"| bonus={verification_bonus} | jd_match={jd_match_score:.2f}/10 | source={'verified' if match_score else 'unverified'}"
    )


async def _parse_and_verify(filename: str, task_id: str, job_id: str, owner_uid: str | None = None,
                            resolved_candidate_id: str | None = None, text: str | None = None):
    """Combined background task: parse resume, then run verification"""
    # A task re-queued after a crash during verification was already parsed and its file deleted
    if resolved_candidate_id:
        real_candidate_id = resolved_candidate_id
    else:
        try:
            job = await db.jobs.find_one({"_id": ObjectId(job_id)}, {"org_id": 1})
        except Exception:
            job = None
        real_candidate_id = await _parse_and_store(filename, task_id, owner_uid, (job or {}).get("org_id"),
                                                   **({"text": text} if text is not None else {}))
    # The candidate is stored (or the parse failed for good): the file isn't needed any more.
    # Not in a finally, so a cancelled task keeps its file for the retry.
    await asyncio.to_thread(_remove_stored_file, filename)
    
    # Check if parsing succeeded before verification
    task = await db.tasks.find_one({"task_id": task_id})
    if task and task.get("status") != "failed":
        await _run_unified_verification(real_candidate_id, job_id, task_id)


async def process_resume_task(task: dict):
    """Queue handler (see app.services.task_queue): runs one uploaded resume end to end.

    Cover letters in the upload are recognised first: they never become candidates,
    and are paired with a resume of the same job instead.
    """
    # AI and verification calls for this task use its workspace's provider keys
    if provider_keys.enabled():
        try:
            job = await db.jobs.find_one({"_id": ObjectId(task["job_id"])}, {"org_id": 1})
        except Exception:
            job = None
        await provider_keys.use_org((job or {}).get("org_id"))
    resolved = task.get("resolved_candidate_id")
    if resolved:
        # A retried task was already classified and parsed, and its file is gone.
        # ponytail: a letter split from a combined PDF is lost on that rare retry;
        # store letter_text on the task if it ever matters.
        doc = {"kind": "resume", "resume_text": None, "letter_text": None}
    else:
        doc = await cover_letter_service.prepare_upload(task, os.path.join(RESUMES_DIR, task["filename"]))
    if doc["kind"] == "cover_letter":
        await cover_letter_service.after_resume(task, None)
        return
    split = {"text": doc["resume_text"]} if doc["resume_text"] else {}
    await _parse_and_verify(task["filename"], task["task_id"], task["job_id"], task.get("owner_uid"),
                            resolved, **split)
    await cover_letter_service.after_resume(task, doc["letter_text"])


def _write_file(path: str, content: bytes):
    with open(path, "wb") as f:
        f.write(content)


@router.post("/{job_id}/upload", dependencies=[Depends(require_job_action("candidate.upload"))])
async def upload_resumes(
    job_id: str,
    files: List[UploadFile] = File(...),
    user: AuthUser = Depends(get_current_user),
):
    """Upload resumes; each one is queued and processed by the task workers."""
    rate_limit(user.uid, "upload")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(400, f"Too many files: upload at most {MAX_FILES_PER_UPLOAD} per request")
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    # Validate the whole batch first so a bad file doesn't leave half a batch queued
    for file in files:
        if not file.filename:
            raise HTTPException(400, "Every file needs a filename")
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("pdf", "docx", "doc", "txt"):
            raise HTTPException(400, f"Unsupported file type: {ext}")
        if file.size is not None and file.size > max_bytes:
            raise HTTPException(413, f"{file.filename} is larger than {MAX_UPLOAD_MB} MB")
        # One file in memory at a time; file.size can be None, so never read past the limit
        content = await file.read(max_bytes + 1)
        await file.seek(0)
        if len(content) > max_bytes:
            raise HTTPException(413, f"{file.filename} is larger than {MAX_UPLOAD_MB} MB")
        if not content_matches_type(ext, content):
            raise HTTPException(400, f"{file.filename} is not a valid .{ext} file")

    await use_quota(await ensure_org(user), "resume_upload", len(files), feature="resume_parsing")

    saved = []
    tasks = []
    for file in files:
        # Generate unique candidate_id using UUID
        candidate_id = str(uuid.uuid4())
        safe_name = os.path.basename(file.filename)
        unique_name = f"{candidate_id}_{safe_name}"
        dest = os.path.join(RESUMES_DIR, unique_name)
        
        # Save file without blocking the event loop
        content = await file.read()
        await asyncio.to_thread(_write_file, dest, content)
        
        tasks.append({
            "task_id": candidate_id,
            "job_id": job_id,
            "owner_uid": user.uid,
            "filename": unique_name,
            "original_filename": safe_name,
            "type": "parse_and_verify",
            "status": "queued",
            "attempts": 0,
            "created_at": datetime.utcnow()
        })
        saved.append({
            "filename": file.filename, 
            "stored_as": unique_name,
            "candidate_id": candidate_id
        })
    
    # Queue parsing + verification; workers pick these up immediately
    if tasks:
        await db.tasks.insert_many(tasks)
        task_queue.notify()
    
    return {"status": "accepted", "saved": saved}


@router.get("/{job_id}/tasks", dependencies=[Depends(require_job_owner)])
async def get_job_tasks(job_id: str, limit: int = 200):
    """Processing progress for uploaded resumes (the frontend polls this)."""
    await cover_letter_service.expire_waiting_letters(job_id)
    counts = {"queued": 0, "processing": 0, "done": 0, "failed": 0}
    unpaired_letters = 0
    async for row in db.tasks.aggregate([
        {"$match": {"job_id": job_id}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        status = row["_id"]
        if status == "queued":
            counts["queued"] += row["n"]
        elif status in ("done", "verification_failed", cover_letter_service.ATTACHED, cover_letter_service.UNPAIRED):
            # verification_failed still creates the candidate (with unverified scores)
            counts["done"] += row["n"]
            if status == cover_letter_service.UNPAIRED:
                unpaired_letters += row["n"]
        elif status in TERMINAL_STATUSES:
            counts["failed"] += row["n"]
        else:  # processing / parsed / verifying
            counts["processing"] += row["n"]

    recent = await db.tasks.find(
        {"job_id": job_id},
        {"_id": 0, "task_id": 1, "original_filename": 1, "filename": 1, "status": 1,
         "error": 1, "created_at": 1, "completed_at": 1},
    ).sort("created_at", -1).to_list(length=min(max(limit, 1), 1000))

    return {
        "job_id": job_id,
        "counts": {**counts, "total": sum(counts.values())},
        # Included in "done"; these letters need attaching by hand
        "unpaired_cover_letters": unpaired_letters,
        "tasks": recent,
    }


@router.put("/{job_id}/candidates/{candidate_id}/status", dependencies=[Depends(require_job_action("candidate.status"))])
async def update_candidate_status(job_id: str, candidate_id: str, status_update: dict):
    """Update candidate application status"""
    new_status = normalize_status(status_update.get("status"))
    if not new_status:
        raise HTTPException(400, f"Status must be one of: {', '.join(CANDIDATE_STATUSES)}")
        
    result = await db.applications.update_one(
        {"job_id": job_id, "candidate_id": candidate_id},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(404, "Application not found")
        
    return {"status": "success", "new_status": new_status}


async def _verification_by_candidate(collection, candidate_ids: List[str]) -> Dict[str, dict]:
    """Fetch verification docs for many candidates in one query (docs use either id field name)."""
    by_id: Dict[str, dict] = {}
    cursor = db[collection].find(
        {"$or": [{"candidateId": {"$in": candidate_ids}}, {"candidate_id": {"$in": candidate_ids}}]},
        {"candidateId": 1, "candidate_id": 1, "verificationStatus": 1, "matchScore": 1, "codingProfilesData": 1,
         "portfoliosData": 1},
    )
    async for doc in cursor:
        cid = doc.get("candidateId") or doc.get("candidate_id")
        by_id.setdefault(cid, doc)
    return by_id


_CODING_FIELDS = ("platform", "handle", "status", "name", "rating", "max_rating", "title", "max_title",
                  "stars", "problems_solved", "contests", "issues", "checked_at")


def _coding_profiles_summary(candidate: dict | None, verification: dict | None) -> List[dict]:
    """Coding profiles for the dossier: checked results, or the listed handles while pending.

    The profile link is rebuilt from the validated handle, never taken from stored data.
    """
    checked = (verification or {}).get("codingProfilesData") or []
    if not checked:
        checked = [{"platform": p, "handle": h, "status": "pending"}
                   for p, h in ((candidate or {}).get("coding_profiles") or {}).items()]
    out = []
    for p in checked:
        try:
            url = profile_url(p.get("platform"), p.get("handle"))
        except (KeyError, ValueError):
            continue
        out.append({**{k: p.get(k) for k in _CODING_FIELDS}, "issues": p.get("issues") or [], "profile_url": url})
    return out


_PORTFOLIO_FIELDS = ("platform", "handle", "status", "name", "headline", "location", "followers", "appreciations",
                     "reputation", "badges", "top_tags", "tiers", "medals", "competitions", "skills", "experience",
                     "education", "note", "checked_at")


def _portfolios_summary(candidate: dict | None, verification: dict | None) -> List[dict]:
    """Portfolio and community profiles for the dossier: checked results, or the listed ones while pending.

    Profile links are rebuilt from the validated handle or URL; project links are kept only if https and public.
    """
    checked = (verification or {}).get("portfoliosData") or []
    if not checked:
        checked = [{"platform": p, "handle": h, "status": "pending"}
                   for p, h in ((candidate or {}).get("portfolios") or {}).items()]
    out = []
    for p in checked:
        try:
            url = portfolio_checks.profile_url(p.get("platform"), p.get("handle"))
        except (KeyError, ValueError):
            continue
        projects = [{**pr, "url": portfolio_checks.public_url(pr.get("url"), https_only=True)}
                    for pr in p.get("projects") or [] if isinstance(pr, dict)]
        out.append({**{k: p.get(k) for k in _PORTFOLIO_FIELDS}, "projects": projects,
                    "issues": p.get("issues") or [], "profile_url": url})
    return out


@router.get("/{job_id}/candidates", dependencies=[Depends(require_job_owner)])
async def get_job_candidates(job_id: str, skip: int = 0, limit: int = 1000):
    """Get all candidates for a job from applications collection"""
    # Previously capped at 100 with 2-3 queries per candidate; now batched
    limit = min(max(limit, 1), 5000)
    applications = await db.applications.find({"job_id": job_id}, {"cover_letter.text": 0}).sort(
        "application_date", -1
    ).skip(max(skip, 0)).to_list(length=limit)
    candidate_ids = [app.get("candidate_id") for app in applications]

    candidates_by_id = {
        c["candidate_id"]: c
        async for c in db.candidates.find(
            {"candidate_id": {"$in": candidate_ids}},
            {"candidate_id": 1, "parsed.personal_info": 1, "parsed.skills": 1, "parsed.education": 1,
             "parsed.experience": 1, "filename": 1, "github_username": 1, "linkedin_url": 1,
             "coding_profiles": 1, "portfolios": 1},
        )
    }
    job_doc = await db.jobs.find_one({"_id": ObjectId(job_id)}, {"required_skills": 1})
    required_skills = (job_doc or {}).get("required_skills") or []

    evaluations_by_id = {
        e["candidate_id"]: e
        async for e in db.evaluations.find(
            {"job_id": job_id, "candidate_id": {"$in": candidate_ids}},
            {"candidate_id": 1, "total_score": 1, "submitted_at": 1},
        )
    }
    verification_by_id = await _verification_by_candidate("verification_data", candidate_ids)
    result = []
    for app in applications:
        candidate_id = app.get("candidate_id")
        
        # Get candidate data
        candidate = candidates_by_id.get(candidate_id)
        parsed = candidate.get("parsed", {}) if candidate else {}
        personal_info = parsed.get("personal_info", {})
        
        verification = verification_by_id.get(candidate_id)

        # Read stored skill_matches from application document (computed at upload time)
        score_details = app.get("score_details") or {}
        skill_matches = score_details.get("skill_matches", [])
        portfolios = _portfolios_summary(candidate, verification)

        result.append({
            "candidate_id": candidate_id,
            "name": personal_info.get("full_name", "Unknown"),
            "email": personal_info.get("email", ""),
            # The parser stores "phone_number"; "phone" kept for older records
            "phone": personal_info.get("phone_number") or personal_info.get("phone", ""),
            "status": normalize_status(app.get("status")) or "Under Review",
            "application_date": app.get("application_date"),
            "score_details": score_details,
            # Real job-description match, 0-100 (scored 0-10 internally). This field
            # used to carry the GitHub score, which the UI showed as "Role Match".
            # None (not 0) while a score is missing, so the UI shows "—" instead of 0%
            "jd_match_score": None if score_details.get("jd_match_score") is None
            else round(float(score_details["jd_match_score"]) * 10, 1),
            # None (not 0) when GitHub wasn't verified, so the UI shows "not analysed"
            "github_score": score_details.get("skills_match_score", 0)
            if ((verification or {}).get("verificationStatus") or {}).get("github") == "verified" else None,
            # None when no source could be checked: "not verified" is not "0% credible"
            "verification_score": None if score_details.get("score_source") == "unverified"
            else score_details.get("overall_score"),
            "interview_score": (evaluations_by_id.get(candidate_id) or {}).get("total_score"),
            "interviewed_at": (evaluations_by_id.get(candidate_id) or {}).get("submitted_at"),
            "skills": _split_skills(parsed.get("skills")),
            "education": [e for e in parsed.get("education") or [] if isinstance(e, str)],
            "experience": [e for e in parsed.get("experience") or [] if isinstance(e, str)],
            "github_url": f"https://github.com/{candidate['github_username']}" if candidate and candidate.get("github_username") else None,
            "linkedin_url": candidate.get("linkedin_url") if candidate else None,
            "filename": candidate.get("filename") if candidate else None,
            "verification_status": verification.get("verificationStatus") if verification else None,
            "coding_profiles": _coding_profiles_summary(candidate, verification),
            "portfolios": portfolios,
            # Job skills shown on portfolios or Stack Overflow tags: evidence only, not scored
            "portfolio_skill_evidence": portfolio_checks.skill_evidence(portfolios, required_skills),
            "skill_matches": skill_matches,  # NEW: Real skill matches
            "has_cover_letter": bool(app.get("cover_letter")),
        })
    
    return {"job_id": job_id, "candidates": result}