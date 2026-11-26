"""
Structured interview scorecards (logic in app/services/scorecards.py).

- The job's template lives on the job document (jobs.scorecard).
- One `scorecards` doc per job x candidate x interviewer: status requested -> draft -> submitted.
- Interviewers who owe a scorecard see only their own until they submit it.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import AuthUser, get_current_user, require_job_owner
from app.database import db
from app.org import ensure_org
from app.routes.evaluation_routes import EARLY_STATUSES
from app.services import scorecards as sc
from app.services.cover_letter_service import _parse_json
from app.services.fact_checker_service import AIServiceUnavailable, _call_groq
from app.services.quota import rate_limit, use_quota

router = APIRouter(prefix="/jobs", tags=["scorecards"])
CARD = "/{job_id}/candidates/{candidate_id}/scorecards"
AI_DOWN = "The AI service is down, so {what} can't be made right now. Try again later."


async def _require_application(job_id: str, candidate_id: str) -> None:
    # 404 so other workspaces' candidate ids aren't revealed
    if not await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 1}):
        raise HTTPException(404, "Candidate not found")


def _template(job: dict) -> list:
    return ((job.get("scorecard") or {}).get("competencies")) or []


def _card_out(card: dict) -> dict:
    return {k: card.get(k) for k in ("author_uid", "author_name", "status", "ratings", "recommendation", "summary",
                                     "requested_by_name", "created_at", "updated_at", "submitted_at")} | \
        {"versions": len(card.get("history") or [])}


async def _cards(job_id: str, candidate_id: str) -> list:
    return await db.scorecards.find({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 0}).to_list(100)


async def _visible_cards(job_id: str, candidate_id: str, uid: str):
    """(all cards, caller's card, whether the caller must submit before seeing others)."""
    cards = await _cards(job_id, candidate_id)
    mine = next((c for c in cards if c["author_uid"] == uid), None)
    return cards, mine, sc.must_submit_first(mine)


# ── Template ─────────────────────────────────────────────────────────────

@router.get("/{job_id}/scorecard")
async def get_template(job: dict = Depends(require_job_owner)):
    return {"scorecard": job.get("scorecard")}


@router.put("/{job_id}/scorecard")
async def save_template(body: sc.TemplateIn, job: dict = Depends(require_job_owner),
                        user: AuthUser = Depends(get_current_user)):
    scorecard = {"competencies": [c.model_dump() for c in body.competencies],
                 "updated_at": datetime.utcnow(), "updated_by": user.name or user.email or user.uid}
    await db.jobs.update_one({"_id": job["_id"]}, {"$set": {"scorecard": scorecard}})
    return {"scorecard": scorecard}


@router.post("/{job_id}/scorecard/suggest")
async def suggest_template(job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """AI draft of competencies and anchors from the job description. Not saved: the recruiter edits it first."""
    rate_limit(user.uid, "ai")
    await use_quota(await ensure_org(user), "ai_call", feature="scorecards")
    try:
        raw = await _call_groq(sc.SUGGEST_SYSTEM, sc.suggest_prompt(job), temperature=0.3)
        draft = sc.TemplateIn.model_validate(_parse_json(raw))
    except AIServiceUnavailable:
        raise HTTPException(503, AI_DOWN.format(what="a suggested scorecard"))
    except ValueError:  # bad JSON or a draft that fails TemplateIn (ValidationError is a ValueError)
        raise HTTPException(503, "The AI service returned an unusable draft. Try again, or write the scorecard yourself.")
    return {"competencies": [c.model_dump() for c in draft.competencies]}


@router.get("/{job_id}/scorecard-counts", dependencies=[Depends(require_job_owner)])
async def scorecard_counts(job_id: str):
    """{candidate_id: {submitted, total}} for the pipeline's "Scorecards 2/3" indicator."""
    counts = {}
    async for row in db.scorecards.aggregate([
        {"$match": {"job_id": job_id}},
        {"$group": {"_id": "$candidate_id", "total": {"$sum": 1},
                    "submitted": {"$sum": {"$cond": [{"$eq": ["$status", "submitted"]}, 1, 0]}}}},
    ]):
        counts[row["_id"]] = {"submitted": row["submitted"], "total": row["total"]}
    return {"counts": counts}


# ── Interviewer scorecards ───────────────────────────────────────────────

@router.get(CARD)
async def get_scorecards(job_id: str, candidate_id: str, job: dict = Depends(require_job_owner),
                         user: AuthUser = Depends(get_current_user)):
    await _require_application(job_id, candidate_id)
    cards, mine, locked = await _visible_cards(job_id, candidate_id, user.uid)
    others = [] if locked else [_card_out(c) for c in cards if c["author_uid"] != user.uid and c["status"] == "submitted"]
    return {
        "template": _template(job),
        "mine": _card_out(mine) if mine else None,
        "locked": locked,
        "others": others,
        # Who has been asked and where they are; never their ratings
        "interviewers": [{"uid": c["author_uid"], "name": c.get("author_name"), "status": c["status"]} for c in cards],
    }


@router.put(CARD + "/mine")
async def save_my_scorecard(job_id: str, candidate_id: str, body: sc.ScorecardIn,
                            job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """Save a draft (autosave) or submit. Only the author edits their card; each re-submission keeps the previous version."""
    await _require_application(job_id, candidate_id)
    template = _template(job)
    if not template:
        raise HTTPException(409, "This job has no scorecard yet. Set one up on the job page first.")
    try:
        ratings = sc.check_submission(template, body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    key = {"job_id": job_id, "candidate_id": candidate_id, "author_uid": user.uid}
    existing = await db.scorecards.find_one(key)
    if existing and existing["status"] == "submitted" and not body.submit:
        raise HTTPException(409, "This scorecard is already submitted. Submit again to update it.")
    now = datetime.utcnow()
    fields = {"ratings": ratings, "recommendation": body.recommendation, "summary": body.summary.strip(),
              "author_name": user.name or user.email or "Interviewer", "updated_at": now,
              "status": "submitted" if body.submit else "draft"}
    update = {"$set": fields, "$setOnInsert": {"created_at": now}}
    if body.submit:
        fields["submitted_at"] = now
        if existing and existing["status"] == "submitted":
            update["$push"] = {"history": {k: existing.get(k) for k in ("ratings", "recommendation", "summary", "submitted_at")}}
    await db.scorecards.update_one(key, update, upsert=True)
    if body.submit:
        # A scorecard means the candidate was interviewed; later stages are left alone
        await db.applications.update_one(
            {"job_id": job_id, "candidate_id": candidate_id, "status": {"$in": EARLY_STATUSES}},
            {"$set": {"status": "Interview", "updated_at": now}},
        )
    return {"mine": _card_out(await db.scorecards.find_one(key, {"_id": 0}))}


class RequestIn(BaseModel):
    uid: str


@router.post(CARD + "/requests")
async def request_scorecard(job_id: str, candidate_id: str, body: RequestIn,
                            job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """Ask a workspace member to interview: they then see only their own card until they submit."""
    await _require_application(job_id, candidate_id)
    member = await db.org_members.find_one({"org_id": job["org_id"], "uid": body.uid})
    if not member:
        raise HTTPException(404, "Member not found")
    now = datetime.utcnow()
    await db.scorecards.update_one(
        {"job_id": job_id, "candidate_id": candidate_id, "author_uid": body.uid},
        {"$setOnInsert": {"status": "requested", "ratings": [], "recommendation": None, "summary": "",
                          "author_name": member.get("name") or member.get("email") or "Interviewer",
                          "requested_by_name": user.name or user.email, "created_at": now, "updated_at": now}},
        upsert=True,
    )
    return {"status": "requested"}


@router.delete(CARD + "/requests/{uid}", dependencies=[Depends(require_job_owner)])
async def cancel_request(job_id: str, candidate_id: str, uid: str):
    """Withdraw a request nobody has started on; drafts and submitted cards stay."""
    await _require_application(job_id, candidate_id)
    await db.scorecards.delete_one({"job_id": job_id, "candidate_id": candidate_id, "author_uid": uid, "status": "requested"})
    return {"status": "cancelled"}


# ── Evidence summary ─────────────────────────────────────────────────────

async def _summary_inputs(job_id: str, candidate_id: str, job: dict, uid: str):
    await _require_application(job_id, candidate_id)
    cards, _, locked = await _visible_cards(job_id, candidate_id, uid)
    if locked:
        raise HTTPException(403, "Submit your own scorecard first: other interviewers' ratings stay hidden until you do.")
    return _template(job), cards


@router.get(CARD + "/summary")
async def evidence_summary(job_id: str, candidate_id: str, job: dict = Depends(require_job_owner),
                           user: AuthUser = Depends(get_current_user)):
    template, cards = await _summary_inputs(job_id, candidate_id, job, user.uid)
    evaluation = await db.evaluations.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"questions": 1})
    return {"summary": sc.aggregate(template, cards, evaluation), "has_template": bool(template)}


@router.post(CARD + "/brief")
async def evidence_brief(job_id: str, candidate_id: str, job: dict = Depends(require_job_owner),
                         user: AuthUser = Depends(get_current_user)):
    """AI summary of the submitted evidence notes only, citing the interviewer behind each point."""
    rate_limit(user.uid, "ai")
    template, cards = await _summary_inputs(job_id, candidate_id, job, user.uid)
    if not any(c["status"] == "submitted" for c in cards):
        raise HTTPException(409, "No submitted scorecards to summarise yet")
    await use_quota(await ensure_org(user), "ai_call", feature="scorecards")
    prompt, labels = sc.brief_prompt(template, cards)
    try:
        brief = sc.check_brief(_parse_json(await _call_groq(sc.BRIEF_SYSTEM, prompt, temperature=0.2)), labels)
    except AIServiceUnavailable:
        raise HTTPException(503, AI_DOWN.format(what="the evidence brief"))
    except ValueError:
        brief = None
    if not brief:
        raise HTTPException(503, "The AI service returned an unusable brief. Try again later.")
    return {"brief": brief}
