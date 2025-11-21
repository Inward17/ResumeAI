# app.py
from fastapi import FastAPI, File, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import textwrap
import tempfile
import pdfplumber
import docx
import json
import glob
import datetime
import asyncio
import re
from pathlib import Path

# async mongodb driver
from motor.motor_asyncio import AsyncIOMotorClient

# langextract (synchronous)
import langextract as lx

# ---------- SETTINGS ----------
class Settings(BaseSettings):
    MODEL_ID: str
    LANGEXTRACT_API_KEY: str
    MONGO_URI: str
    MONGO_DB: str
    ALLOWED_RESUMES_DIR: str

    class Config:
        env_file = Path(".env")
        env_file_encoding = "utf-8"

settings = Settings()  # will raise if required vars missing

# ---------- FASTAPI APP ----------
app = FastAPI(title="Resume Parser API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# make sure resumes dir exists
Path(settings.ALLOWED_RESUMES_DIR).mkdir(parents=True, exist_ok=True)

# ---------- HELPERS: file reading ----------
def read_pdf(file_path: str) -> str:
    # try normal extraction, fallback to words if needed
    text_pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            ptext = page.extract_text() or ""
            if not ptext:
                # fallback: join words (works for odd layouts)
                words = page.extract_words()
                if words:
                    ptext = " ".join(w.get("text", "") for w in words)
            text_pages.append(ptext)
    return "\n\n".join(text_pages)

def read_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

def read_file(file_path: str) -> str:
    ext = file_path.lower().split(".")[-1]
    if ext == "pdf":
        return read_pdf(file_path)
    elif ext == "docx":
        return read_docx(file_path)
    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {ext}")

# ---------- PROMPT + EXAMPLES ----------
PROMPT = textwrap.dedent("""
Extract structured resume information from the entire document.
Extract each field only ONCE from the complete resume.
Return the following information:
- full_name: The candidate's full name
- email: Email address
- phone_number: Contact phone number
- github: GitHub profile URL
- linkedin: LinkedIn profile URL
- skills: All technical skills, languages, frameworks, and tools (as a comma-separated list)
- education: All education details including degree, university, year
- experience: All work experience including company, role, duration, and responsibilities
- projects: All project details including project name, technologies used, and description
- certifications: All certifications with issuing organization
- achievements: All achievements, awards, or accomplishments
""")

EXAMPLES = [
    lx.data.ExampleData(
        text=textwrap.dedent("""
        John Doe
        Email: john.doe@gmail.com
        Phone: +1 555-123-4567
        GitHub: github.com/johndoe
        LinkedIn: linkedin.com/in/johndoe

        SKILLS
        Python, FastAPI, Docker, React, MongoDB

        EDUCATION
        B.Tech in Computer Science, MIT, 2020

        EXPERIENCE
        Software Engineer at Google (2020–2024)
        - Built scalable microservices
        - Led team of 5 developers

        PROJECTS
        E-commerce Platform
        Python, Flask, React, PostgreSQL
        - Built a full-stack e-commerce application
        - Implemented payment gateway integration
        AI based Chatbot
        Python, TensorFlow, NLP
        - Developed an AI chatbot for customer support 
        - Integrated with existing CRM systems

        CERTIFICATIONS
        AWS Certified Solutions Architect (Amazon)
        Docker Certified Associate (Docker Inc.)

        ACHIEVEMENTS
        - Won Best Innovation Award at TechHack 2023
        - Published research paper in IEEE Conference
        """),
        extractions=[
            lx.data.Extraction(extraction_class="full_name", extraction_text="John Doe"),
            lx.data.Extraction(extraction_class="email", extraction_text="john.doe@gmail.com"),
            lx.data.Extraction(extraction_class="phone_number", extraction_text="+1 555-123-4567"),
            lx.data.Extraction(extraction_class="github", extraction_text="github.com/johndoe"),
            lx.data.Extraction(extraction_class="linkedin", extraction_text="linkedin.com/in/johndoe"),
            lx.data.Extraction(extraction_class="skills", extraction_text="Python, FastAPI, Docker, React, MongoDB"),
            lx.data.Extraction(extraction_class="education", extraction_text="B.Tech in Computer Science, MIT, 2020"),
            lx.data.Extraction(extraction_class="experience", extraction_text="Software Engineer at Google (2020–2024) - Built scalable microservices - Led team of 5 developers"),
            lx.data.Extraction(extraction_class="projects", extraction_text="E-commerce Platform - Python, Flask, React, PostgreSQL - Built a full-stack e-commerce application - Implemented payment gateway integration"),
            lx.data.Extraction(extraction_class="certifications", extraction_text="AWS Certified Solutions Architect (Amazon), Docker Certified Associate (Docker Inc.)"),
            lx.data.Extraction(extraction_class="achievements", extraction_text="Won Best Innovation Award at TechHack 2023, Published research paper in IEEE Conference"),
        ]
    )
]

# ---------- UTILS: fallback project finder ----------
def find_projects_fallback(text: str) -> List[str]:
    # look around headings like "Projects", "Selected Projects", etc.
    projects = []
    pattern = re.compile(r"(projects?|selected projects|personal projects)\s*[:\-]?\s*\n(.*?)(\n[A-Z][A-Za-z ]{1,40}\s*[:\n]|$)", re.I | re.S)
    for m in pattern.finditer(text):
        block = m.group(2).strip()
        # split heuristically by double newlines or bullets or numbered lists
        items = re.split(r"\n{2,}|\n-\s+|\n•\s+|\n\s*\d+\.\s+|\n[A-Z][^\n]+\n-{3,}", block)
        for it in items:
            it = it.strip()
            if len(it) > 20:  # filter noise
                # collapse multiple spaces and newlines
                it = re.sub(r"\s{2,}", " ", it.replace("\n", " ").strip())
                projects.append(it)
    return projects

# ---------- EXTRACTOR LOGIC ----------
def group_extractions(result) -> dict:
    grouped_data = {
        "full_name": "",
        "email": "",
        "phone_number": "",
        "github": "",
        "linkedin": "",
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "achievements": []
    }

    for ext in result.extractions:
        extraction_class = getattr(ext, "extraction_class", None)
        extraction_text = (getattr(ext, "extraction_text", "") or "").strip()

        if not extraction_text:
            continue

        if extraction_class in ["full_name", "email", "phone_number", "github", "linkedin"]:
            if not grouped_data[extraction_class]:
                grouped_data[extraction_class] = extraction_text
        elif extraction_class == "skills":
            # skills may be comma separated; split and extend
            parts = [p.strip() for p in re.split(r",|\n", extraction_text) if p.strip()]
            for p in parts:
                if p not in grouped_data["skills"]:
                    grouped_data["skills"].append(p)
        elif extraction_class == "education":
            if extraction_text not in grouped_data["education"]:
                grouped_data["education"].append(extraction_text)
        elif extraction_class == "experience":
            if extraction_text not in grouped_data["experience"]:
                grouped_data["experience"].append(extraction_text)
        elif extraction_class == "projects":
            # split multi-project text into individual items heuristically
            parts = re.split(r"\n{2,}|\n-\s+|\n•\s+|\n\s*\d+\.\s+", extraction_text)
            for p in parts:
                p = p.strip()
                if p and p not in grouped_data["projects"]:
                    grouped_data["projects"].append(p)
        elif extraction_class == "certifications":
            if extraction_text not in grouped_data["certifications"]:
                grouped_data["certifications"].append(extraction_text)
        elif extraction_class == "achievements":
            parts = [p.strip() for p in re.split(r",|\n|;", extraction_text) if p.strip()]
            for p in parts:
                if p not in grouped_data["achievements"]:
                    grouped_data["achievements"].append(p)

    # Flatten skills list into comma separated string or None
    if grouped_data["skills"]:
        grouped_data["skills"] = ", ".join(grouped_data["skills"])
    else:
        grouped_data["skills"] = None

    extracted_data = {
        "personal_info": {
            "full_name": grouped_data["full_name"] or None,
            "email": grouped_data["email"] or None,
            "phone_number": grouped_data["phone_number"] or None,
            "github": grouped_data["github"] or None,
            "linkedin": grouped_data["linkedin"] or None,
        },
        "skills": grouped_data["skills"],
        "education": grouped_data["education"] or None,
        "experience": grouped_data["experience"] or None,
        "projects": grouped_data["projects"] or None,
        "certifications": grouped_data["certifications"] or None,
        "achievements": grouped_data["achievements"] or None,
    }
    return extracted_data

async def run_extraction_for_text(text: str):
    # run langextract in a thread (since it's synchronous)
    def sync_extract():
        return lx.extract(
            text_or_documents=text,
            prompt_description=PROMPT,
            examples=EXAMPLES,
            model_id=settings.MODEL_ID,
            api_key=settings.LANGEXTRACT_API_KEY,
        )
    result = await asyncio.to_thread(sync_extract)
    return result

# ---------- MONGODB (motor) ----------
mongo_client: Optional[AsyncIOMotorClient] = None
db = None

@app.on_event("startup")
async def startup_db_client():
    global mongo_client, db
    # ensure API key exists
    if not settings.LANGEXTRACT_API_KEY:
        raise RuntimeError("Please set LANGEXTRACT_API_KEY in environment or .env (do not hardcode secrets).")

    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB]

    # ensure index for faster queries
    await db.resumes.create_index("metadata.filename")

@app.on_event("shutdown")
async def shutdown_db_client():
    global mongo_client
    if mongo_client:
        mongo_client.close()

# ---------- Pydantic models ----------
class ExtractResponse(BaseModel):
    status: str
    data: dict

class ProcessDirectoryRequest(BaseModel):
    directory: Optional[str] = None
    patterns: Optional[List[str]] = None

# ---------- CORE: process a single file path ----------
async def extract_from_file_path(file_path: str, source: str = "local") -> Optional[dict]:
    try:
        # read raw text and save for debugging
        raw_text = await asyncio.to_thread(read_file, file_path)
        await asyncio.to_thread(lambda: open(file_path + ".raw.txt", "w", encoding="utf-8").write(raw_text))

        # run extraction (if resume is very long, we still run on whole text first)
        result = await run_extraction_for_text(raw_text)

        # save raw extraction output for debugging
        try:
            serial_extractions = [{"class": getattr(e, "extraction_class", None), "text": getattr(e, "extraction_text", None)} for e in result.extractions]
            await asyncio.to_thread(lambda: open(file_path + ".extractions.json", "w", encoding="utf-8").write(json.dumps(serial_extractions, indent=2, ensure_ascii=False)))
        except Exception:
            pass

        structured = group_extractions(result)

        # fallback: try regex-based project detection and merge results
        fallback_projects = find_projects_fallback(raw_text)
        if fallback_projects:
            structured_projects = structured.get("projects") or []
            for p in fallback_projects:
                if p not in structured_projects:
                    structured_projects.append(p)
            structured["projects"] = structured_projects

        metadata = {
            "filename": os.path.basename(file_path),
            "path": os.path.abspath(file_path),
            "source": source,
            "processed_at": datetime.datetime.utcnow().isoformat() + "Z"
        }

        document = {
            "metadata": metadata,
            "extracted": structured
        }

        # save JSON locally (use jsonable_encoder to ensure serialization)
        output_file = os.path.splitext(file_path)[0] + "_data.json"
        await asyncio.to_thread(lambda: open(output_file, "w", encoding="utf-8").write(json.dumps(jsonable_encoder(document), indent=2, ensure_ascii=False)))

        # insert into mongodb and convert ObjectId to str
        insert_result = await db.resumes.insert_one(document)
        document["_id"] = str(insert_result.inserted_id)

        return document

    except Exception as e:
        return {"error": str(e), "file": file_path}

# ---------- API ENDPOINTS ----------
@app.post("/extract", response_model=ExtractResponse)
async def extract_resume(file: UploadFile = File(...)):
    """Upload a single resume file and extract + store it in MongoDB"""
    try:
        suffix = os.path.splitext(file.filename)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        document = await extract_from_file_path(tmp_path, source="upload")
        # cleanup
        try:
            os.remove(tmp_path)
        except Exception:
            pass

        if not document:
            raise HTTPException(status_code=500, detail="Extraction failed")

        return JSONResponse(content=jsonable_encoder({"status": "success", "data": document}))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-multiple", response_model=ExtractResponse)
async def extract_multiple_resumes(files: List[UploadFile] = File(...)):
    """Upload multiple resume files in one request"""
    results = {}
    for file in files:
        suffix = os.path.splitext(file.filename)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        doc = await extract_from_file_path(tmp_path, source="upload-multiple")
        results[file.filename] = doc
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return JSONResponse(content=jsonable_encoder({"status": "success", "data": results}))

@app.post("/process-directory", response_model=ExtractResponse)
async def process_directory(req: ProcessDirectoryRequest = Body(...)):
    """
    Process resumes from server-side directories.
    To avoid arbitrary filesystem access, by default it only processes files inside the configured ALLOWED_RESUMES_DIR.
    You can pass 'directory' (relative to ALLOWED_RESUMES_DIR) or 'patterns' (glob patterns relative to ALLOWED_RESUMES_DIR).
    """
    base_dir = settings.ALLOWED_RESUMES_DIR
    if req.directory:
        target_dir = os.path.abspath(os.path.join(base_dir, req.directory))
    else:
        target_dir = os.path.abspath(base_dir)

    if not target_dir.startswith(os.path.abspath(base_dir)):
        raise HTTPException(status_code=400, detail="Directory not allowed")

    if req.patterns:
        files = []
        for p in req.patterns:
            files.extend(glob.glob(os.path.join(base_dir, p)))
        files = sorted(set(files))
    else:
        patterns = ["*.pdf", "*.docx", "*.txt"]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(target_dir, pattern)))
        files = sorted(set(files))

    if not files:
        raise HTTPException(status_code=404, detail="No files found to process")

    all_results = {}
    for fp in files:
        res = await extract_from_file_path(fp, source="directory")
        all_results[fp] = res

    combined_output = os.path.join(target_dir, "all_resumes_data.json")
    await asyncio.to_thread(lambda: open(combined_output, "w", encoding="utf-8").write(json.dumps(jsonable_encoder(all_results), indent=2, ensure_ascii=False)))

    return JSONResponse(content=jsonable_encoder({"status": "success", "data": all_results}))

@app.get("/resumes")
async def list_resumes(limit: int = 50, skip: int = 0):
    """List stored resumes metadata (paginated)"""
    cursor = db.resumes.find({}, {"extracted": 0}).sort("metadata.processed_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    return {"status": "success", "count": len(items), "items": items}

@app.get("/resumes/{resume_id}")
async def get_resume(resume_id: str):
    """Get a single resume document by MongoDB _id"""
    from bson import ObjectId
    try:
        doc = await db.resumes.find_one({"_id": ObjectId(resume_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Resume not found")
        doc["_id"] = str(doc["_id"])
        return {"status": "success", "data": doc}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str):
    from bson import ObjectId
    try:
        result = await db.resumes.delete_one({"_id": ObjectId(resume_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Resume not found")
        return {"status": "success", "deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
