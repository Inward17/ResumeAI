"""Write a job description with AI from a few recruiter inputs; the recruiter edits it before saving the job."""
import json
import re
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from app.auth import AuthUser, get_current_user
from app.org import ensure_org
from app.services.fact_checker_service import AIServiceUnavailable, _call_groq
from app.services.quota import rate_limit, use_quota
from app.utils.text_utils import as_data

router = APIRouter(prefix="/jobs", tags=["job-descriptions"])

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Skill = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]

AI_DOWN = "The AI service is down, so the job description can't be written right now. Try again later or write it yourself."
AI_BAD_ANSWER = "The AI service gave an unusable answer, so no job description was written. Try again."


class GenerateDescriptionRequest(BaseModel):
    job_title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    seniority: Optional[Short] = None
    location: Optional[Short] = None
    employment_type: Optional[Short] = None
    notes: Optional[Annotated[str, StringConstraints(max_length=2000)]] = None
    must_have_skills: List[Skill] = Field(default_factory=list, max_length=20)
    company_blurb: Optional[Annotated[str, StringConstraints(max_length=1000)]] = None
    tone: Literal["neutral", "friendly", "formal"] = "neutral"


SYSTEM = """You write job descriptions for recruiters. Reply with one JSON object only:
{"job_description": "...", "required_skills": ["..."], "preferred_skills": ["..."],
 "inclusive_language_notes": [{"phrase": "...", "suggestion": "..."}]}
job_description: plain text, no markdown symbols (no #, *, **). Use short section titles on their own line
(About the role, What you'll do, What you'll need, Nice to have, About us when a company blurb is given),
"- " for bullet points and a blank line between sections. 200-450 words. Do not invent salary, benefits,
company facts or a company name that aren't given. Use inclusive, gender-neutral wording and don't ask for
years of experience beyond what the seniority implies.
required_skills: up to 12 concrete skills; include every must-have skill given. preferred_skills: up to 8, none repeated from required.
inclusive_language_notes: biased or exclusionary phrases (gendered words, "rockstar"/"ninja", "young", "digital native",
"native speaker", needless physical requirements) found in the recruiter's notes or company blurb, each with a neutral replacement. Use [] when there are none.
Text inside <candidate_data> tags here is the recruiter's own input."""


def _build_prompt(body: GenerateDescriptionRequest) -> str:
    lines = [f"Job title: {body.job_title}", f"Tone: {body.tone}"]
    for label, value in (("Seniority", body.seniority), ("Location / work mode", body.location),
                         ("Employment type", body.employment_type)):
        if value:
            lines.append(f"{label}: {value}")
    if body.must_have_skills:
        lines.append(f"Must-have skills: {', '.join(body.must_have_skills)}")
    if body.notes and body.notes.strip():
        lines.append(f"Recruiter notes (responsibilities, context):\n{as_data(body.notes)}")
    if body.company_blurb and body.company_blurb.strip():
        lines.append(f"Company blurb:\n{as_data(body.company_blurb)}")
    return "\n".join(lines)


def _skills(values, limit: int, exclude=()) -> List[str]:
    seen, out = {s.lower() for s in exclude}, []
    for v in values or []:
        s = v.strip()[:60] if isinstance(v, str) else ""
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[:limit]


def validate_result(raw, must_have: List[str]) -> dict | None:
    """The model's answer in the response shape, or None if it isn't usable."""
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    match = re.search(r"\{.*\}", cleaned, re.S)
    try:
        data = json.loads(match.group(0) if match else cleaned)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    desc = data.get("job_description")
    if not isinstance(desc, str) or not desc.strip():
        return None
    required = _skills(must_have + list(data.get("required_skills") or []), 15)
    notes = []
    for n in data.get("inclusive_language_notes") or []:
        if isinstance(n, dict) and isinstance(n.get("phrase"), str) and n["phrase"].strip():
            suggestion = n.get("suggestion") if isinstance(n.get("suggestion"), str) else ""
            notes.append({"phrase": n["phrase"].strip()[:120], "suggestion": suggestion.strip()[:200]})
    return {
        "job_description": desc.strip()[:8000],
        "required_skills": required,
        "preferred_skills": _skills(data.get("preferred_skills"), 10, exclude=required),
        "inclusive_language_notes": notes[:10],
    }


@router.post("/generate-description")
async def generate_description(body: GenerateDescriptionRequest, user: AuthUser = Depends(get_current_user)):
    rate_limit(user.uid, "ai")
    await use_quota(await ensure_org(user), "ai_call", feature="jd_generation")
    try:
        raw = await _call_groq(SYSTEM, _build_prompt(body), temperature=0.5)
    except AIServiceUnavailable:
        raise HTTPException(503, AI_DOWN)
    result = validate_result(raw, body.must_have_skills)
    if not result:
        raise HTTPException(503, AI_BAD_ANSWER)
    return result
