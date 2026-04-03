"""
Context Builder — Section 6.3

Reads MongoDB and assembles a structured AgentContext.
This is the only place in the agent layer that touches the database directly.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from app.database import db
from app.models.agent_models import SignalFreshness, AgentContext

# ── Freshness thresholds (Section 5.2) ──────────────────────────────────
FRESHNESS_THRESHOLDS = {
    "github":     timedelta(days=7),
    "linkedin":   timedelta(days=14),
    "web_search": timedelta(days=30),
}

# MongoDB signal‑data key mapping
_SIGNAL_KEY_MAP = {
    "github":     "githubData",
    "linkedin":   "linkedinData",
    "web_search": "webSearchData",
}

# Legacy VerificationDataModel stores verification timestamps in nested objects.
# Map signal → field that holds a verifiedAt / last_verified timestamp.
_TIMESTAMP_FIELD = {
    "github":     "verifiedAt",
    "linkedin":   "verifiedAt",
    "web_search": "verifiedAt",
}
# Legacy schema exposes confidence as a computed score100 / overallCredibility,
# not as a flat confidence_score field.  We default confidence to 0.0 unless
# a flat confidence_score key is present (agent-written docs).
_CONFIDENCE_FIELD = "confidence_score"


# ── Freshness computation ───────────────────────────────────────────────
def compute_freshness(verification_doc: Optional[dict]) -> List[SignalFreshness]:
    """
    For each verification signal, determine whether its data is
    still considered 'fresh' based on the last_verified timestamp
    and the configured thresholds.
    """
    doc = verification_doc or {}
    results: List[SignalFreshness] = []

    for signal, data_key in _SIGNAL_KEY_MAP.items():
        data = doc.get(data_key, {}) or {}
        # Support both legacy (verifiedAt) and agent-written (last_verified) timestamps
        last = data.get("last_verified") or data.get(_TIMESTAMP_FIELD[signal])
        is_fresh = False

        if last:
            # Handle both datetime objects and ISO strings from Mongo
            if isinstance(last, str):
                last = datetime.fromisoformat(last)
            age = datetime.utcnow() - last
            is_fresh = age < FRESHNESS_THRESHOLDS[signal]

        # Support both agent-written flat key and legacy nested structure
        confidence = data.get(_CONFIDENCE_FIELD, 0.0)
        # If not present, legacy docs may carry score/score100 (github) or
        # average_score (web search) — normalise to 0–1 range
        if not confidence:
            raw = data.get("score100") or data.get("score") or 0
            confidence = round(min(raw / 100.0, 1.0), 4) if raw else 0.0

        results.append(SignalFreshness(
            signal        = signal,
            last_verified = last,
            is_fresh      = is_fresh,
            confidence    = confidence,
        ))

    return results


# ── Public API ──────────────────────────────────────────────────────────
async def build(candidate_id: str, job_id: str, memory) -> AgentContext:
    """
    Build the full AgentContext by reading from the existing
    MongoDB collections.  `memory` is a SessionMemory instance
    that provides the action history for this request.
    """
    import os
    from bson import ObjectId

    dual_run = os.environ.get("DUAL_RUN", "false").lower() == "true"
    # Agent mode: use the isolated shadow collection when dual-run is active
    verif_collection = "verification_data_agent" if dual_run else "verification_data"

    # Legacy service stores docs with "candidateId" (camelCase);
    # agent-written docs use "candidate_id" (snake_case).
    verification_doc = await db[verif_collection].find_one(
        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
    )

    # Fast lookup attempts for candidate (camelCase and snake_case support)
    candidate_doc = await db.candidates.find_one(
        {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
    )
    
    # Fallback: if candidate not found, it's very likely candidate_id is actually a task_id
    # from the frontend upload loop which was resolved via name/phone deduplication.
    if not candidate_doc:
        task_doc = await db.tasks.find_one({"task_id": candidate_id})
        if task_doc and task_doc.get("resolved_candidate_id"):
            real_candidate_id = task_doc["resolved_candidate_id"]
            candidate_id = real_candidate_id  # Swap reference globally for this agent execution
            candidate_doc = await db.candidates.find_one(
                {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
            )
            # Re-fetch verification doc with the REAL candidate ID
            verification_doc = await db[verif_collection].find_one(
                {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}
            )

    # Fix job ObjectId lookup — _id in MongoDB is an ObjectId, not a plain string
    job_doc = None
    try:
        job_doc = await db.jobs.find_one({"_id": ObjectId(job_id)})
    except Exception:
        pass
    if not job_doc:
        job_doc = await db.jobs.find_one({"$or": [{"jobId": job_id}, {"job_id": job_id}]})

    evaluation_doc = await db.evaluations.find_one(
        {"candidate_id": candidate_id, "job_id": job_id}
    )
    application_doc = await db.applications.find_one(
        {"candidate_id": candidate_id, "job_id": job_id}
    )

    freshness = compute_freshness(verification_doc)

    # CRITICAL: When no verification doc exists yet (first run), use the parsed resume
    # data as verification_data so the agent tools can extract GitHub/LinkedIn URLs.
    # The tools read personal_info.github, personal_info.linkedin, education, experience
    # directly from verification_data — which is just the candidate's parsed resume.
    if not verification_doc and candidate_doc:
        parsed = candidate_doc.get("parsed", {})
        # Build a synthetic verification_data shaped like what agent tools expect
        verification_doc = {
            "candidate_id": candidate_id,
            "personal_info": parsed.get("personal_info", {}),
            "education": parsed.get("education", []),
            "experience": parsed.get("experience", []),
            "skills": parsed.get("skills"),
            "projects": parsed.get("projects", []),
            # Include candidate-level URLs so rule_engine and tools can find them
            "github_username": candidate_doc.get("github_username"),
            "linkedin_url": candidate_doc.get("linkedin_url"),
        }
    elif verification_doc and candidate_doc:
        # Existing doc may be missing personal_info/URLs (agent only writes
        # githubData/linkedinData/webSearchData).  Merge from candidate so
        # tools can find GitHub/LinkedIn URLs for re-verification.
        parsed = candidate_doc.get("parsed", {})
        if "personal_info" not in verification_doc:
            verification_doc["personal_info"] = parsed.get("personal_info", {})
        if "education" not in verification_doc:
            verification_doc["education"] = parsed.get("education", [])
        if "experience" not in verification_doc:
            verification_doc["experience"] = parsed.get("experience", [])
        if "projects" not in verification_doc:
            verification_doc["projects"] = parsed.get("projects", [])
        if "github_username" not in verification_doc:
            verification_doc["github_username"] = candidate_doc.get("github_username")
        if "linkedin_url" not in verification_doc:
            verification_doc["linkedin_url"] = candidate_doc.get("linkedin_url")

    return AgentContext(
        candidate_id      = candidate_id,
        job_id            = job_id,
        verification_data = verification_doc or {},
        freshness         = freshness,
        job               = job_doc or {},
        evaluation        = evaluation_doc or {},
        history           = memory.action_history,
    )
