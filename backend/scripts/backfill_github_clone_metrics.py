#!/usr/bin/env python3
"""
One-time GitHub clone-metrics backfill.

Purpose:
- Re-run the real GitHub verification pipeline for historical candidates
- Persist refreshed githubData.github_v2_data into verification_data
- Refresh metrics for every affected application

This exists because older verification_data records did not persist the
intermediate clone metrics now exported by the system:
  - structureJaccard
  - topChunkMean
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.github_services_v2 import verify_github  # noqa: E402
from app.services.metrics_service import upsert_metrics_for_application  # noqa: E402


load_dotenv(BACKEND_DIR / ".env")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resume_validator")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute exact GitHub clone metrics for historical candidates."
    )
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="Limit the backfill to one or more candidate IDs.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-run GitHub verification for all candidates with GitHub usernames, not just missing historical clone metrics.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of candidates to process in this run.",
    )
    return parser.parse_args()


def verification_query(candidate_id: str) -> Dict[str, Any]:
    return {"$or": [{"candidateId": candidate_id}, {"candidate_id": candidate_id}]}


def metrics_key(candidate_id: str, job_id: str) -> str:
    return f"{candidate_id}::{job_id}"


def github_username_from_candidate(candidate_doc: Dict[str, Any]) -> Optional[str]:
    username = candidate_doc.get("github_username")
    if username:
        return str(username).strip()

    parsed = candidate_doc.get("parsed") or {}
    personal = parsed.get("personal_info") or {}
    github_value = str(personal.get("github") or "").strip()
    if not github_value:
        return None
    if "github.com" in github_value:
        return github_value.rstrip("/").split("/")[-1]
    return github_value


def parsed_resume_for_github(candidate_doc: Dict[str, Any]) -> Dict[str, Any]:
    parsed = dict(candidate_doc.get("parsed") or {})
    personal = dict(parsed.get("personal_info") or {})
    github_username = github_username_from_candidate(candidate_doc)
    if github_username and not personal.get("github"):
        personal["github"] = f"github.com/{github_username}"
    parsed["personal_info"] = personal
    if github_username:
        parsed["github_username"] = github_username
    return parsed


def build_github_data_payload(result) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "username": result.username,
        "success": bool(result.success),
        "score": result.score100,
        "score100": result.score100,
        "score40": result.score40,
        "confidenceLevel": result.confidenceLevel,
        "redFlags": result.redFlags or [],
        "verifiedAt": now,
        "github_v2_data": result.to_mongo_dict(),
    }


async def candidate_needs_backfill(
    db,
    candidate_id: str,
    *,
    force_all: bool,
) -> bool:
    if force_all:
        return True

    applications = await db.applications.find({"candidate_id": candidate_id}, {"job_id": 1}).to_list(length=100)
    if not applications:
        return False

    for application in applications:
        job_id = application.get("job_id")
        if not job_id:
            continue
        metric = await db.metrics.find_one(
            {"metrics_key": metrics_key(candidate_id, job_id)},
            {
                "_id": 0,
                "clone_metrics.jaccard_status": 1,
                "clone_metrics.top_k_mean_status": 1,
            },
        )
        if not metric:
            return True
        clone_metrics = metric.get("clone_metrics") or {}
        if clone_metrics.get("jaccard_status") == "missing_not_persisted":
            return True
        if clone_metrics.get("top_k_mean_status") == "missing_not_persisted":
            return True

    return False


async def refresh_candidate_github_metrics(db, candidate_doc: Dict[str, Any]) -> Dict[str, Any]:
    candidate_id = candidate_doc["candidate_id"]
    github_username = github_username_from_candidate(candidate_doc)
    if not github_username:
        return {"candidate_id": candidate_id, "status": "skipped", "reason": "missing_github_username"}

    parsed_resume = parsed_resume_for_github(candidate_doc)
    result = await verify_github(candidate_id=candidate_id, parsed_resume=parsed_resume)

    if not result.success:
        return {
            "candidate_id": candidate_id,
            "status": "failed",
            "reason": result.error or "github_verification_failed",
        }

    github_data_payload = build_github_data_payload(result)

    await db.verification_data.update_one(
        {"candidateId": candidate_id},
        {
            "$set": {
                "candidateId": candidate_id,
                "updatedAt": datetime.utcnow(),
                "githubData": github_data_payload,
                "verificationStatus.github": "verified",
            },
            "$setOnInsert": {
                "createdAt": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    applications = await db.applications.find({"candidate_id": candidate_id}, {"job_id": 1}).to_list(length=100)
    refreshed_jobs = 0
    for application in applications:
        job_id = application.get("job_id")
        if not job_id:
            continue
        await upsert_metrics_for_application(
            candidate_id=candidate_id,
            job_id=job_id,
            candidate_doc=candidate_doc,
            verification_doc=None,
            db_client=db,
        )
        refreshed_jobs += 1

    return {
        "candidate_id": candidate_id,
        "status": "updated",
        "github_username": github_username,
        "refreshed_jobs": refreshed_jobs,
        "score100": result.score100,
    }


async def gather_candidate_ids(db, args: argparse.Namespace) -> List[str]:
    if args.candidate_id:
        seen: Set[str] = set()
        ordered: List[str] = []
        for candidate_id in args.candidate_id:
            if candidate_id and candidate_id not in seen:
                seen.add(candidate_id)
                ordered.append(candidate_id)
        return ordered

    candidates = await db.candidates.find(
        {},
        {
            "_id": 0,
            "candidate_id": 1,
            "github_username": 1,
            "parsed.personal_info.github": 1,
        },
    ).to_list(length=None)

    candidate_ids: List[str] = []
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue
        if not (candidate.get("github_username") or ((candidate.get("parsed") or {}).get("personal_info") or {}).get("github")):
            continue
        if await candidate_needs_backfill(db, candidate_id, force_all=args.all):
            candidate_ids.append(candidate_id)
        if args.limit and len(candidate_ids) >= args.limit:
            break

    return candidate_ids


async def async_main() -> int:
    args = parse_args()
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]

    try:
        await db.command("ping")
    except Exception as exc:
        print(f"Failed to connect to MongoDB at {MONGO_URL}: {exc}", file=sys.stderr)
        client.close()
        return 1

    try:
        candidate_ids = await gather_candidate_ids(db, args)
        if not candidate_ids:
            print("No candidates require GitHub clone-metrics backfill.")
            return 0

        processed = 0
        updated = 0
        skipped = 0
        failed = 0

        for candidate_id in candidate_ids:
            candidate_doc = await db.candidates.find_one({"candidate_id": candidate_id})
            if not candidate_doc:
                print(f"[SKIP] {candidate_id}: candidate document not found")
                skipped += 1
                continue

            outcome = await refresh_candidate_github_metrics(db, candidate_doc)
            processed += 1

            status = outcome["status"]
            if status == "updated":
                updated += 1
                print(
                    f"[UPDATED] {outcome['candidate_id']} "
                    f"github={outcome.get('github_username')} "
                    f"jobs={outcome.get('refreshed_jobs', 0)} "
                    f"score100={outcome.get('score100')}"
                )
            elif status == "skipped":
                skipped += 1
                print(f"[SKIP] {outcome['candidate_id']}: {outcome.get('reason')}")
            else:
                failed += 1
                print(f"[FAILED] {outcome['candidate_id']}: {outcome.get('reason')}")

        print(
            f"Backfill finished. processed={processed} updated={updated} "
            f"skipped={skipped} failed={failed}"
        )
        return 0 if failed == 0 else 1
    finally:
        client.close()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
