#!/usr/bin/env python3
"""
DB-backed metrics backfill/export script.

What it does:
1. Reads real candidate/application/job/verification records from MongoDB
2. Upserts one document per candidate/job into the `metrics` collection
3. Appends new rows from `metrics` into a CSV export

Important:
- Uses real stored system data first
- Recomputes missing skill metrics via the actual skill scoring pipeline
- Does NOT invent unavailable historical GitHub clone sub-metrics
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.metrics_service import upsert_metrics_for_application  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "resume_validator")
CLIENT = None
DB = None


CSV_HEADERS = [
    "metrics_key",
    "candidate_id",
    "job_id",
    "full_name",
    "filename",
    "job_required_skills_count",
    "job_preferred_skills_count",
    "weighted_skill_score",
    "skill_metric_source",
    "skill_count",
    "max_cosine_similarity",
    "avg_cosine_similarity",
    "avg_all_section_cosine_similarity",
    "dynamic_weight_status",
    "available_signal_count",
    "weight_resume_consistency",
    "weight_repository_authenticity",
    "weight_readme_originality",
    "weight_code_originality",
    "weight_behavioral_authenticity",
    "weight_oss_contribution",
    "clone_code_similarity_max",
    "clone_readme_similarity_max",
    "jaccard_status",
    "max_jaccard_similarity",
    "avg_jaccard_similarity",
    "top_k_mean_status",
    "max_top_k_mean",
    "avg_top_k_mean",
    "updated_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill/export DB metrics.")
    parser.add_argument(
        "--output",
        default=str(BACKEND_DIR / "results" / "resume_metrics_export.csv"),
        help="CSV export path.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep polling MongoDB for new applications/metrics.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Polling interval in seconds when --watch is enabled.",
    )
    return parser.parse_args()


def ensure_output_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()


def load_existing_metric_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            row["metrics_key"]
            for row in reader
            if row.get("metrics_key")
        }


def flatten_metric_doc(doc: Dict) -> Dict[str, str]:
    skill = doc.get("skill_metrics") or {}
    dynamic = doc.get("dynamic_weight_metrics") or {}
    weights = dynamic.get("weights") or {}
    clone = doc.get("clone_metrics") or {}

    def fmt(value):
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value)

    return {
        "metrics_key": fmt(doc.get("metrics_key")),
        "candidate_id": fmt(doc.get("candidate_id")),
        "job_id": fmt(doc.get("job_id")),
        "full_name": fmt(doc.get("full_name")),
        "filename": fmt(doc.get("filename")),
        "job_required_skills_count": fmt(doc.get("job_required_skills_count")),
        "job_preferred_skills_count": fmt(doc.get("job_preferred_skills_count")),
        "weighted_skill_score": fmt(skill.get("weighted_skill_score")),
        "skill_metric_source": fmt(skill.get("source")),
        "skill_count": fmt(skill.get("skill_count")),
        "max_cosine_similarity": fmt(skill.get("max_cosine_similarity")),
        "avg_cosine_similarity": fmt(skill.get("avg_cosine_similarity")),
        "avg_all_section_cosine_similarity": fmt(skill.get("avg_all_section_cosine_similarity")),
        "dynamic_weight_status": fmt(dynamic.get("status")),
        "available_signal_count": fmt(dynamic.get("available_signal_count")),
        "weight_resume_consistency": fmt(weights.get("ResumeConsistency")),
        "weight_repository_authenticity": fmt(weights.get("RepositoryAuthenticity")),
        "weight_readme_originality": fmt(weights.get("ReadmeOriginality")),
        "weight_code_originality": fmt(weights.get("CodeOriginality")),
        "weight_behavioral_authenticity": fmt(weights.get("BehavioralAuthenticity")),
        "weight_oss_contribution": fmt(weights.get("OSSContribution")),
        "clone_code_similarity_max": fmt(clone.get("code_similarity_max")),
        "clone_readme_similarity_max": fmt(clone.get("readme_similarity_max")),
        "jaccard_status": fmt(clone.get("jaccard_status")),
        "max_jaccard_similarity": fmt(clone.get("max_jaccard_similarity")),
        "avg_jaccard_similarity": fmt(clone.get("avg_jaccard_similarity")),
        "top_k_mean_status": fmt(clone.get("top_k_mean_status")),
        "max_top_k_mean": fmt(clone.get("max_top_k_mean")),
        "avg_top_k_mean": fmt(clone.get("avg_top_k_mean")),
        "updated_at": fmt(doc.get("updated_at")),
    }


async def backfill_metrics() -> int:
    count = 0
    async for application in DB.applications.find({}, {"candidate_id": 1, "job_id": 1}):
        candidate_id = application.get("candidate_id")
        job_id = application.get("job_id")
        if not candidate_id or not job_id:
            continue
        result = await upsert_metrics_for_application(candidate_id=candidate_id, job_id=job_id, db_client=DB)
        if result is not None:
            count += 1
    return count


async def append_new_metric_rows(csv_path: Path) -> int:
    ensure_output_file(csv_path)
    existing = load_existing_metric_keys(csv_path)
    rows: List[Dict[str, str]] = []

    async for metric_doc in DB.metrics.find({}).sort("updated_at", 1):
        metrics_key = metric_doc.get("metrics_key")
        if not metrics_key or metrics_key in existing:
            continue
        rows.append(flatten_metric_doc(metric_doc))

    if not rows:
        return 0

    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writerows(rows)

    return len(rows)


async def process_once(csv_path: Path) -> tuple[int, int]:
    backfilled = await backfill_metrics()
    appended = await append_new_metric_rows(csv_path)
    return backfilled, appended


async def async_main() -> int:
    global CLIENT, DB
    args = parse_args()
    output_path = Path(args.output).resolve()
    ensure_output_file(output_path)
    CLIENT = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    DB = CLIENT[DB_NAME]

    try:
        await DB.command("ping")
    except Exception as exc:
        print(f"Failed to connect to MongoDB at {MONGO_URL}: {exc}", file=sys.stderr)
        CLIENT.close()
        return 1

    try:
        if not args.watch:
            backfilled, appended = await process_once(output_path)
            print(
                f"Processed {backfilled} application metric record(s); "
                f"appended {appended} new CSV row(s) to {output_path}"
            )
            return 0

        print(f"Watching MongoDB applications/metrics and exporting to {output_path}")
        while True:
            backfilled, appended = await process_once(output_path)
            if backfilled or appended:
                print(
                    f"Processed {backfilled} application metric record(s); "
                    f"appended {appended} new CSV row(s)"
                )
            await asyncio.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        print("Stopped watcher.")
        return 0
    finally:
        CLIENT.close()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
