"""
Hiring reports: where the workspace's hiring process hurts, with numbers to act on.

GET /api/reports/overview      funnel, time in stage, stuck candidates, overdue feedback,
                               screening quality, job health, AI usage and a "pain points" list
GET /api/reports/export.csv    one section as CSV (stuck | jobs | funnel)

The maths are pure functions over fetched rows (tested directly). Queries are bounded:
at most MAX_JOBS jobs and MAX_APPLICATIONS applications (newest first; ``truncated`` is
set when the cap is hit), candidate names only for the listed rows (MAX_LIST_ROWS),
and resume-processing failures are grouped by a MongoDB aggregation (MAX_ERROR_GROUPS).

Time in stage comes from ``applications.status_history`` (app.services.status_history).
Applications created before it existed fall back to their timestamps, and the report
says the data is partial.
"""
import csv
import io
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.auth import AuthUser, get_current_user
from app.database import db
from app.org import access, job_filter, membership, reject_api_key
from app.routes.job_routes import SHORTLISTED_STATUSES
from app.routes.resume import normalize_status
from app.services.quota import usage_today

router = APIRouter(prefix="/reports", tags=["reports"])

STAGES = ["Under Review", "Shortlisted", "Interview", "Offer", "Hired"]
ACTIVE_STAGES = STAGES[:-1]  # a candidate can be stuck in these
LOW_CREDIBILITY = 60
NO_NEW_CANDIDATES_DAYS = 14
RED_FLAG_SEVERITIES = {"major", "critical"}
DROP_MIN_SAMPLE = 10  # candidates reaching a stage before its conversion counts as the biggest drop-off

MAX_JOBS = 500
MAX_APPLICATIONS = 20000
MAX_LIST_ROWS = 200
MAX_ERROR_GROUPS = 50

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

STUCK_SUGGESTIONS = {
    "Under Review": "Review these candidates or reject them, so nobody waits without an answer.",
    "Shortlisted": "Schedule interviews for these candidates or move them on.",
    "Interview": "Collect the interview feedback and decide on these candidates.",
    "Offer": "Follow up on these open offers before candidates accept elsewhere.",
}


# ── Pure maths ──────────────────────────────────────────────────────────

def _days(delta: timedelta) -> float:
    return delta.total_seconds() / 86400


def percentile(values, p: float):
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    v = sorted(values)
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)]


def summarize(values) -> dict:
    """{median_days, p90_days, count}; None (not 0) when there is no data."""
    return {
        "median_days": round(statistics.median(values), 1) if values else None,
        "p90_days": round(percentile(values, 90), 1) if values else None,
        "count": len(values),
    }


def pct(part: int, whole: int):
    return round(100 * part / whole, 1) if whole else None


def history(app: dict) -> tuple[list, bool]:
    """[(status, at)] oldest first, and whether it is a best-effort guess from timestamps."""
    entries = [(normalize_status(e.get("status")) or e.get("status"), e["at"])
               for e in app.get("status_history") or [] if isinstance(e, dict) and isinstance(e.get("at"), datetime)]
    if entries:
        return entries, False
    applied = app.get("application_date") or app.get("updated_at")
    status = normalize_status(app.get("status")) or "Under Review"
    guess = [("Under Review", applied)] if applied else []
    if status != "Under Review" and (app.get("updated_at") or applied):
        guess.append((status, app.get("updated_at") or applied))
    return guess, True


def app_row(app: dict, now: datetime) -> dict:
    """The fields reports need from one application."""
    entries, partial = history(app)
    status = normalize_status(app.get("status")) or "Under Review"
    since = next((at for s, at in reversed(entries) if s == status), None) or app.get("updated_at") or app.get("application_date")
    reached = [STAGES.index(s) for s, _ in entries if s in STAGES] + ([STAGES.index(status)] if status in STAGES else [])
    times = [at for _, at in entries] + [t for t in (app.get("application_date"), app.get("updated_at")) if t]
    return {
        "job_id": app.get("job_id"),
        "candidate_id": app.get("candidate_id"),
        "status": status,
        "entries": entries,
        "partial": partial,
        "applied": app.get("application_date"),
        "since": since,
        "days_in_stage": round(_days(now - since), 1) if since else None,
        "reached": max(reached, default=0),
        "last_activity": max(times, default=None),
        "score_details": app.get("score_details") or {},
    }


def funnel(rows: list) -> dict:
    """Candidates per stage now, how many ever reached each stage, and stage-to-stage conversion (%).

    The biggest drop-off is the lowest conversion among stages at least DROP_MIN_SAMPLE candidates reached.
    """
    current = Counter(r["status"] for r in rows)
    reached = [sum(1 for r in rows if r["reached"] >= i) for i in range(len(STAGES))]
    conversions = [{"from": STAGES[i], "to": STAGES[i + 1], "from_count": reached[i], "to_count": reached[i + 1],
                    "rate": pct(reached[i + 1], reached[i])} for i in range(len(STAGES) - 1)]
    known = [c for c in conversions if c["rate"] is not None and c["from_count"] >= DROP_MIN_SAMPLE]
    biggest = min(known, key=lambda c: c["rate"]) if known else None
    for c in conversions:
        c["biggest_drop"] = c is biggest
    return {
        "stages": [{"stage": s, "current": current[s], "reached": reached[i]} for i, s in enumerate(STAGES)],
        "rejected": current["Rejected"],
        "conversions": conversions,
        "biggest_drop": biggest,
    }


def time_in_stage(rows: list) -> list:
    """Median / p90 days spent in each stage, from candidates who left it."""
    spent = defaultdict(list)
    for r in rows:
        if r["partial"]:
            continue  # guessed timestamps would distort the durations
        for (s, start), (_, end) in zip(r["entries"], r["entries"][1:]):
            if s in ACTIVE_STAGES and end >= start:
                spent[s].append(_days(end - start))
    return [{"stage": s, **summarize(spent[s])} for s in ACTIVE_STAGES]


def milestones(rows: list) -> dict:
    """Median days from application to first review (any move), shortlist and hire."""
    first_review, shortlist, hire = [], [], []
    for r in rows:
        if r["partial"] or not r["applied"]:
            continue
        for target, test in ((first_review, lambda s: s != "Under Review"),
                             (shortlist, lambda s: s in SHORTLISTED_STATUSES),
                             (hire, lambda s: s == "Hired")):
            at = next((at for s, at in r["entries"] if test(s)), None)
            if at and at >= r["applied"]:
                target.append(_days(at - r["applied"]))
    return {"first_review": summarize(first_review), "shortlist": summarize(shortlist), "hire": summarize(hire)}


def stuck(rows: list, threshold_days: int) -> list:
    """Candidates in an active stage for longer than the threshold, longest first."""
    out = [r for r in rows if r["status"] in ACTIVE_STAGES and r["days_in_stage"] is not None
           and r["days_in_stage"] > threshold_days]
    return sorted(out, key=lambda r: -r["days_in_stage"])


def overdue_feedback(rows: list, evaluated: set, days: int) -> list:
    """Candidates at Interview for more than ``days`` with no evaluation submitted."""
    out = [r for r in rows if r["status"] == "Interview" and (r["job_id"], r["candidate_id"]) not in evaluated
           and r["days_in_stage"] is not None and r["days_in_stage"] > days]
    return sorted(out, key=lambda r: -r["days_in_stage"])


def credibility(score_details: dict):
    """0–100, or None when no source could be checked (not 0)."""
    if score_details.get("score_source") == "unverified":
        return None
    value = score_details.get("overall_score")
    return float(value) if isinstance(value, (int, float)) else None


def has_red_flags(verification: dict | None) -> bool:
    v = verification or {}
    discrepancies = (v.get("verificationStatus") or {}).get("discrepancies") or []
    if any(isinstance(d, dict) and str(d.get("severity") or "").lower() in RED_FLAG_SEVERITIES for d in discrepancies):
        return True
    return bool((v.get("githubData") or {}).get("redFlags"))


def failure_reason(status: str, error: str | None) -> str:
    """Plain-words category for a failed resume task (see app.routes.resume / task_queue error texts)."""
    e = (error or "").lower()
    if status == "verification_failed":
        return "Verification failed"
    if "took too long" in e or "timeout" in e:
        return "Timed out reading the file"
    if "stopped responding" in e or "interrupted" in e:
        return "Processing interrupted"
    if "no text could be read" in e:
        return "No readable text (scanned image?)"
    if "could not parse" in e:
        return "Could not parse the resume"
    if "could not save" in e:
        return "Could not save the candidate"
    return "Other error"


def screening(rows: list, verification_by_cid: dict, task_counts: dict, failures: list) -> dict:
    """Credibility, red flags, verification sources and resume-processing failures."""
    scores = [c for c in (credibility(r["score_details"]) for r in rows) if c is not None]
    low = sum(1 for c in scores if c < LOW_CREDIBILITY)
    cids = {r["candidate_id"] for r in rows}
    flagged = sum(1 for cid in cids if has_red_flags(verification_by_cid.get(cid)))
    sources = {"github": Counter(), "linkedin": Counter(), "webCheck": Counter()}
    for cid in cids:
        status = (verification_by_cid.get(cid) or {}).get("verificationStatus") or {}
        for source, counter in sources.items():
            counter[status.get(source) or "pending"] += 1
    reasons = Counter()
    for f in failures:
        reasons[failure_reason(f["status"], f.get("error"))] += f["count"]
    total_tasks = sum(task_counts.values())
    failed = task_counts.get("failed", 0) + task_counts.get("verification_failed", 0)
    return {
        "candidates": len(cids),
        "scored": len(scores),
        "low_credibility": low,
        "low_credibility_pct": pct(low, len(scores)),
        "red_flags": flagged,
        "red_flags_pct": pct(flagged, len(cids)),
        "verification_sources": {s: dict(c) for s, c in sources.items()},
        "verification_failures": task_counts.get("verification_failed", 0),
        "tasks_total": total_tasks,
        "tasks_failed": failed,
        "tasks_failed_pct": pct(failed, total_tasks),
        "failure_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common()],
    }


def job_status(job: dict) -> str:
    return job.get("status") or ("Active" if job.get("is_active", True) else "Closed")


def job_health(jobs: list, rows: list, stuck_rows: list, overdue_rows: list, now: datetime) -> list:
    by_job = defaultdict(list)
    for r in rows:
        by_job[r["job_id"]].append(r)
    stuck_n = Counter(r["job_id"] for r in stuck_rows)
    overdue_n = Counter(r["job_id"] for r in overdue_rows)
    out = []
    for job in jobs:
        jid = str(job["_id"])
        apps = by_job.get(jid, [])
        posted = job.get("posted_at")
        open_days = int(_days(now - posted)) if isinstance(posted, datetime) else None
        last_applied = max((r["applied"] for r in apps if r["applied"]), default=None)
        activity = [r["last_activity"] for r in apps if r["last_activity"]]
        status = job_status(job)
        quiet_since = last_applied or posted
        no_new = status == "Active" and isinstance(quiet_since, datetime) and _days(now - quiet_since) > NO_NEW_CANDIDATES_DAYS
        out.append({
            "job_id": jid,
            "title": job.get("job_title") or "Untitled job",
            "status": status,
            "open_days": open_days,
            "candidates": len(apps),
            "shortlisted_pct": pct(sum(1 for r in apps if r["status"] in SHORTLISTED_STATUSES), len(apps)),
            "stuck": stuck_n[jid],
            "overdue_feedback": overdue_n[jid],
            "last_activity": max(activity, default=None),
            "last_application": last_applied,
            "no_new_candidates": no_new,
        })
    return sorted(out, key=lambda j: (-(j["stuck"] + j["overdue_feedback"]), -j["candidates"]))


def _plural(n: int, word: str, plural: str | None = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _only_job(rows: list):
    ids = {r["job_id"] for r in rows}
    return ids.pop() if len(ids) == 1 else None


def pain_points(report: dict, stuck_rows: list, overdue_rows: list, stuck_days: int, feedback_days: int) -> list:
    """Plain-words problems, most severe first. Rules (thresholds below):

    - stuck in a stage > stuck_days: high ≥10 candidates, medium ≥3, else low (one item per stage)
    - interviews without feedback > feedback_days: high ≥5, else medium
    - the biggest drop-off (≥10 candidates reaching the earlier stage) under 25%: medium
    - active jobs with no new candidates in 14 days: medium
    - ≥30% of verified candidates under 60 credibility (≥5 verified): medium
    - candidates with major/critical verification red flags: medium ≥5, else low
    - resume processing failures ≥10% of uploads (≥5 uploads): high ≥25%, else medium
    - today's AI calls or uploads ≥80% of the daily limit: high at 100%, else medium
    - median time to first review over stuck_days (≥5 measured): medium
    """
    items = []

    def add(pid, severity, title, metric, suggestion, job_id=None, status=None, section=None):
        items.append({"id": pid, "severity": severity, "title": title, "metric": metric, "suggestion": suggestion,
                      "link": {"job_id": job_id, "status": status, "section": section}})

    for stage in ACTIVE_STAGES:
        group = [r for r in stuck_rows if r["status"] == stage]
        if group:
            n = len(group)
            add(f"stuck-{stage.lower().replace(' ', '-')}", "high" if n >= 10 else "medium" if n >= 3 else "low",
                f"{_plural(n, 'candidate')} stuck in {stage} for over {_plural(stuck_days, 'day')}", n,
                STUCK_SUGGESTIONS[stage], _only_job(group), stage, "stuck")

    if overdue_rows:
        n = len(overdue_rows)
        add("overdue-feedback", "high" if n >= 5 else "medium",
            f"{_plural(n, 'interview')} with no feedback after {_plural(feedback_days, 'day')}", n,
            "Ask the interviewers to submit their evaluations so candidates get a decision.",
            _only_job(overdue_rows), "Interview", "feedback")

    drop = report["funnel"]["biggest_drop"]
    if drop and drop["rate"] < 25:
        add("drop-off", "medium", f"Only {drop['rate']:g}% of candidates move from {drop['from']} to {drop['to']}",
            drop["rate"], "Check whether the job description and required skills match the people applying.",
            report["filters"]["job_id"], drop["from"], "funnel")

    quiet = [j for j in report["jobs"] if j["no_new_candidates"]]
    if quiet:
        n = len(quiet)
        add("no-new-candidates", "medium",
            f"{_plural(n, 'active job has', 'active jobs have')} had no new candidates for {NO_NEW_CANDIDATES_DAYS} days", n,
            "Repost or promote these jobs, or close them if they are filled.",
            quiet[0]["job_id"] if n == 1 else None, None, "jobs")

    s = report["screening"]
    if s["scored"] >= 5 and s["low_credibility_pct"] is not None and s["low_credibility_pct"] >= 30:
        add("low-credibility", "medium",
            f"{s['low_credibility_pct']:g}% of verified candidates have credibility below {LOW_CREDIBILITY}",
            s["low_credibility_pct"], "Look at where these candidates come from and tighten the sourcing channel.",
            report["filters"]["job_id"], None, "screening")
    if s["red_flags"]:
        add("red-flags", "medium" if s["red_flags"] >= 5 else "low",
            f"{_plural(s['red_flags'], 'candidate has', 'candidates have')} verification red flags", s["red_flags"],
            "Open their dossiers and check the flagged claims before interviewing.",
            report["filters"]["job_id"], None, "screening")
    if s["tasks_total"] >= 5 and s["tasks_failed_pct"] is not None and s["tasks_failed_pct"] >= 10:
        add("processing-failures", "high" if s["tasks_failed_pct"] >= 25 else "medium",
            f"{s['tasks_failed']} of {s['tasks_total']} resume uploads failed ({s['tasks_failed_pct']:g}%)",
            s["tasks_failed_pct"], "See the failure reasons below and re-upload the affected resumes.",
            report["filters"]["job_id"], None, "screening")

    for kind, u in (report.get("ai_usage") or {}).items():
        if u["limit"] and u["used"] >= 0.8 * u["limit"]:
            add(f"quota-{kind}", "high" if u["used"] >= u["limit"] else "medium",
                f"Today's {u['label']}: {u['used']} of {u['limit']} used", round(100 * u["used"] / u["limit"], 1),
                "Spread large uploads over several days or raise the daily limit.", section="ai-usage")

    fr = report["milestones"]["first_review"]
    if fr["count"] >= 5 and fr["median_days"] is not None and fr["median_days"] > stuck_days:
        add("slow-first-review", "medium", f"Candidates wait a median {fr['median_days']:g} days for a first review",
            fr["median_days"], "Set aside regular time to review new candidates.",
            report["filters"]["job_id"], "Under Review", "timing")

    return sorted(items, key=lambda i: (SEVERITY_ORDER[i["severity"]], -float(i["metric"] or 0)))


# ── Data access ─────────────────────────────────────────────────────────

async def _visible_jobs_filter(user) -> dict:
    """Jobs the caller may see in reports: the workspace's, only assigned ones for restricted roles."""
    return job_filter(await access(user))


def _date_range(start: Optional[date], end: Optional[date]) -> dict:
    rng = {}
    if start:
        rng["$gte"] = datetime.combine(start, datetime.min.time())
    if end:
        rng["$lt"] = datetime.combine(end + timedelta(days=1), datetime.min.time())
    return rng


async def _jobs(user, job_id: Optional[str]) -> list:
    query = await _visible_jobs_filter(user)
    if job_id:
        try:
            query["_id"] = ObjectId(job_id)
        except Exception:
            raise HTTPException(404, "Job not found")
    jobs = await db.jobs.find(query, {"job_title": 1, "status": 1, "is_active": 1, "posted_at": 1}) \
        .sort("posted_at", -1).to_list(MAX_JOBS)
    if job_id and not jobs:
        raise HTTPException(404, "Job not found")  # another workspace's job looks the same as a missing one
    return jobs


async def _names(rows: list) -> dict:
    ids = list({r["candidate_id"] for r in rows})
    return {c["candidate_id"]: (c.get("parsed") or {}).get("personal_info", {}).get("full_name") or "Unknown"
            async for c in db.candidates.find({"candidate_id": {"$in": ids}}, {"candidate_id": 1, "parsed.personal_info.full_name": 1})}


def _person_rows(rows: list, names: dict, titles: dict) -> list:
    return [{"job_id": r["job_id"], "job_title": titles.get(r["job_id"], ""), "candidate_id": r["candidate_id"],
             "name": names.get(r["candidate_id"], "Unknown"), "stage": r["status"], "days": r["days_in_stage"],
             "partial": r["partial"]} for r in rows[:MAX_LIST_ROWS]]


async def build_report(user, job_id: Optional[str], start: Optional[date], end: Optional[date],
                       stuck_days: int, feedback_days: int) -> dict:
    now = datetime.utcnow()
    jobs = await _jobs(user, job_id)
    job_ids = [str(j["_id"]) for j in jobs]
    titles = {str(j["_id"]): j.get("job_title") or "Untitled job" for j in jobs}
    rng = _date_range(start, end)

    app_query = {"job_id": {"$in": job_ids}, **({"application_date": rng} if rng else {})}
    apps = await db.applications.find(
        app_query, {"job_id": 1, "candidate_id": 1, "status": 1, "application_date": 1, "updated_at": 1,
                    "status_history": 1, "score_details.overall_score": 1, "score_details.score_source": 1},
    ).sort("application_date", -1).to_list(MAX_APPLICATIONS)
    rows = [app_row(a, now) for a in apps]
    cids = list({r["candidate_id"] for r in rows})

    evaluated = {(e["job_id"], e["candidate_id"]) async for e in db.evaluations.find(
        {"job_id": {"$in": job_ids}, "candidate_id": {"$in": cids}}, {"job_id": 1, "candidate_id": 1})}
    verification_by_cid = {}
    async for v in db.verification_data.find(
            {"$or": [{"candidateId": {"$in": cids}}, {"candidate_id": {"$in": cids}}]},
            {"candidateId": 1, "candidate_id": 1, "verificationStatus": 1, "githubData.redFlags": 1}):
        verification_by_cid.setdefault(v.get("candidateId") or v.get("candidate_id"), v)

    task_match = {"job_id": {"$in": job_ids}, **({"created_at": rng} if rng else {})}
    task_counts = {row["_id"]: row["n"] async for row in db.tasks.aggregate([
        {"$match": task_match}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    failures = [{"status": row["_id"]["status"], "error": row["_id"]["error"], "count": row["n"]}
                async for row in db.tasks.aggregate([
                    {"$match": {**task_match, "status": {"$in": ["failed", "verification_failed"]}}},
                    {"$group": {"_id": {"status": "$status", "error": "$error"}, "n": {"$sum": 1}}},
                    {"$sort": {"n": -1}}, {"$limit": MAX_ERROR_GROUPS}])]

    stuck_rows = stuck(rows, stuck_days)
    overdue_rows = overdue_feedback(rows, evaluated, feedback_days)
    names = await _names(stuck_rows[:MAX_LIST_ROWS] + overdue_rows[:MAX_LIST_ROWS])
    by_stage = Counter(r["status"] for r in stuck_rows)

    report = {
        "generated_at": now,
        "filters": {"job_id": job_id, "from": start, "to": end, "stuck_days": stuck_days, "feedback_days": feedback_days},
        "truncated": len(apps) >= MAX_APPLICATIONS or len(jobs) >= MAX_JOBS,
        "partial_data": any(r["partial"] for r in rows),
        "partial_count": sum(1 for r in rows if r["partial"]),
        "totals": {"jobs": len(jobs), "candidates": len(rows)},
        "funnel": funnel(rows),
        "time_in_stage": time_in_stage(rows),
        "milestones": milestones(rows),
        "stuck": {"count": len(stuck_rows), "threshold_days": stuck_days,
                  "by_stage": {s: by_stage[s] for s in ACTIVE_STAGES},
                  "candidates": _person_rows(stuck_rows, names, titles)},
        "overdue_feedback": {"count": len(overdue_rows), "days": feedback_days,
                             "candidates": _person_rows(overdue_rows, names, titles)},
        "screening": screening(rows, verification_by_cid, task_counts, failures),
        "jobs": job_health(jobs, rows, stuck_rows, overdue_rows, now),
        "ai_usage": await usage_today((await membership(user))["org_id"]),
    }
    report["pain_points"] = pain_points(report, stuck_rows, overdue_rows, stuck_days, feedback_days)
    return report


# ── CSV ─────────────────────────────────────────────────────────────────

def safe_cell(value) -> str:
    """CSV cell text; text starting with = + - @ (or tab / CR) gets a leading quote so spreadsheets don't run it."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(header: list, rows: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return buf.getvalue()


def export_rows(report: dict, kind: str) -> tuple[list, list]:
    if kind == "stuck":
        return (["Job", "Candidate", "Stage", "Days in stage", "Partial data"],
                [[c["job_title"], c["name"], c["stage"], c["days"], c["partial"]] for c in report["stuck"]["candidates"]])
    if kind == "jobs":
        return (["Job", "Status", "Open days", "Candidates", "Shortlisted %", "Stuck", "Overdue feedback",
                 "Last activity", f"No new candidates in {NO_NEW_CANDIDATES_DAYS} days"],
                [[j["title"], j["status"], j["open_days"], j["candidates"], j["shortlisted_pct"], j["stuck"],
                  j["overdue_feedback"], j["last_activity"], j["no_new_candidates"]] for j in report["jobs"]])
    conv = {c["from"]: c["rate"] for c in report["funnel"]["conversions"]}
    return (["Stage", "Candidates now", "Reached stage", "Moved to next stage %"],
            [[s["stage"], s["current"], s["reached"], conv.get(s["stage"])] for s in report["funnel"]["stages"]]
            + [["Rejected", report["funnel"]["rejected"], None, None]])


# ── Routes ──────────────────────────────────────────────────────────────

def _params(job_id: Optional[str] = None,
            start: Optional[date] = Query(None, alias="from"),
            end: Optional[date] = Query(None, alias="to"),
            stuck_days: int = Query(7, ge=1, le=365),
            feedback_days: int = Query(3, ge=1, le=90)) -> dict:
    return {"job_id": job_id or None, "start": start, "end": end, "stuck_days": stuck_days, "feedback_days": feedback_days}


@router.get("/overview")
async def overview(params: dict = Depends(_params), user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    return await build_report(user, **params)


@router.get("/export.csv")
async def export_csv(report: Literal["stuck", "jobs", "funnel"], params: dict = Depends(_params),
                     user: AuthUser = Depends(get_current_user)):
    reject_api_key(user)
    header, rows = export_rows(await build_report(user, **params), report)
    filename = f"resumeai-{report}-{datetime.utcnow().date().isoformat()}.csv"
    return Response(to_csv(header, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
