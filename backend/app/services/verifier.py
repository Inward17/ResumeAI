import re
import asyncio
from rapidfuzz import fuzz
from app.services.search import search_web


def extract_entities(profile: dict) -> dict:
    """Extract education and experience from LinkedIn profile"""
    educations = []
    experiences = []
    
    for edu in profile.get("educations", []):
        college = edu.get("title") or edu.get("subtitle")
        if college:
            educations.append({"college": college})
    
    for exp in profile.get("experiences", []):
        company = exp.get("subtitle") or exp.get("companyName")
        position = exp.get("title") or "Unknown"
        if company:
            experiences.append({"company": company, "position": position})
    
    return {"educations": educations, "experiences": experiences}


async def verify_profile(profile: dict) -> dict:
    """Verify LinkedIn profile data"""
    entities = extract_entities(profile)
    
    # Verify education
    edu_tasks = [search_web(e["college"], "education") for e in entities["educations"]]
    edu_results = await asyncio.gather(*edu_tasks) if edu_tasks else []
    
    # Verify experience
    exp_tasks = [search_web(e["company"], "experience") for e in entities["experiences"]]
    exp_results = await asyncio.gather(*exp_tasks) if exp_tasks else []
    
    # Combine results
    verified_edu = [{**entities["educations"][i], **edu_results[i]} for i in range(len(edu_results))]
    verified_exp = [{**entities["experiences"][i], **exp_results[i]} for i in range(len(exp_results))]
    
    # Score results
    edu_score = compute_score(verified_edu, "education")
    exp_score = compute_score(verified_exp, "experience")
    
    return {
        "profile_url": profile.get("publicIdentifier", "N/A"),
        "education": edu_score,
        "experience": exp_score
    }


def compute_score(entries: list, field_type: str) -> dict:
    """Compute verification score"""
    if not entries:
        return {"details": [], "average_score": 0, "overall_tag": "Not Found"}
    
    scored = []
    total = 0
    
    for entry in entries:
        verified = entry.get("verified", False)
        snippet = entry.get("snippet", "") or ""
        title = entry.get("title", "") or ""
        combined = f"{title} {snippet}".lower()
        
        score = 0
        if verified and entry.get("top_result"):
            if field_type == "education":
                college = entry.get("college", "").lower()
                similarity = fuzz.token_set_ratio(college, combined)
                score = 100 if similarity >= 90 else (50 if similarity >= 70 else 0)
            
            elif field_type == "experience":
                company = re.sub(r'\s*·.*$', '', entry.get("company", "")).lower()
                sim = fuzz.token_set_ratio(company, combined)
                if sim >= 70:
                    score = 50
                    position = entry.get("position", "").lower()
                    if position in combined:
                        score = 100
        
        tag = "Verified" if score >= 75 else ("Mismatch" if score > 25 else "Not Found")
        total += score
        scored.append({**entry, "score": score, "tag": tag})
    
    avg = round(total / len(scored), 2)
    overall = "Verified" if avg >= 75 else ("Mismatch" if avg > 25 else "Not Found")
    
    return {"details": scored, "average_score": avg, "overall_tag": overall}