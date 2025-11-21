# backend/main.py
import os
import io
import json
import uuid
import glob
import shutil
import logging
import asyncio
import textwrap
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import FastAPI, APIRouter, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# ---------- External libs used by your parser + verification ----------
# langextract (lx) is used in your parser code
import langextract as lx
import pdfplumber
import docx
from apify_client import ApifyClient
from ddgs import DDGS
from rapidfuzz import fuzz

# ---------- Load env ----------
load_dotenv(".env")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "resume_validator")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # used by langextract call
RESUMES_DIR = os.environ.get("RESUMES_DIR", "resumes")
APIFY_ACTOR_ID = os.environ.get("APIFY_ACTOR_ID", "yZnhB5JewWf9xSmoM")  # default you used

# ---------- Basic logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------- Ensure resumes dir ----------
os.makedirs(RESUMES_DIR, exist_ok=True)

# ---------- MongoDB (motor) ----------
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ---------- FastAPI app & router ----------
app = FastAPI(title="ResumeAI - Combined Backend Skeleton")
api_router = APIRouter(prefix="/api/v1")

# CORS - allow origins via env or default to localhost
origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ---------- Pydantic models ----------
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class LinkedInRequest(BaseModel):
    profileUrls: List[str]

class ProfileVerificationRequest(BaseModel):
    # Accept either a dict (single profile) or list of dicts
    data: Union[Dict[str, Any], List[Dict[str, Any]]]

# ---------- Utilities: file reading ----------
def read_pdf_bytes(b: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(b)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        return "\n".join(pages).strip()
    except Exception:
        return ""

def read_docx_bytes(b: bytes) -> str:
    try:
        f = io.BytesIO(b)
        doc = docx.Document(f)
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception:
        return ""

def read_file_bytes(filename: str, content: bytes) -> str:
    ext = filename.lower().split(".")[-1]
    if ext == "pdf":
        return read_pdf_bytes(content)
    elif ext in ("docx", "doc"):
        return read_docx_bytes(content)
    elif ext == "txt":
        return content.decode("utf-8", errors="ignore")
    else:
        # fallback try PDF then text
        t = read_pdf_bytes(content)
        if t:
            return t
        return content.decode("utf-8", errors="ignore")

# ---------- Parser prompt & example setup (kept from your code) ----------
PARSER_PROMPT = textwrap.dedent("""
Extract structured resume information from the entire document.
Extract each field only ONCE from the complete resume.

IMPORTANT FOR PROJECTS EXTRACTION:
- Extract EACH project separately as individual project entries
- For each project, include: project name, technologies used, description, and duration/date if available
- If there are multiple projects, extract each one as a separate projects entry
- Preserve all details for each individual project

Return the following information:
- full_name
- email
- phone_number
- github
- linkedin
- skills
- education
- experience
- projects
- certifications
- achievements
""")

# Example you provided (kept minimal here; can be expanded)
EXAMPLES = [
    lx.data.ExampleData(
        text=textwrap.dedent("""
        John Doe
        Email: john.doe@gmail.com
        Phone: +1 555-123-4567
        GitHub: github.com/johndoe
        LinkedIn: linkedin.com/in/johndoe
        
        SKILLS
        Python, FastAPI, Docker, React
        
        EDUCATION
        B.Tech in Computer Science, MIT, 2020
        
        EXPERIENCE
        Software Engineer at Google (2020–2024)
        - Built scalable microservices
        
        PROJECTS
        E-commerce Platform (Jan 2023 - Mar 2023)
        Python, Flask, React, PostgreSQL
        - Built a full-stack e-commerce application
        """),
        extractions=[
            lx.data.Extraction(extraction_class="full_name", extraction_text="John Doe"),
            lx.data.Extraction(extraction_class="email", extraction_text="john.doe@gmail.com"),
            lx.data.Extraction(extraction_class="phone_number", extraction_text="+1 555-123-4567"),
            lx.data.Extraction(extraction_class="github", extraction_text="github.com/johndoe"),
            lx.data.Extraction(extraction_class="linkedin", extraction_text="linkedin.com/in/johndoe"),
            lx.data.Extraction(extraction_class="skills", extraction_text="Python, FastAPI, Docker, React"),
            lx.data.Extraction(extraction_class="education", extraction_text="B.Tech in Computer Science, MIT, 2020"),
            lx.data.Extraction(extraction_class="experience", extraction_text="Software Engineer at Google (2020–2024) - Built scalable microservices"),
            lx.data.Extraction(extraction_class="projects", extraction_text="E-commerce Platform (Jan 2023 - Mar 2023) - Python, Flask, React, PostgreSQL - Built a full-stack e-commerce application"),
        ]
    )
]

# ---------- Parsing function (runs in thread because langextract is blocking) ----------
def parse_projects_from_extractions(extractions):
    projects = []
    project_extractions = [ext for ext in extractions if ext.extraction_class == "projects"]
    tech_keywords = ["Python", "JavaScript", "React", "Node.js", "Java", "C++", "AWS", "Docker",
                    "MongoDB", "PostgreSQL", "MySQL", "Flask", "Django", "FastAPI", "HTML", "CSS",
                    "TypeScript", "Vue", "Angular", "Express", "Spring", "TensorFlow", "PyTorch"]

    for project_ext in project_extractions:
        project_text = project_ext.extraction_text.strip()
        if not project_text:
            continue
        project_data = {
            "name": "",
            "technologies": [],
            "description": "",
            "duration": "",
            "details": project_text
        }
        parts = [p.strip() for p in re.split(r'\s*-\s*', project_text) if p.strip()]
        if parts:
            first = parts[0]
            dur_match = re.search(r'\((.*?)\)', first)
            if dur_match:
                project_data["duration"] = dur_match.group(1)
                project_data["name"] = first.split('(')[0].strip()
            else:
                project_data["name"] = first

            found_tech = []
            for tech in tech_keywords:
                if tech.lower() in project_text.lower():
                    found_tech.append(tech)
            project_data["technologies"] = found_tech
            if len(parts) > 1:
                project_data["description"] = " - ".join(parts[1:])
        projects.append(project_data)
    return projects

def run_langextract(text: str) -> Dict[str, Any]:
    # use GEMINI_API_KEY from env via langextract API call param
    result = lx.extract(
        text_or_documents=text,
        prompt_description=PARSER_PROMPT,
        examples=EXAMPLES,
        model_id=os.environ.get("LANGEXTRACT_MODEL_ID", "gemini-2.5-flash-lite"),
        api_key=GEMINI_API_KEY,
    )
    return result

def parse_resume_from_text(text: str) -> Dict[str, Any]:
    # call run_langextract in a blocking way — intended to be run via asyncio.to_thread
    result = run_langextract(text)
    # group
    grouped = {
        "full_name": None,
        "email": None,
        "phone_number": None,
        "github": None,
        "linkedin": None,
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "achievements": []
    }
    for ext in result.extractions:
        cls = ext.extraction_class
        txt = ext.extraction_text.strip()
        if not txt:
            continue
        if cls in ["full_name", "email", "phone_number", "github", "linkedin"]:
            if not grouped[cls]:
                grouped[cls] = txt
        elif cls == "skills":
            if txt not in grouped["skills"]:
                grouped["skills"].append(txt)
        elif cls == "education":
            if txt not in grouped["education"]:
                grouped["education"].append(txt)
        elif cls == "experience":
            if txt not in grouped["experience"]:
                grouped["experience"].append(txt)
        elif cls == "projects":
            if txt not in grouped["projects"]:
                grouped["projects"].append(txt)
        elif cls == "certifications":
            if txt not in grouped["certifications"]:
                grouped["certifications"].append(txt)
        elif cls == "achievements":
            if txt not in grouped["achievements"]:
                grouped["achievements"].append(txt)

    structured_projects = parse_projects_from_extractions(result.extractions)
    parsed = {
        "personal_info": {
            "full_name": grouped["full_name"],
            "email": grouped["email"],
            "phone_number": grouped["phone_number"],
            "github": grouped["github"],
            "linkedin": grouped["linkedin"]
        },
        "skills": ", ".join(grouped["skills"]) if grouped["skills"] else None,
        "education": grouped["education"] or None,
        "experience": grouped["experience"] or None,
        "projects": structured_projects or None,
        "certifications": grouped["certifications"] or None,
        "achievements": grouped["achievements"] or None
    }
    return parsed

# ---------- Background parse task ----------
async def _bg_parse_and_store(filename: str, candidate_id: str):
    """
    background worker: read file, parse, store into MongoDB candidate collection, update tasks
    """
    try:
        filepath = os.path.join(RESUMES_DIR, filename)
        with open(filepath, "rb") as f:
            content = f.read()
        text = read_file_bytes(filename, content)
        if not text:
            raise ValueError("Empty extracted text from file")

        # run langextract in thread (blocking)
        parsed = await asyncio.to_thread(parse_resume_from_text, text)

        # build candidate doc
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

        # update task status
        await db.tasks.update_one({"task_id": candidate_id}, {"$set": {"status": "done", "completed_at": datetime.utcnow(), "result": {"parsed": True}}})
        logger.info(f"Parsed and stored candidate {candidate_id}")

    except Exception as e:
        logger.exception("Error in background parse")
        await db.tasks.update_one({"task_id": candidate_id}, {"$set": {"status": "failed", "completed_at": datetime.utcnow(), "error": str(e)}})


# ---------- Upload endpoint (saves file, creates task, schedules background parse) ----------
@api_router.post("/jobs/{job_id}/upload")
async def upload_resumes(job_id: str, background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    saved = []
    for file in files:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("pdf", "docx", "doc", "txt"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        dest = os.path.join(RESUMES_DIR, unique_name)

        # Save file to disk
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)

        # create a task row in DB
        task_doc = {
            "task_id": unique_name,
            "job_id": job_id,
            "filename": unique_name,
            "type": "parse",
            "status": "queued",
            "created_at": datetime.utcnow()
        }
        await db.tasks.insert_one(task_doc)

        # schedule background parse
        background_tasks.add_task(_bg_parse_and_store, unique_name, unique_name)

        saved.append({"filename": file.filename, "stored_as": unique_name})

    return {"status": "accepted", "saved": saved}


# ---------- Simple status endpoints (from your skeleton) ----------
@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**sc) for sc in status_checks]

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    await db.status_checks.insert_one(status_obj.dict())
    return status_obj

# ---------- Apify LinkedIn scraping endpoint ----------
if APIFY_TOKEN:
    apify_client = ApifyClient(APIFY_TOKEN)
else:
    apify_client = None
    logger.warning("APIFY_TOKEN not set; /scrape-linkedin will fail if invoked")

@api_router.post("/scrape-linkedin")
async def scrape_linkedin(req: LinkedInRequest):
    if not apify_client:
        raise HTTPException(status_code=500, detail="Apify client not configured (missing APIFY_TOKEN)")

    try:
        formatted_urls = [{"url": url_str} for url_str in req.profileUrls]
        run_input = {
            "urls": formatted_urls,
            "scrapeCompany": False,
            "findContacts": False,
            "findContacts.contactCompassToken": "",
        }
        run = apify_client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
        # Collect results from dataset
        ds = apify_client.dataset(run["defaultDatasetId"])
        results = [item for item in ds.iterate_items()]  # note: blocking call in this library
        return {"status": "success", "data": results}
    except Exception as e:
        logger.exception("Apify actor error")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- DuckDuckGo search helper (runs in thread) ----------
def ddg_search_sync(query: str, field_type: str = None) -> Dict[str, Any]:
    try:
        with DDGS() as ddgs:
            search_query = query
            company_name = query
            if field_type == "experience":
                company_name = re.sub(r'\s*·.*$', '', query)
                search_query = f"{company_name} official site OR website"
            elif field_type == "education":
                search_query = f"{query} official site university"

            results = list(ddgs.text(search_query, max_results=5))
            if not results:
                return {"verified": False, "top_result": None}
            # heuristics: try to find one that contains company_name or query
            for r in results:
                text_comb = (r.get("title","") + " " + r.get("href","")).lower()
                if field_type == "experience" and company_name.lower() in text_comb:
                    return {"verified": True, "top_result": r.get("href"), "title": r.get("title"), "snippet": r.get("body")}
                if field_type == "education" and query.lower() in text_comb:
                    return {"verified": True, "top_result": r.get("href"), "title": r.get("title"), "snippet": r.get("body")}
            # fallback to first result
            r = results[0]
            return {"verified": True, "top_result": r.get("href"), "title": r.get("title"), "snippet": r.get("body")}
    except Exception as e:
        return {"verified": False, "error": str(e)}

async def search_duckduckgo(query: str, field_type: str = None) -> Dict[str, Any]:
    return await asyncio.to_thread(ddg_search_sync, query, field_type)

# ---------- Verification utils (extract and scoring) ----------
def extract_entities(profile_json: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    educations = []
    experiences = []
    for edu in profile_json.get("educations", []):
        college = edu.get("title") or edu.get("subtitle") or "Unknown"
        if college and college != "Unknown":
            educations.append({"college": college})
    for exp in profile_json.get("experiences", []):
        company = exp.get("subtitle") or exp.get("companyName") or exp.get("title")
        position = exp.get("title") or "Unknown"
        if company and company != "Unknown":
            experiences.append({"company": company, "position": position})
    return {"educations": educations, "experiences": experiences}

def compute_score_and_tag(entries: List[Dict[str, Any]], field_type: str) -> Dict[str, Any]:
    scored_entries = []
    total_score = 0
    if not entries:
        return {"details": [], "average_score": 0, "overall_tag": "Not Found"}
    for entry in entries:
        verified = entry.get("verified", False)
        snippet = entry.get("snippet", "") or ""
        title = entry.get("title", "") or ""
        position = entry.get("position", "").lower() if field_type == "experience" else ""
        combined_text = f"{title} {snippet}".lower()
        score = 0
        if not verified or entry.get("top_result") is None:
            score = 0
        elif field_type == "education":
            college_name = entry.get("college", "").lower()
            similarity = fuzz.token_set_ratio(college_name, combined_text)
            if similarity >= 90:
                score = 100
            elif similarity >= 70:
                score = 50
            else:
                score = 0
        elif field_type == "experience":
            company_name = entry.get("company", "").lower()
            company_name = re.sub(r'\s*·.*$', '', company_name)
            company_similarity = fuzz.token_set_ratio(company_name, combined_text)
            if company_similarity >= 70:
                score = 50
                if position and position != "unknown" and position in combined_text:
                    score = 100
            else:
                score = 0

        if score >= 75:
            tag = "Verified"
        elif score <= 25:
            tag = "Not Found"
        else:
            tag = "Mismatch"

        total_score += score
        scored_entries.append({**entry, "score": score, "tag": tag})

    avg_score = round(total_score / len(scored_entries), 2) if scored_entries else 0
    return {"details": scored_entries, "average_score": avg_score, "overall_tag": ("Verified" if avg_score >= 75 else "Mismatch" if avg_score > 25 else "Not Found")}

# ---------- Verification endpoint ----------
@api_router.post("/verify-profile-data")
async def verify_profile_data(req: ProfileVerificationRequest):
    try:
        profiles = req.data if isinstance(req.data, list) else [req.data]
        output = []
        for profile in profiles:
            extracted = extract_entities(profile)
            # spawn searches in parallel
            edu_tasks = [search_duckduckgo(e["college"], field_type="education") for e in extracted["educations"]]
            exp_tasks = [search_duckduckgo(e["company"], field_type="experience") for e in extracted["experiences"]]
            edu_results = await asyncio.gather(*edu_tasks) if edu_tasks else []
            exp_results = await asyncio.gather(*exp_tasks) if exp_tasks else []
            verified_edu = [{**extracted["educations"][i], **edu_results[i]} for i in range(len(edu_results))] if edu_results else []
            verified_exp = [{**extracted["experiences"][i], **exp_results[i]} for i in range(len(exp_results))] if exp_results else []
            edu_score_info = compute_score_and_tag(verified_edu, field_type="education")
            exp_score_info = compute_score_and_tag(verified_exp, field_type="experience")
            output.append({"profile_url": profile.get("publicIdentifier") or profile.get("profileUrl") or "N/A", "education": edu_score_info, "experience": exp_score_info})
        return {"status": "success", "results": output}
    except Exception as e:
        logger.exception("verify_profile_data error")
        raise HTTPException(status_code=500, detail=str(e))

# ---------- Include router in app ----------
app.include_router(api_router)

# ---------- Shutdown event ----------
@app.on_event("shutdown")
async def shutdown():
    client.close()
    logger.info("shutdown: mongo client closed")

# ---------- Root health ----------
@app.get("/")
async def root():
    return {"service": "resumeai-backend", "time": datetime.utcnow().isoformat()}
