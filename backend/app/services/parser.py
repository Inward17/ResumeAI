import re
import random
import asyncio
import langextract as lx
from app.utils.prompts import PARSER_PROMPT, EXAMPLES
import os

# Max resumes sent to Gemini at the same time (per backend process).
# Raise it if your Gemini quota allows; the free tier only allows a few requests/minute.
PARSE_CONCURRENCY = int(os.getenv("PARSE_CONCURRENCY", "4"))
PARSE_TIMEOUT_SECONDS = float(os.getenv("PARSE_TIMEOUT_SECONDS", "120"))
PARSE_MAX_RETRIES = int(os.getenv("PARSE_MAX_RETRIES", "4"))
# langextract splits text into chunks of this many characters and makes one
# Gemini call per chunk. Its default (1000) turned a typical resume into 4-6
# calls; one chunk per resume cuts quota usage several-fold.
PARSER_MAX_CHAR_BUFFER = int(os.getenv("PARSER_MAX_CHAR_BUFFER", "8000"))

_TRANSIENT_MARKERS = ("429", "resource_exhausted", "rate limit", "quota", "503", "unavailable",
                      "overloaded", "500", "internal", "deadline", "timed out", "timeout")

_parse_semaphore = None


def _get_parse_semaphore() -> asyncio.Semaphore:
    global _parse_semaphore
    if _parse_semaphore is None:
        _parse_semaphore = asyncio.Semaphore(PARSE_CONCURRENCY)
    return _parse_semaphore


def _is_transient(exc: Exception) -> bool:
    message = f"{type(exc).__name__} {exc}".lower()
    return any(marker in message for marker in _TRANSIENT_MARKERS)


def parse_projects(extractions):
    """Parse project extractions into structured format"""
    projects = []
    project_extractions = [ext for ext in extractions if ext.extraction_class == "projects"]
    
    for project_ext in project_extractions:
        text = project_ext.extraction_text.strip()
        if not text:
            continue
        
        project = {
            "name": "",
            "technologies": [],
            "description": "",
            "duration": "",
            "details": text
        }
        
        lines = [line.strip() for line in text.split('-') if line.strip()]
        if lines:
            first_line = lines[0]
            duration_match = re.search(r'\((.*?)\)', first_line)
            
            if duration_match:
                project["duration"] = duration_match.group(1)
                project["name"] = first_line.split('(')[0].strip()
            else:
                project["name"] = first_line
            
            # Extract technologies
            tech_keywords = [
                "Python", "JavaScript", "React", "Node.js", "Java", "C++", "AWS", "Docker",
                "MongoDB", "PostgreSQL", "MySQL", "Flask", "Django", "FastAPI", "HTML", "CSS",
                "TypeScript", "Vue", "Angular", "Express", "Spring", "TensorFlow", "PyTorch"
            ]
            project["technologies"] = [tech for tech in tech_keywords if tech.lower() in text.lower()]
            
            if len(lines) > 1:
                project["description"] = " - ".join(lines[1:])
        
        projects.append(project)
    
    return projects


async def _extract_with_retries(text: str):
    """Call langextract with bounded concurrency, retrying rate limits / transient errors."""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    timeouts = 0
    for attempt in range(PARSE_MAX_RETRIES + 1):
        try:
            async with _get_parse_semaphore():
                # langextract is blocking, so run it in a thread with a timeout
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        lx.extract,
                        text_or_documents=text,
                        prompt_description=PARSER_PROMPT,
                        examples=EXAMPLES,
                        model_id="gemini-2.5-flash",
                        api_key=GEMINI_API_KEY,
                        max_char_buffer=PARSER_MAX_CHAR_BUFFER,
                    ),
                    timeout=PARSE_TIMEOUT_SECONDS,
                )
        except asyncio.TimeoutError:
            timeouts += 1
            print(f"Resume parsing timed out after {PARSE_TIMEOUT_SECONDS:.0f}s (attempt {attempt + 1})")
            if timeouts > 1 or attempt == PARSE_MAX_RETRIES:
                raise ValueError("Resume parsing timed out")
        except Exception as e:
            if attempt == PARSE_MAX_RETRIES or not _is_transient(e):
                raise
            print(f"Resume parsing transient error (attempt {attempt + 1}): {e}")
        # Exponential backoff with jitter so parallel workers don't retry in lockstep
        await asyncio.sleep(min(60, 2 ** (attempt + 1)) + random.uniform(0, 1))


async def parse_resume(text: str) -> dict:
    """Parse resume text and extract structured information"""
    
    result = await _extract_with_retries(text)

    # Group extractions
    data = {
        "full_name": "", "email": "", "phone_number": "", "github": "", "linkedin": "",
        "skills": [], "education": [], "experience": [], "projects": [],
        "certifications": [], "achievements": [],
        "university": [], "company": []  # NEW: For verification
    }
    
    for ext in result.extractions:
        cls = ext.extraction_class
        txt = ext.extraction_text.strip()
        if not txt:
            continue
        
        if cls in ["full_name", "email", "phone_number", "github", "linkedin"]:
            if not data[cls]:
                data[cls] = txt
        elif cls in data:  # Only append if key exists in data dict
            if txt not in data[cls]:
                data[cls].append(txt)
    
    # Parse projects
    structured_projects = parse_projects(result.extractions)
    
    # Build output
    return {
        "personal_info": {
            "full_name": data["full_name"] or None,
            "email": data["email"] or None,
            "phone_number": data["phone_number"] or None,
            "github": data["github"] or None,
            "linkedin": data["linkedin"] or None
        },
        "skills": ", ".join(data["skills"]) if data["skills"] else None,
        "education": data["education"] if data["education"] else None,
        "experience": data["experience"] if data["experience"] else None,
        "projects": structured_projects if structured_projects else None,
        "certifications": data["certifications"] if data["certifications"] else None,
        "achievements": data["achievements"] if data["achievements"] else None,
        # NEW: Extracted entity names for verification
        "university": data["university"] if data["university"] else None,
        "company": data["company"] if data["company"] else None,
    }