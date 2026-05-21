"""
Metrics service.

Stores a DB-backed `metrics` document per candidate/job application using:
- real stored data from `candidates`, `applications`, `jobs`, `verification_data`
- real pipeline functions when recomputation is required

This service never fabricates missing values. If an exact metric is not
available in persisted historical data, it stores `None` plus a status note.
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from app.database import db
from app.services.skill_matching.pipeline import run_unified_skill_scoring
from app.services.github_services_v2.scoring.signal_fusion import _redistribute_weights


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    values = [float(v) for v in values if v is not None]
    return round(mean(values), 4) if values else None


def _safe_max(values: Iterable[float]) -> Optional[float]:
    values = [float(v) for v in values if v is not None]
    return round(max(values), 4) if values else None


def _flatten_github_v2(verification_doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not verification_doc:
        return {}
    github_data = verification_doc.get("githubData") or {}
    return github_data.get("github_v2_data") or {}


def _verification_query(candidate_id: str) -> Dict[str, Any]:
    return {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}


def _extract_skill_metrics_from_application(application_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    score_details = (application_doc or {}).get("score_details") or {}
    skill_matches = score_details.get("skill_matches") or []
    jd_match_score = score_details.get("jd_match_score")

    if not skill_matches or jd_match_score is None:
        return None

    evidenceful = [
        match for match in skill_matches
        if isinstance(match, dict) and isinstance(match.get("evidence"), dict) and match.get("evidence")
    ]
    if not evidenceful:
        return None

    per_skill_max_cosines = [
        max(float(v) for v in match["evidence"].values())
        for match in evidenceful
        if match["evidence"]
    ]
    all_cosines = [
        float(v)
        for match in evidenceful
        for v in match["evidence"].values()
    ]

    return {
        "source": "applications.score_details.skill_matches",
        "skill_count": len(skill_matches),
        "weighted_skill_score": round(float(jd_match_score), 4),
        "max_cosine_similarity": _safe_max(per_skill_max_cosines),
        "avg_cosine_similarity": _safe_mean(per_skill_max_cosines),
        "avg_all_section_cosine_similarity": _safe_mean(all_cosines),
        "skill_matches": skill_matches,
    }


async def _recompute_skill_metrics(
    parsed_resume: Dict[str, Any],
    job_doc: Optional[Dict[str, Any]],
    github_v2_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not parsed_resume or not job_doc:
        return None

    required_skills = list(job_doc.get("required_skills") or [])
    preferred_skills = list(job_doc.get("preferred_skills") or [])
    all_skills = [skill for skill in required_skills + preferred_skills if skill]
    if not all_skills:
        return None

    scoring_result = await run_unified_skill_scoring(
        required_skills=all_skills,
        parsed=parsed_resume,
        github_v2_data=github_v2_data,
    )

    skill_scores = scoring_result.get("skill_scores") or []
    if not skill_scores:
        return {
            "source": "recomputed_unified_skill_scoring",
            "skill_count": 0,
            "weighted_skill_score": round(float(scoring_result.get("jd_match_score", 0.0) or 0.0), 4),
            "max_cosine_similarity": None,
            "avg_cosine_similarity": None,
            "avg_all_section_cosine_similarity": None,
            "skill_matches": [],
        }

    per_skill_max_cosines = []
    all_cosines = []
    for match in skill_scores:
        evidence = match.get("evidence") or {}
        if evidence:
            per_skill_max_cosines.append(max(float(v) for v in evidence.values()))
            all_cosines.extend(float(v) for v in evidence.values())

    return {
        "source": "recomputed_unified_skill_scoring",
        "skill_count": len(skill_scores),
        "weighted_skill_score": round(float(scoring_result.get("jd_match_score", 0.0) or 0.0), 4),
        "max_cosine_similarity": _safe_max(per_skill_max_cosines),
        "avg_cosine_similarity": _safe_mean(per_skill_max_cosines),
        "avg_all_section_cosine_similarity": _safe_mean(all_cosines),
        "skill_matches": skill_scores,
    }


def _extract_dynamic_weight_metrics(github_v2_data: Dict[str, Any]) -> Dict[str, Any]:
    signals = github_v2_data.get("signals") or {}
    available = {
        key: value for key, value in signals.items()
        if value is not None
    }
    if not available:
        return {
            "source": "verification_data.githubData.github_v2_data.signals",
            "status": "unavailable",
            "available_signal_count": 0,
            "weights": {},
        }

    redistributed = _redistribute_weights(available)
    return {
        "source": "verification_data.githubData.github_v2_data.signals",
        "status": "available",
        "available_signal_count": len(available),
        "weights": {key: round(float(value), 4) for key, value in redistributed.items()},
    }


def _extract_clone_metrics(github_v2_data: Dict[str, Any]) -> Dict[str, Any]:
    clone_analysis = github_v2_data.get("cloneAnalysis") or {}
    repo_details = clone_analysis.get("repoDetails") or []
    populated_repo_details = [detail for detail in repo_details if isinstance(detail, dict)]

    jaccard_values = [
        detail.get("structureJaccard")
        for detail in populated_repo_details
        if detail.get("structureJaccard") is not None
    ]
    top_k_values = [
        detail.get("topChunkMean")
        for detail in populated_repo_details
        if detail.get("topChunkMean") is not None
    ]

    return {
        "source": "verification_data.githubData.github_v2_data.cloneAnalysis",
        "code_similarity_max": clone_analysis.get("codeSimilarityMax"),
        "readme_similarity_max": clone_analysis.get("readmeSimilarityMax"),
        "jaccard_status": "available" if jaccard_values else "missing_not_persisted",
        "top_k_mean_status": "available" if top_k_values else "missing_not_persisted",
        "max_jaccard_similarity": _safe_max(jaccard_values),
        "avg_jaccard_similarity": _safe_mean(jaccard_values),
        "max_top_k_mean": _safe_max(top_k_values),
        "avg_top_k_mean": _safe_mean(top_k_values),
        "repo_count": len(populated_repo_details),
    }


def _build_metrics_doc(
    candidate_doc: Dict[str, Any],
    application_doc: Optional[Dict[str, Any]],
    job_doc: Optional[Dict[str, Any]],
    verification_doc: Optional[Dict[str, Any]],
    skill_metrics: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    parsed = candidate_doc.get("parsed") or {}
    personal_info = parsed.get("personal_info") or {}
    github_v2_data = _flatten_github_v2(verification_doc)
    dynamic_weights = _extract_dynamic_weight_metrics(github_v2_data)
    clone_metrics = _extract_clone_metrics(github_v2_data)

    required_skills = list((job_doc or {}).get("required_skills") or [])
    preferred_skills = list((job_doc or {}).get("preferred_skills") or [])
    score_details = (application_doc or {}).get("score_details") or {}

    metrics_key = f"{candidate_doc.get('candidate_id')}::{(application_doc or {}).get('job_id') or 'no-job'}"

    return {
        "metrics_key": metrics_key,
        "candidate_id": candidate_doc.get("candidate_id"),
        "job_id": (application_doc or {}).get("job_id"),
        "filename": candidate_doc.get("filename"),
        "full_name": personal_info.get("full_name"),
        "email": personal_info.get("email"),
        "github_username": candidate_doc.get("github_username"),
        "job_required_skills_count": len(required_skills),
        "job_preferred_skills_count": len(preferred_skills),
        "score_source": score_details.get("score_source"),
        "skill_metrics": skill_metrics or {
            "source": "unavailable",
            "skill_count": 0,
            "weighted_skill_score": None,
            "max_cosine_similarity": None,
            "avg_cosine_similarity": None,
            "avg_all_section_cosine_similarity": None,
            "skill_matches": [],
        },
        "dynamic_weight_metrics": dynamic_weights,
        "clone_metrics": clone_metrics,
        "sources": {
            "candidate": "candidates.parsed",
            "application": "applications.score_details" if application_doc else "unavailable",
            "verification": "verification_data.githubData.github_v2_data" if github_v2_data else "unavailable",
            "job": "jobs" if job_doc else "unavailable",
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def upsert_metrics_for_application(
    candidate_id: str,
    job_id: str,
    *,
    candidate_doc: Optional[Dict[str, Any]] = None,
    application_doc: Optional[Dict[str, Any]] = None,
    job_doc: Optional[Dict[str, Any]] = None,
    verification_doc: Optional[Dict[str, Any]] = None,
    db_client=None,
) -> Optional[Dict[str, Any]]:
    dbh = db if db_client is None else db_client

    candidate_doc = candidate_doc or await dbh.candidates.find_one({"candidate_id": candidate_id})
    if not candidate_doc:
        return None

    application_doc = application_doc or await dbh.applications.find_one(
        {"candidate_id": candidate_id, "job_id": job_id}
    )
    if not application_doc:
        return None

    verification_doc = verification_doc or await dbh.verification_data.find_one(
        _verification_query(candidate_id)
    )
    if verification_doc is None:
        verification_doc = await dbh.verification_data_agent.find_one(
            _verification_query(candidate_id)
        )

    if job_doc is None:
        from bson import ObjectId
        try:
            job_doc = await dbh.jobs.find_one({"_id": ObjectId(job_id)})
        except Exception:
            job_doc = await dbh.jobs.find_one({"$or": [{"jobId": job_id}, {"job_id": job_id}]})

    skill_metrics = _extract_skill_metrics_from_application(application_doc)
    if skill_metrics is None:
        skill_metrics = await _recompute_skill_metrics(
            candidate_doc.get("parsed") or {},
            job_doc,
            _flatten_github_v2(verification_doc),
        )

    metrics_doc = _build_metrics_doc(
        candidate_doc=candidate_doc,
        application_doc=application_doc,
        job_doc=job_doc,
        verification_doc=verification_doc,
        skill_metrics=skill_metrics,
    )
    update_payload = dict(metrics_doc)
    update_payload.pop("created_at", None)

    await dbh.metrics.update_one(
        {"metrics_key": metrics_doc["metrics_key"]},
        {
            "$set": {
                **update_payload,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    return metrics_doc
