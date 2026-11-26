"""Cover letter attached to one application (job + candidate) from the candidate dossier."""
import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile

from app.auth import AuthUser, get_current_user, require_job_action, require_job_owner
from app.database import db
from app.org import ensure_org
from app.services import cover_letter_service as cl
from app.services.quota import rate_limit, use_quota
from app.utils.file_utils import read_file

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

router = APIRouter(prefix="/jobs", tags=["cover-letter"])
PATH = "/{job_id}/candidates/{candidate_id}/cover-letter"


async def _require_application(job_id: str, candidate_id: str) -> dict:
    app = await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"cover_letter": 1})
    if not app:
        # 404 so other workspaces' candidate ids aren't revealed
        raise HTTPException(404, "Candidate not found")
    return app


async def _letter_from_request(request: Request) -> dict:
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, UploadFile) or not file.filename:
            raise HTTPException(400, "Attach a file named 'file'")
        name = os.path.basename(file.filename)
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        if ext not in cl.ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {ext or 'none'}")
        content = await file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
        if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"{name} is larger than {MAX_UPLOAD_MB} MB")
        if not cl.content_matches_extension(ext, content):
            raise HTTPException(400, f"{name} is not a valid .{ext} file")
        # Read in memory: the upload never touches the disk
        try:
            text = await asyncio.wait_for(asyncio.to_thread(read_file, name, content), cl.TEXT_EXTRACT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise HTTPException(400, f"{name} took too long to read")
        source, filename = "uploaded", name
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Send a file (multipart) or JSON {\"text\": \"...\"}")
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            raise HTTPException(400, "Send a file (multipart) or JSON {\"text\": \"...\"}")
        source, filename = "pasted", None
    if not (text or "").strip():
        raise HTTPException(400, "No text could be read from this cover letter")
    return cl.new_letter(text, source, filename)


@router.get(PATH, dependencies=[Depends(require_job_owner)])
async def get_cover_letter(job_id: str, candidate_id: str):
    app = await _require_application(job_id, candidate_id)
    return {"cover_letter": app.get("cover_letter")}


@router.post(PATH, dependencies=[Depends(require_job_action("candidate.verify"))])
async def attach_cover_letter(job_id: str, candidate_id: str, request: Request,
                              user: AuthUser = Depends(get_current_user)):
    """Attach (or replace) the letter from a file upload or pasted text, then analyse it."""
    rate_limit(user.uid, "ai")
    await _require_application(job_id, candidate_id)
    letter = await _letter_from_request(request)
    await use_quota(await ensure_org(user), "ai_call", feature="cover_letters")
    await cl.attach(job_id, candidate_id, letter)
    return {"cover_letter": await cl.analyze_and_store(job_id, candidate_id)}


@router.post(PATH + "/analysis", dependencies=[Depends(require_job_action("ai.run"))])
async def retry_cover_letter_analysis(job_id: str, candidate_id: str, user: AuthUser = Depends(get_current_user)):
    rate_limit(user.uid, "ai")
    app = await _require_application(job_id, candidate_id)
    if not app.get("cover_letter"):
        raise HTTPException(404, "No cover letter attached")
    await use_quota(await ensure_org(user), "ai_call", feature="cover_letters")
    return {"cover_letter": await cl.analyze_and_store(job_id, candidate_id)}


@router.delete(PATH, dependencies=[Depends(require_job_action("candidate.verify"))])
async def delete_cover_letter(job_id: str, candidate_id: str):
    await _require_application(job_id, candidate_id)
    await db.applications.update_one({"job_id": job_id, "candidate_id": candidate_id},
                                     {"$unset": {"cover_letter": ""}})
    return {"status": "deleted"}
