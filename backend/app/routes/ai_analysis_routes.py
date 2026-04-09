"""
AI Analysis Routes - Generate AI-powered candidate analysis using Gemini
Uses exactly 1 Gemini API call per candidate, then caches the result.
"""
import json
import os
from fastapi import APIRouter, HTTPException
from app.database import db
from bson import ObjectId

router = APIRouter(prefix="/jobs", tags=["ai-analysis"])


async def _call_gemini(prompt: str) -> dict | None:
    """Call Gemini API via REST (single call). Returns parsed JSON or None."""
    import httpx

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, params={"key": api_key})

        if resp.status_code != 200:
            print(f"[AI Analysis] Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        # Parse JSON response
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned.strip())

    except Exception as e:
        print(f"[AI Analysis] Gemini call failed: {e}")
        return None


def _build_prompt(candidate: dict, job: dict, scores: dict) -> str:
    """Build a minimal prompt to save tokens."""
    parsed = candidate.get("parsed", {})
    personal_info = parsed.get("personal_info", {})
    name = personal_info.get("full_name", "Unknown")
    skills = parsed.get("skills", "")
    if isinstance(skills, list):
        skills = ", ".join(skills[:10])
    elif skills:
        skills = skills[:200]

    job_title = job.get("job_title", "N/A")
    required_skills = ", ".join(job.get("required_skills", [])[:8])
    overall_score = scores.get("overall_score", 0)
    skills_score = scores.get("skills_match_score", 0)

    return f"""Candidate: {name}
Skills: {skills}
Job: {job_title} (requires: {required_skills})
Scores: overall={overall_score}%, skills={skills_score}%

Return JSON: {{"recommendation":"Strongly Recommended"|"Recommended"|"Not Recommended","reasoning":"<2 sentence summary of fit>","strengths":["<1>","<2>"],"concerns":["<1>"]}}"""


@router.get("/{job_id}/candidates/{candidate_id}/analysis")
async def get_candidate_analysis(job_id: str, candidate_id: str):
    """
    Get AI-generated analysis for a candidate. 
    Uses exactly 1 Gemini API call, then caches the result in the applications collection.
    """
    # Check cache first — return immediately if analysis already exists
    application = await db.applications.find_one({
        "job_id": job_id,
        "candidate_id": candidate_id
    })

    if not application:
        raise HTTPException(404, "Application not found")

    # Return cached analysis if available
    cached = application.get("ai_analysis")
    if cached:
        return {"status": "success", "analysis": cached, "cached": True}

    # Fetch candidate and job data only (no verification queries)
    candidate = await db.candidates.find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    try:
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        raise HTTPException(400, "Invalid job ID")
    if not job:
        raise HTTPException(404, "Job not found")

    scores = application.get("score_details", {})

    # Build prompt and call Gemini (single API call)
    prompt = _build_prompt(candidate, job, scores)
    print(f"[AI Analysis] Generating analysis for {candidate_id}...")
    result = await _call_gemini(prompt)

    if result:
        # Cache the result so we never call Gemini again for this candidate+job
        await db.applications.update_one(
            {"job_id": job_id, "candidate_id": candidate_id},
            {"$set": {"ai_analysis": result}}
        )
        print(f"[AI Analysis] ✅ Analysis generated and cached for {candidate_id}")
        return {"status": "success", "analysis": result, "cached": False}
    else:
        # Gemini failed — return a fallback
        fallback = {
            "recommendation": "Recommended" if scores.get("overall_score", 0) >= 60 else "Not Recommended",
            "reasoning": "AI analysis is currently unavailable. Please review the verification scores and skill matches manually.",
            "strengths": [],
            "concerns": ["AI analysis could not be generated at this time"]
        }
        return {"status": "fallback", "analysis": fallback, "cached": False}
