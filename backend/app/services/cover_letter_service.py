"""
Cover letters: storage, detection in bulk uploads, pairing with resumes, and AI analysis.

A cover letter is evidence for one application (job_id + candidate_id), stored on the
application document as ``cover_letter``. It never changes role match or credibility.
"""
import asyncio
import io
import json
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from app.database import db
from app.services.fact_checker_service import AIServiceUnavailable, _call_groq
from app.services.task_queue import IN_PROGRESS_STATUSES
from app.utils.file_utils import read_file
from app.utils.text_utils import as_data

MAX_LETTER_CHARS = 20000
ALLOWED_EXTENSIONS = ("pdf", "docx", "doc", "txt")
TEXT_EXTRACT_TIMEOUT_SECONDS = int(os.getenv("TEXT_EXTRACT_TIMEOUT_SECONDS", "60"))

# Task statuses for documents in a bulk upload that turned out to be cover letters
PENDING = "cover_letter_pending"      # waiting for its resume to finish
ATTACHED = "cover_letter_attached"
UNPAIRED = "cover_letter_unpaired"
UNPAIRED_MESSAGE = "Cover letter without a matching resume. Attach it from the candidate's dossier."

AI_DOWN = "Analysis unavailable: the AI service is down."
AI_BAD_ANSWER = "Analysis unavailable: the AI returned an answer that couldn't be read."


# ── Upload checks ───────────────────────────────────────────────────────────

_MAGIC = {"pdf": (b"%PDF-",), "docx": (b"PK\x03\x04",), "doc": (b"\xd0\xcf\x11\xe0", b"PK\x03\x04")}


def content_matches_extension(ext: str, content: bytes) -> bool:
    """Minimal content check so a file is what its extension says."""
    if ext == "txt":
        return b"\x00" not in content[:4096]
    return content.startswith(_MAGIC.get(ext, (b"\x00\x00invalid",)))


def extract_pages(filename: str, content: bytes) -> list[str]:
    """Text per page for PDFs (so a letter page can be split off), else one 'page'."""
    if filename.lower().endswith(".pdf"):
        import pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return [page.extract_text() or "" for page in pdf.pages]
        except Exception:
            return []
    return [read_file(filename, content)]


# ── Classification ─────────────────────────────────────────────────────────

_SALUTATION = re.compile(r"^\s*(dear\b|to whom it may concern|hello\b|greetings\b)", re.I | re.M)
_CLOSING = re.compile(
    r"^\s*(sincerely|yours sincerely|yours faithfully|yours truly|best regards|kind regards|warm regards|"
    r"regards|respectfully|best wishes|thank you for your (time|consideration))\b", re.I | re.M)
_LETTER_PHRASES = re.compile(
    r"\b(i am writing|i'm writing|to apply for|my application for|the (position|role) of|i am excited|"
    r"i look forward to|i would welcome)\b", re.I)
_SECTION = re.compile(
    r"^\s*(education|experience|work experience|professional experience|employment( history)?|skills|"
    r"technical skills|projects|certifications|achievements|summary|objective|publications|internships?)\s*:?\s*$",
    re.I | re.M)


def _tokens(filename: str) -> list[str]:
    return re.findall(r"[a-z]+", os.path.splitext(os.path.basename(filename or "").lower())[0])


def _signals(text: str, filename: str = "") -> tuple[int, int]:
    """(letter score, resume score) from cheap text and filename cues."""
    tokens = set(_tokens(filename))
    letter = resume = 0
    if tokens & {"cover", "coverletter", "letter", "motivation", "cl"}:
        letter += 3
    if tokens & {"resume", "cv"}:
        resume += 3
    head = "\n".join(text.splitlines()[:25])
    if _SALUTATION.search(head):
        letter += 2
    if _CLOSING.search(text):
        letter += 2
    if _LETTER_PHRASES.search(text):
        letter += 1
    sections = {m.group(1).lower() for m in _SECTION.finditer(text)}
    resume += min(2 * len(sections), 6)
    return letter, resume


def classify_heuristic(text: str, filename: str = "") -> str | None:
    """'cover_letter', 'resume', or None when the cues disagree."""
    letter, resume = _signals(text, filename)
    if letter >= 4 and resume <= 2:
        return "cover_letter"
    if letter == 0 or resume - letter >= 3:
        return "resume"
    return None


async def classify_with_ai(text: str) -> str:
    """One small AI call for unclear documents; falls back to 'resume' (the old behaviour)."""
    system = ('Decide whether this document is a resume/CV or a cover letter. '
              'Return ONLY JSON: {"type": "resume"} or {"type": "cover_letter"}.')
    try:
        data = _parse_json(await _call_groq(system, as_data(text[:4000]), temperature=0))
    except (AIServiceUnavailable, ValueError):
        return "resume"
    return "cover_letter" if isinstance(data, dict) and data.get("type") == "cover_letter" else "resume"


async def classify(text: str, filename: str = "") -> str:
    return classify_heuristic(text, filename) or await classify_with_ai(text)


def split_combined(pages: list[str]) -> tuple[str, str] | None:
    """(letter, resume) when a PDF is a cover letter followed by a resume, else None.

    ponytail: only the letter-then-resume order with a 1-2 page letter and clear
    resume headings is split; anything less certain is treated as a resume.
    """
    for k in (2, 1):  # a two-page letter first, so its second page isn't parsed as resume
        if len(pages) <= k:
            continue
        letter, rest = "\n".join(pages[:k]), "\n".join(pages[k:])
        rest_resume = _signals(rest)[1]
        if classify_heuristic(letter) == "cover_letter" and rest_resume >= 4 and not _SALUTATION.search(rest):
            return letter, rest
    return None


# ── Pairing ────────────────────────────────────────────────────────────────

_NAME_LINE = re.compile(r"^[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-\.]*){1,3}$")
_STEM_STOP = {"resume", "cv", "cover", "coverletter", "letter", "cl", "application", "final", "updated",
              "new", "copy", "and", "for", "the", "of", "my", "motivation"}


def letter_names(text: str) -> list[str]:
    """Likely author names: the line after the sign-off, and the letter's first line."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    is_name = lambda l: _NAME_LINE.match(l) and not _SALUTATION.match(l) and not _CLOSING.match(l)
    names = []
    for i, line in enumerate(lines):
        if _CLOSING.match(line):
            names += [n for n in lines[i + 1:i + 3] if is_name(n)][:1]
    if lines and is_name(lines[0]):
        names.append(lines[0])
    return list(dict.fromkeys(names))


def _name_key(name: str) -> str:
    # Initials are dropped so "Jane A. Doe" matches "Jane Doe"
    return " ".join(sorted(t for t in re.findall(r"[a-z]+", (name or "").lower()) if len(t) > 1))


def names_match(a: str, b: str) -> bool:
    ka, kb = _name_key(a), _name_key(b)
    return bool(ka and kb) and SequenceMatcher(None, ka, kb).ratio() >= 0.9


def filename_stem(filename: str) -> str:
    """'Jane_Doe_Resume.pdf' and 'Jane_Doe_Cover_Letter.pdf' both give 'doe jane'."""
    return " ".join(sorted({t for t in _tokens(filename) if len(t) > 1 and t not in _STEM_STOP}))


def match_letter(letter: dict, resumes: list[dict]) -> str | None:
    """Candidate id for a letter, or None when there's no match or it's ambiguous.

    resumes: [{"candidate_id", "name", "stem"}], one per finished resume upload.
    """
    stem = letter.get("letter_stem")
    names = letter.get("letter_names") or []
    by_stem = {r["candidate_id"] for r in resumes if stem and r.get("stem") == stem}
    by_name = {r["candidate_id"] for r in resumes if any(names_match(n, r.get("name") or "") for n in names)}
    if len(by_stem) == 1 and (not by_name or by_name == by_stem):
        return next(iter(by_stem))
    if not by_stem and len(by_name) == 1:
        return next(iter(by_name))
    return None


async def _job_resumes(job_id: str) -> list[dict]:
    apps = await db.applications.find({"job_id": job_id}, {"candidate_id": 1}).to_list(length=None)
    ids = [a["candidate_id"] for a in apps]
    names = {c["candidate_id"]: (c.get("parsed") or {}).get("personal_info", {}).get("full_name")
             async for c in db.candidates.find({"candidate_id": {"$in": ids}},
                                               {"candidate_id": 1, "parsed.personal_info.full_name": 1})}
    stems = {}
    async for t in db.tasks.find({"job_id": job_id, "resolved_candidate_id": {"$in": ids}},
                                 {"resolved_candidate_id": 1, "original_filename": 1}):
        stems.setdefault(t["resolved_candidate_id"], set()).add(filename_stem(t.get("original_filename") or ""))
    out = []
    for cid in ids:
        for stem in stems.get(cid) or {""}:
            out.append({"candidate_id": cid, "name": names.get(cid), "stem": stem})
    return out


# ── Storage ────────────────────────────────────────────────────────────────

def new_letter(text: str, source: str, filename: str | None) -> dict:
    text = text.strip()
    return {
        "text": text[:MAX_LETTER_CHARS],
        "truncated": len(text) > MAX_LETTER_CHARS,
        "source": source,  # uploaded / pasted / auto_detected
        "filename": filename,
        "uploaded_at": datetime.utcnow(),
        "analysis": None,
        "analysis_status": "pending",
        "analysis_error": None,
        "analyzed_at": None,
    }


async def attach(job_id: str, candidate_id: str, letter: dict, replace: bool = True) -> bool:
    """Store a letter on the application; with replace=False an existing letter is kept."""
    query = {"job_id": job_id, "candidate_id": candidate_id}
    if not replace:
        query["cover_letter"] = {"$exists": False}
    result = await db.applications.update_one(query, {"$set": {"cover_letter": letter}})
    return result.modified_count == 1


async def _attach_auto(job_id: str, candidate_id: str, text: str, filename: str) -> bool:
    letter = new_letter(text, "auto_detected", filename)
    if not await attach(job_id, candidate_id, letter, replace=False):
        return False
    await analyze_and_store(job_id, candidate_id)
    return True


# ── Bulk upload flow (called from the resume task worker) ──────────────────

async def prepare_upload(task: dict, path: str) -> dict:
    """Classify one uploaded document before it is parsed as a resume.

    Returns {"kind": "cover_letter"} when the task is now a pending letter (file deleted),
    else {"kind": "resume", "resume_text": str|None, "letter_text": str|None} where the
    texts are set only when a combined letter+resume PDF was split.
    Any failure here falls back to the normal resume path.
    """
    resume = {"kind": "resume", "resume_text": None, "letter_text": None}
    filename = task.get("original_filename") or task["filename"]
    try:
        content = await asyncio.to_thread(_read_bytes, path)
        pages = await asyncio.wait_for(asyncio.to_thread(extract_pages, task["filename"], content),
                                       TEXT_EXTRACT_TIMEOUT_SECONDS)
        text = "\n".join(pages)
        if not text.strip():
            return resume
        split = split_combined(pages)
        if split:
            return {**resume, "letter_text": split[0], "resume_text": split[1]}
        if await classify(text, filename) != "cover_letter":
            return resume
    except Exception as e:
        print(f"[COVER] Classification skipped for task {task.get('task_id')}: {type(e).__name__}")
        return resume

    await db.tasks.update_one({"task_id": task["task_id"]}, {"$set": {
        "status": PENDING, "kind": "cover_letter", "classified_at": datetime.utcnow(),
        "cover_letter_text": text.strip()[:MAX_LETTER_CHARS],
        "letter_names": letter_names(text), "letter_stem": filename_stem(filename),
    }})
    try:
        os.remove(path)  # the text is kept; the file isn't needed
    except OSError:
        pass
    return {"kind": "cover_letter"}


def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


async def after_resume(task: dict, letter_text: str | None):
    """After a resume task: attach the letter split from it, then pair waiting letters."""
    try:
        if letter_text:
            done = await db.tasks.find_one({"task_id": task["task_id"]})
            cid = (done or {}).get("resolved_candidate_id")
            if cid and done.get("status") in ("done", "verification_failed"):
                await _attach_auto(task["job_id"], cid, letter_text,
                                   task.get("original_filename") or task["filename"])
        await settle_job(task["job_id"])
    except Exception as e:
        # The resume itself is saved; a cover letter problem mustn't fail its task
        print(f"[COVER] Pairing failed for job {task.get('job_id')}: {type(e).__name__}: {e}")


async def settle_job(job_id: str):
    """Pair waiting cover letters with finished resumes of the job.

    Once nothing in the job is queued or in progress, letters still waiting are
    reported as unpaired; they never create a candidate.
    """
    if not await db.tasks.find_one({"job_id": job_id, "status": PENDING}, {"_id": 1}):
        return
    # Counted before reading resumes: if nothing is in flight now, every resume is saved
    in_flight = await db.tasks.count_documents(
        {"job_id": job_id, "status": {"$in": ["queued", *IN_PROGRESS_STATUSES]}})
    resumes = await _job_resumes(job_id)
    async for letter in db.tasks.find({"job_id": job_id, "status": PENDING}):
        cid = match_letter(letter, resumes)
        if not cid:
            continue
        # Claim first so two workers can't attach the same letter
        claim = await db.tasks.update_one({"task_id": letter["task_id"], "status": PENDING},
                                          {"$set": {"status": ATTACHED}})
        if not claim.modified_count:
            continue
        attached = await _attach_auto(job_id, cid, letter.get("cover_letter_text") or "",
                                      letter.get("original_filename") or letter.get("filename"))
        update = {"completed_at": datetime.utcnow(), "resolved_candidate_id": cid}
        if not attached:
            update.update(status=UNPAIRED, error="This candidate already has a cover letter. "
                                                 "Replace it from the dossier if this one is newer.")
        await db.tasks.update_one({"task_id": letter["task_id"]},
                                  {"$set": update, "$unset": {"cover_letter_text": ""}})
    if not in_flight:
        await _mark_unpaired({"job_id": job_id, "status": PENDING})


async def _mark_unpaired(query: dict):
    await db.tasks.update_many(query, {
        "$set": {"status": UNPAIRED, "completed_at": datetime.utcnow(), "error": UNPAIRED_MESSAGE},
        "$unset": {"cover_letter_text": ""},
    })


async def expire_waiting_letters(job_id: str):
    """Recovery for a worker that died before pairing: release letters left waiting.

    Only when nothing in the job is in flight and no task finished in the last two
    minutes, so it never races a worker that is pairing right now.
    """
    if not await db.tasks.find_one({"job_id": job_id, "status": PENDING}, {"_id": 1}):
        return
    if await db.tasks.find_one({"job_id": job_id, "$or": [
        {"status": {"$in": ["queued", *IN_PROGRESS_STATUSES]}},
        {"completed_at": {"$gte": datetime.utcnow() - timedelta(minutes=2)}},
    ]}, {"_id": 1}):
        return
    await _mark_unpaired({"job_id": job_id, "status": PENDING})


# ── Analysis ───────────────────────────────────────────────────────────────

ANALYSIS_SYSTEM = """You review a job applicant's cover letter for a recruiter, comparing it with the job and the applicant's resume.
Return ONLY a JSON object with exactly these fields:
{
  "summary": "2-3 sentences on what the letter says",
  "fit": {
    "specificity": "specific" | "generic" | "mixed",
    "addresses_role": true | false,
    "requirements_addressed": ["job requirements the letter speaks to, copied from the job's list"],
    "notes": "1-2 sentences on how well the letter fits this job"
  },
  "contradictions": [
    {"topic": "employer" | "dates" | "title" | "degree" | "skill" | "other",
     "letter_claim": "what the letter says", "resume_says": "what the resume says, or 'not on resume'",
     "severity": "major" | "minor"}
  ],
  "probe_points": ["2-4 short points the interviewer should probe"]
}
List a contradiction only where the letter and resume disagree, or the letter claims a skill or experience the resume doesn't show. Use [] when there are none.
Do not score the candidate and do not guess whether the letter was written by AI."""


def _parse_json(text) -> dict | list:
    if not isinstance(text, str):
        raise ValueError("no text")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    match = re.search(r"\{.*\}", cleaned, re.S)
    return json.loads(match.group(0) if match else cleaned)


def _s(value, limit: int = 600) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def validate_analysis(data) -> dict | None:
    """The model's answer in the stored shape, or None if it isn't usable."""
    if not isinstance(data, dict) or not _s(data.get("summary")):
        return None
    fit = data.get("fit") if isinstance(data.get("fit"), dict) else {}
    # Missing or null lists are empty; any other non-list shape makes the answer unusable
    if any(v is not None and not isinstance(v, list) for v in
           (data.get("contradictions"), data.get("probe_points"), fit.get("requirements_addressed"))):
        return None
    specificity = fit.get("specificity") if fit.get("specificity") in ("specific", "generic", "mixed") else None
    contradictions = []
    for c in data.get("contradictions") or []:
        if not isinstance(c, dict) or not _s(c.get("letter_claim")):
            continue
        contradictions.append({
            "topic": c.get("topic") if c.get("topic") in ("employer", "dates", "title", "degree", "skill") else "other",
            "letter_claim": _s(c.get("letter_claim"), 300),
            "resume_says": _s(c.get("resume_says"), 300),
            "severity": "major" if c.get("severity") == "major" else "minor",
        })
    contradictions.sort(key=lambda c: c["severity"] != "major")
    return {
        "summary": _s(data.get("summary"), 1000),
        "fit": {
            "specificity": specificity,
            "addresses_role": fit.get("addresses_role") if isinstance(fit.get("addresses_role"), bool) else None,
            "requirements_addressed": [r for r in (_s(x, 120) for x in fit.get("requirements_addressed") or []) if r][:12],
            "notes": _s(fit.get("notes")),
        },
        "contradictions": contradictions[:10],
        "probe_points": [p for p in (_s(x, 300) for x in data.get("probe_points") or []) if p][:4],
    }


def _resume_context(parsed: dict) -> str:
    keep = ("personal_info", "skills", "experience", "education", "company", "university", "certifications", "projects")
    return json.dumps({k: parsed.get(k) for k in keep if parsed.get(k)}, default=str)[:5000]


async def analyze_letter(letter_text: str, job: dict, parsed_resume: dict) -> tuple[dict | None, str | None]:
    """(analysis, None) on success, (None, error message) when the AI is down or answers badly."""
    user = (
        f"JOB\nTitle: {job.get('job_title', '')}\n"
        f"Description: {(job.get('job_description') or '')[:1500]}\n"
        f"Required skills: {', '.join(job.get('required_skills') or [])}\n"
        f"Preferred skills: {', '.join(job.get('preferred_skills') or [])}\n\n"
        f"RESUME (parsed)\n{as_data(_resume_context(parsed_resume or {}))}\n\n"
        f"COVER LETTER\n{as_data(letter_text[:8000])}"
    )
    try:
        raw = await _call_groq(ANALYSIS_SYSTEM, user, temperature=0.2)
    except AIServiceUnavailable:
        return None, AI_DOWN
    try:
        analysis = validate_analysis(_parse_json(raw))
    except ValueError:
        analysis = None
    return (analysis, None) if analysis else (None, AI_BAD_ANSWER)


async def analyze_and_store(job_id: str, candidate_id: str) -> dict | None:
    """Analyse the application's current letter and store the result; returns the letter."""
    from bson import ObjectId
    app = await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id})
    letter = (app or {}).get("cover_letter")
    if not letter:
        return None
    job = await db.jobs.find_one({"_id": ObjectId(job_id)}) or {}
    candidate = await db.candidates.find_one({"candidate_id": candidate_id}) or {}
    analysis, error = await analyze_letter(letter.get("text") or "", job, candidate.get("parsed") or {})
    update = {
        "cover_letter.analysis": analysis,
        "cover_letter.analysis_status": "done" if analysis else "unavailable",
        "cover_letter.analysis_error": error,
        "cover_letter.analyzed_at": datetime.utcnow() if analysis else None,
    }
    # Only if the letter wasn't replaced while the AI was working
    await db.applications.update_one(
        {"_id": app["_id"], "cover_letter.uploaded_at": letter["uploaded_at"]}, {"$set": update})
    app = await db.applications.find_one({"_id": app["_id"]}, {"cover_letter": 1})
    return (app or {}).get("cover_letter")
