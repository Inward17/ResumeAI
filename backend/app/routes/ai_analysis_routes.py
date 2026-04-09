import os
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import google.genai as genai

from app.database import db

router = APIRouter(prefix="/jobs/{job_id}/candidates/{candidate_id}", tags=["ai_analysis"])
logger = logging.getLogger(__name__)

class AIAnalysisResponse(BaseModel):
    recommendation: str
    reasoning: str
    generated_at: str

async def _generate_analysis(job_doc: dict, candidate_doc: dict, application_doc: dict, verification_doc: dict) -> Dict[str, Any]:
    """Gather all context and prompt Gemini to produce a professional 
    Markdown-formatted candidate assessment."""
    
    job_title = job_doc.get("job_title", "Unknown Role")
    required = job_doc.get("required_skills", [])
    preferred = job_doc.get("preferred_skills", [])
    
    parsed = candidate_doc.get("parsed", {})
    name = parsed.get("personal_info", {}).get("full_name", "Candidate")
    
    score_details = application_doc.get("score_details", {})
    overall_score = score_details.get("overall_score", 0)
    jd_match_score = score_details.get("jd_match_score", 0)
    
    v_status = verification_doc.get("verificationStatus", {}) if verification_doc else {}
    github_score = 0
    if verification_doc and verification_doc.get("githubData"):
        github_score = verification_doc["githubData"].get("score", 0)

    prompt = f"""
You are an expert technical recruiter AI and verification engine evaluating a candidate for a job.
You must synthesize the parsed resume data, verification results, and algorithmic scores to produce a final, highly-reliable readout for the hiring team.

## Candidate Information
Name: {name}
Job Applied For: {job_title}

## Job Requirements
Required Skills: {', '.join(required) if required else 'None given'}
Preferred Skills: {', '.join(preferred) if preferred else 'None given'}

## Algorithmic Scores
Unified JD Match Score (0-10): {jd_match_score}
Verification Credibility Score (0-100%): {overall_score}%
GitHub Technical Reality Score (0-100%): {github_score}%

## External Verification Status
GitHub: {v_status.get('github', 'Pending/Unknown')}
LinkedIn: {v_status.get('linkedin', 'Pending/Unknown')}
Web Background Check: {v_status.get('webCheck', 'Pending/Unknown')}

INSTRUCTIONS:
Write a comprehensive but concise evaluation of this candidate. Use Markdown formatting (bullet points, bold headings, short paragraphs).
Structure the output exactly as follows:
1. **Executive Summary**: A 2-sentence summary of the candidate's fit. Include a formal recommendation category at the start of the summary: [Strongly Recommended | Recommended | Needs Review | Not Recommended].
2. **Skill Alignment**: How well they match the Required vs Preferred skills.
3. **Verification Footprint**: What the GitHub/LinkedIn verification tells us about the *reality* of their resume claims.
4. **Red Flags & Strengths**: Any missing data or outstanding qualities.

Do NOT include pleasantries, greetings, or conversational filler. Output the raw markdown directly.
    """
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)
        
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt.strip(),
        )
        
        text = response.text.strip()
        
        # Simple extraction for the recommendation category
        recommendation = "Needs Review"
        first_line = text.split("\\n")[0].upper()
        if "STRONGLY RECOMMENDED" in first_line:
            recommendation = "Strongly Recommended"
        elif "NOT RECOMMENDED" in first_line:
            recommendation = "Not Recommended"
        elif "RECOMMENDED" in first_line:
            recommendation = "Recommended"
            
        return {
            "recommendation": recommendation,
            "reasoning": text,
            "generated_at": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to generate AI analysis: {e}")
        return {
            "recommendation": "Error Generating Analysis",
            "reasoning": f"An error occurred while calling the AI: {e}",
            "generated_at": datetime.utcnow()
        }


@router.get("/analysis", response_model=AIAnalysisResponse)
async def get_candidate_analysis(job_id: str, candidate_id: str):
    """
    Fetch the AI Reasoning for a specific candidate applying to a job.
    Uses caching to avoid redundant LLM calls unless the verification data is fresher than the cache.
    """
    
    # 1. Fetch necessary docs
    application = await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
        
    job = await db.jobs.find_one({"_id": job_id})
    # Fix for ObjectId wrapper if needed:
    if not job:
        from bson import ObjectId
        try:
            job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        except:
            pass
            
    candidate = await db.candidates.find_one({
        "$or": [{"candidate_id": candidate_id}, {"candidateId": candidate_id}]
    })
    
    # Fetch Verification (handle both collections if dual-run shadow mode is active)
    import os
    dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
    col_name = "verification_data_agent" if dual_run else "verification_data"
    
    verification = await db[col_name].find_one({
        "$or": [{"candidate_id": candidate_id}, {"candidateId": candidate_id}]
    })
    
    if not job or not candidate:
        raise HTTPException(status_code=400, detail="Incomplete data for analysis generation")

    # 2. Check Cache
    ai_analysis = application.get("ai_analysis")
    
    # Determine the timestamp of the latest verification update
    latest_verification_time = datetime.min
    if verification:
        # Check standard fields across pipelines
        for key in ["githubData", "linkedinData", "webSearchData"]:
            data = verification.get(key, {})
            last_v = data.get("last_verified") or data.get("verifiedAt")
            if last_v:
                if isinstance(last_v, str):
                    try:
                        last_v = datetime.fromisoformat(last_v)
                    except:
                        continue
                if last_v > latest_verification_time:
                    latest_verification_time = last_v
                    
    # Is Cache Valid?
    if ai_analysis and "generated_at" in ai_analysis:
        cached_time = ai_analysis["generated_at"]
        if isinstance(cached_time, str):
            cached_time = datetime.fromisoformat(cached_time)
            
        if latest_verification_time <= cached_time:
            # Cache Hit, send it back immediately!
            logger.info(f"AI Analysis Cache HIT for candidate {candidate_id}")
            return AIAnalysisResponse(
                recommendation=ai_analysis.get("recommendation", "Needs Review"),
                reasoning=ai_analysis.get("reasoning", ""),
                generated_at=cached_time.isoformat()
            )
            
    # 3. Cache Miss / Stale -> Generate Fresh
    logger.info(f"AI Analysis Cache MISS or STALE for candidate {candidate_id}. Generating fresh reasoning.")
    fresh_analysis = await _generate_analysis(job, candidate, application, verification)
    
    # 4. Save to DB and Return
    await db.applications.update_one(
        {"_id": application["_id"]},
        {"$set": {"ai_analysis": fresh_analysis}}
    )
    
    # Convert datetime to string for response
    fresh_analysis["generated_at"] = fresh_analysis["generated_at"].isoformat()
    return fresh_analysis
