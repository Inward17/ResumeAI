"""
JD Matching Service - Scores candidates against job requirements
Uses vector embeddings and cosine similarity for semantic matching

Scoring Scheme:
- Resume Skills Match: 0-2 marks
- GitHub Projects Match: 0-3 marks  
- Total: 0-5 marks
"""
from typing import Dict, Optional
from datetime import datetime
from bson import ObjectId

from app.database import db
from app.services.embedding_service import cosine_similarity


async def calculate_jd_match(
    candidate_id: str,
    job_id: str
) -> Dict:
    """
    Calculate JD match score for a candidate against a job.
    
    Args:
        candidate_id: Unique candidate identifier
        job_id: Job posting ID
        
    Returns:
        Dict with resume_match (0-2), github_match (0-3), total (0-5), and details
    """
    result = {
        "resume_match": 0.0,
        "github_match": 0.0,
        "total": 0.0,
        "details": {
            "resume_cosine_similarity": 0.0,
            "github_cosine_similarity": 0.0,
            "has_resume_embedding": False,
            "has_github_embedding": False,
            "has_jd_embedding": False
        }
    }
    
    try:
        # Get job embedding
        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return result
            
        jd_embedding = job.get("jd_embedding")
        if not jd_embedding:
            return result
        result["details"]["has_jd_embedding"] = True
        
        # Get candidate skills embedding
        candidate = await db.candidates.find_one({"candidate_id": candidate_id})
        skills_embedding = candidate.get("skills_embedding") if candidate else None
        
        # Get GitHub projects embedding from verification data
        verification = await db.verification_data.find_one({"candidateId": candidate_id})
        github_embedding = None
        if verification and verification.get("githubData"):
            github_embedding = verification["githubData"].get("projects_embedding")
        
        # Calculate resume match (0-2 marks)
        if skills_embedding and any(v != 0 for v in skills_embedding):
            result["details"]["has_resume_embedding"] = True
            resume_similarity = cosine_similarity(skills_embedding, jd_embedding)
            result["details"]["resume_cosine_similarity"] = round(resume_similarity, 4)
            result["resume_match"] = round(resume_similarity * 2, 2)  # Scale to 0-2
        
        # Calculate GitHub match (0-3 marks)
        if github_embedding and any(v != 0 for v in github_embedding):
            result["details"]["has_github_embedding"] = True
            github_similarity = cosine_similarity(github_embedding, jd_embedding)
            result["details"]["github_cosine_similarity"] = round(github_similarity, 4)
            result["github_match"] = round(github_similarity * 3, 2)  # Scale to 0-3
        
        # Total score
        result["total"] = round(result["resume_match"] + result["github_match"], 2)
        
    except Exception as e:
        print(f"Error calculating JD match for candidate {candidate_id}: {e}")
    
    return result


async def save_evaluation(
    candidate_id: str,
    job_id: str,
    jd_match: Dict
) -> Optional[str]:
    """
    Save JD match evaluation to the evaluations collection.
    
    Args:
        candidate_id: Candidate ID
        job_id: Job ID
        jd_match: Match scores from calculate_jd_match
        
    Returns:
        Inserted evaluation ID or None on error
    """
    try:
        evaluation_doc = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "evaluation_type": "jd_match",
            "scores": {
                "resume_match": jd_match["resume_match"],
                "github_match": jd_match["github_match"],
                "total_jd_score": jd_match["total"]
            },
            "similarity_details": jd_match["details"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Upsert - update if exists, insert if not
        result = await db.evaluations.update_one(
            {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "evaluation_type": "jd_match"
            },
            {"$set": evaluation_doc},
            upsert=True
        )
        
        return str(result.upserted_id) if result.upserted_id else "updated"
        
    except Exception as e:
        print(f"Error saving evaluation for candidate {candidate_id}: {e}")
        return None


async def get_evaluation(candidate_id: str, job_id: str) -> Optional[Dict]:
    """
    Get JD match evaluation for a candidate-job pair.
    
    Args:
        candidate_id: Candidate ID
        job_id: Job ID
        
    Returns:
        Evaluation document or None
    """
    try:
        return await db.evaluations.find_one({
            "candidate_id": candidate_id,
            "job_id": job_id,
            "evaluation_type": "jd_match"
        })
    except Exception as e:
        print(f"Error getting evaluation: {e}")
        return None
