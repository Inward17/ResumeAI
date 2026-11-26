"""
Interview scheduling: common free slots, booking on the organizer's calendar,
self-scheduling links for candidates, reschedule and cancel.

``interviews`` documents: org_id, job_id, candidate_id, interviewer_uids, organizer_uid,
provider, start/end (UTC), timezone, duration_minutes, location_type/text, join_url,
status (proposed/booking/scheduled/cancelled/completed), provider_event_id,
token_hash + offered_slots + token_expires_at (self-scheduling), created_at, history.

``public_router`` serves the candidate's scheduling page (no sign-in): the random,
hashed, expiring link is the credential, and only job title, workspace name,
interviewer names and slot times are revealed.
"""
import hashlib
import html
import logging
import secrets
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument

from app.auth import AuthUser, get_current_user, require_job_owner
from app.database import db
from app.org import APP_URL, membership, oid, reject_api_key, send_email
from app.routes.evaluation_routes import EARLY_STATUSES
from app.services import integrations, provider_keys, scheduling
from app.services.integrations import ProviderError
from app.services.quota import rate_limit
from app.services.scheduling import iso, local_time, naive, utc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scheduling"])
public_router = APIRouter(prefix="/public/schedule", tags=["scheduling"])

LINK_DAYS = 7
MAX_RANGE_DAYS = 31
UPCOMING = ["proposed", "booking", "scheduled"]


def _zone(tz: str) -> str:
    try:
        ZoneInfo(tz)
        return tz
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown timezone")


class _Base(BaseModel):
    interviewer_uids: List[str] = Field(min_length=1, max_length=10)
    duration_minutes: int = Field(60, ge=15, le=240)
    timezone: str = Field("UTC", max_length=64)

    @field_validator("timezone")
    @classmethod
    def _check_tz(cls, v):
        return _zone(v)


class AvailabilityIn(_Base):
    start_date: date
    end_date: date
    work_start: time = time(9)
    work_end: time = time(17)
    include_weekends: bool = False


class _Where(_Base):
    location_type: Literal["video", "phone", "onsite"] = "video"
    location_text: str = Field("", max_length=300)


class BookIn(_Where):
    start: datetime


class LinkIn(_Where):
    slots: List[datetime] = Field(min_length=1, max_length=30)
    expires_in_days: int = Field(LINK_DAYS, ge=1, le=30)


class RescheduleIn(BaseModel):
    start: datetime
    duration_minutes: Optional[int] = Field(None, ge=15, le=240)


class PickIn(BaseModel):
    start: datetime
    timezone: Optional[str] = Field(None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _check_tz(cls, v):
        return _zone(v) if v else None


# ── Access (one place, so it can switch to RBAC permissions later) ──────

async def require_scheduler(user: AuthUser) -> dict:
    """Who may schedule: any signed-in workspace member. Uses their own calendar, so no API keys."""
    reject_api_key(user)
    return await membership(user)


async def _interview(interview_id: str, user: AuthUser) -> tuple:
    m = await require_scheduler(user)
    iv = await db.interviews.find_one({"_id": oid(interview_id), "org_id": m["org_id"]})
    if not iv:
        raise HTTPException(404, "Interview not found")
    return m, iv


# ── Helpers ─────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def schedule_url(token: str) -> str:
    return f"{APP_URL.rstrip('/')}/schedule/{token}"


async def _candidate(job_id: str, candidate_id: str) -> dict:
    if not await db.applications.find_one({"job_id": job_id, "candidate_id": candidate_id}, {"_id": 1}):
        raise HTTPException(404, "Candidate not found")
    doc = await db.candidates.find_one({"candidate_id": candidate_id}, {"parsed.personal_info": 1}) or {}
    info = (doc.get("parsed") or {}).get("personal_info") or {}
    return {"name": info.get("full_name") or "Candidate", "email": (info.get("email") or "").strip()}


async def _interviewers(org_id: str, uids: List[str]) -> List[dict]:
    uids = list(dict.fromkeys(uids))
    members = await db.org_members.find({"org_id": org_id, "uid": {"$in": uids}},
                                        {"_id": 0, "uid": 1, "name": 1, "email": 1}).to_list(len(uids))
    if len(members) != len(uids):
        raise HTTPException(400, "Every interviewer must be a member of this workspace")
    return sorted(members, key=lambda x: uids.index(x["uid"]))


async def _organizer_connection(uid: str, org_id: str) -> dict:
    conn = await integrations.calendar_connection(uid, org_id)
    if not conn:
        raise HTTPException(400, "Connect your Google or Microsoft calendar in Settings > Integrations first")
    return conn


async def _busy_by_person(org_id: str, people: List[dict], start: datetime, end: datetime) -> tuple:
    """({uid: busy intervals} for people whose calendar could be read, [people not checked, with why])."""
    busy, unchecked = {}, []
    for p in people:
        conn = await integrations.calendar_connection(p["uid"], org_id)
        if not conn:
            unchecked.append({"uid": p["uid"], "name": p.get("name"), "reason": "No calendar connected"})
            continue
        try:
            busy[p["uid"]] = await scheduling.busy(conn, start, end)
        except ProviderError as exc:
            unchecked.append({"uid": p["uid"], "name": p.get("name"), "reason": str(exc)})
    return busy, unchecked


async def _conflicts(org_id: str, people: List[dict], start: datetime, end: datetime,
                     ignore: Optional[tuple] = None) -> List[str]:
    """Names of interviewers whose calendar is busy during [start, end).

    ``ignore`` is the interview's current slot when rescheduling, so its own event doesn't count.
    ponytail: a busy block exactly equal to the old slot is skipped; if the provider merged it with an
    adjacent meeting it still counts as busy. Exclude by event id if that bites.
    """
    busy, _ = await _busy_by_person(org_id, people, start - timedelta(minutes=1), end + timedelta(minutes=1))
    names = {p["uid"]: p.get("name") or p.get("email") for p in people}
    return [names[uid] for uid, intervals in busy.items()
            if any(s < end and start < e and (s, e) != ignore for s, e in intervals)]


def _history(action: str, by: Optional[str], **extra) -> dict:
    return {"$push": {"history": {"at": datetime.utcnow(), "action": action, "by": by, **extra}}}


def _out(iv: dict) -> dict:
    return {
        "id": str(iv["_id"]), "job_id": iv["job_id"], "job_title": iv.get("job_title"),
        "candidate_id": iv["candidate_id"], "candidate_name": iv.get("candidate_name"),
        "interviewers": iv.get("interviewers", []), "organizer_uid": iv.get("organizer_uid"),
        "organizer_name": iv.get("organizer_name"), "provider": iv.get("provider"),
        "start": iso(iv.get("start")), "end": iso(iv.get("end")), "timezone": iv.get("timezone"),
        "duration_minutes": iv.get("duration_minutes"), "location_type": iv.get("location_type"),
        "location_text": iv.get("location_text"), "join_url": iv.get("join_url"), "status": iv["status"],
        "offered_slots": [iso(s) for s in iv.get("offered_slots", [])] if iv["status"] == "proposed" else [],
        "token_expires_at": iso(iv.get("token_expires_at")), "created_at": iso(iv.get("created_at")),
    }


def _where(iv: dict) -> str:
    if iv.get("join_url"):
        return f"Join: {iv['join_url']}"
    if iv.get("location_type") == "video":
        return "The video link is in the calendar invitation."
    label = "Phone" if iv.get("location_type") == "phone" else "Location"
    return f"{label}: {iv['location_text']}" if iv.get("location_text") else ""


async def _email_candidate(iv: dict, kind: str, tz: Optional[str] = None, link: Optional[str] = None) -> dict:
    """Email the candidate from the organizer's account, else through Composio; else return the text to copy.

    kind: scheduled | rescheduled | cancelled | link.
    """
    tz = tz or iv.get("timezone") or "UTC"
    first = (iv.get("candidate_name") or "there").split(" ")[0]
    where = f"{iv['job_title']} at {iv['org_name']}"
    people = ", ".join(i.get("name") or i.get("email") for i in iv.get("interviewers", []))
    if kind == "link":
        subject = f"Pick a time for your interview: {where}"
        lines = [f"Hi {first},", "", f"Please pick a time for your {iv['duration_minutes']}-minute interview for {where}:",
                 link, "", f"The link expires on {local_time(iv['token_expires_at'], tz)}."]
    elif kind == "cancelled":
        subject = f"Interview cancelled: {where}"
        lines = [f"Hi {first},", "", f"Your interview for {where} on {local_time(iv['start'], tz)} has been cancelled."]
    else:
        subject = f"Interview {'moved' if kind == 'rescheduled' else 'booked'}: {where}"
        lines = [f"Hi {first},", "",
                 f"Your interview for {where} is {'now ' if kind == 'rescheduled' else ''}on {local_time(iv['start'], tz)}, "
                 f"{iv['duration_minutes']} minutes.", _where(iv), f"Interviewers: {people}" if people else ""]
    text = "\n".join(line for line in lines if line is not None) + "\n"
    result = {"sent": False, "via": None, "error": None, "to": iv.get("candidate_email") or None,
              "subject": subject, "body": text}
    if not iv.get("candidate_email"):
        result["error"] = "The candidate has no email address on their resume"
        return result
    conn = await integrations.calendar_connection(iv["organizer_uid"], iv["org_id"])
    if conn:
        try:
            await scheduling.send_mail(conn, iv["candidate_email"], subject, text)
            return {**result, "sent": True, "via": conn["provider"]}
        except ProviderError as exc:
            result["error"] = str(exc)
    err = await send_email(iv["candidate_email"], subject, html.escape(text).replace("\n", "<br>"))
    if err is None:
        return {**result, "sent": True, "via": "composio", "error": None}
    result["error"] = result["error"] or err
    return result


async def _notify_slack(iv: dict, what: str) -> dict:
    when = local_time(iv["start"], iv.get("timezone") or "UTC") if iv.get("start") else ""
    names = ", ".join(i.get("name") or i.get("email") for i in iv.get("interviewers", []))
    text = f"Interview {what}: {iv.get('candidate_name')} for {iv.get('job_title')}, {when}. Interviewers: {names}."
    if iv.get("join_url") and what != "cancelled":
        text += f" Join: {iv['join_url']}"
    return await integrations.slack_notify(iv["org_id"], text, [i.get("email") for i in iv.get("interviewers", [])])


async def _book(iv: dict, start: datetime, by: Optional[str], tz: Optional[str] = None) -> dict:
    """Create the calendar event for an interview doc, mark it scheduled, email + Slack, move the candidate."""
    end = start + timedelta(minutes=iv["duration_minutes"])
    conn = await integrations.calendar_connection(iv["organizer_uid"], iv["org_id"])
    if not conn:
        raise ProviderError("The organizer's calendar is no longer connected")
    attendees = [{"email": i["email"], "name": i.get("name")} for i in iv["interviewers"] if i.get("email")]
    if iv.get("candidate_email"):
        attendees.append({"email": iv["candidate_email"], "name": iv.get("candidate_name")})
    summary = f"Interview: {iv['candidate_name']} for {iv['job_title']}"
    description = f"{iv['org_name']} interview for {iv['job_title']}, scheduled with ResumeAI."
    event = await scheduling.create_event(conn, summary, description, start, end, attendees,
                                          iv["location_type"], iv.get("location_text", ""))
    update = {"status": "scheduled", "start": naive(start), "end": naive(end), "provider": conn["provider"],
              "provider_event_id": event["event_id"], "join_url": event["join_url"], "offered_slots": []}
    iv = await db.interviews.find_one_and_update({"_id": iv["_id"]}, {"$set": update, **_history("scheduled", by)},
                                                 return_document=ReturnDocument.AFTER)
    moved = await db.applications.update_one(
        {"job_id": iv["job_id"], "candidate_id": iv["candidate_id"], "status": {"$in": EARLY_STATUSES}},
        {"$set": {"status": "Interview", "updated_at": datetime.utcnow()}})
    return {"interview": _out(iv), "email": await _email_candidate(iv, "scheduled", tz),
            "slack": await _notify_slack(iv, "booked"), "candidate_status": "Interview" if moved.modified_count else None}


async def _new_interview(job: dict, candidate_id: str, body: _Where, m: dict, user: AuthUser, status: str) -> dict:
    cand = await _candidate(str(job["_id"]), candidate_id)
    interviewers = await _interviewers(m["org_id"], body.interviewer_uids)
    org = await db.orgs.find_one({"_id": ObjectId(m["org_id"])}, {"name": 1}) or {}
    doc = {
        "org_id": m["org_id"], "job_id": str(job["_id"]), "job_title": job.get("job_title") or "a role",
        "org_name": org.get("name") or "the team", "candidate_id": candidate_id, "candidate_name": cand["name"],
        "candidate_email": cand["email"], "interviewer_uids": [i["uid"] for i in interviewers],
        "interviewers": interviewers, "organizer_uid": user.uid, "organizer_name": user.name or user.email,
        "timezone": body.timezone, "duration_minutes": body.duration_minutes, "location_type": body.location_type,
        "location_text": body.location_text.strip(), "status": status, "created_at": datetime.utcnow(),
        "history": [{"at": datetime.utcnow(), "action": "created", "by": user.uid}],
    }
    doc["_id"] = (await db.interviews.insert_one(doc)).inserted_id
    return doc


def _provider_error(exc: ProviderError) -> HTTPException:
    return HTTPException(502, str(exc))


# ── Routes (signed in) ──────────────────────────────────────────────────

@router.post("/jobs/{job_id}/candidates/{candidate_id}/interviews/availability")
async def availability(job_id: str, candidate_id: str, body: AvailabilityIn,
                       job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """Common free slots of the interviewers whose calendars are connected; the others are listed as not checked."""
    m = await require_scheduler(user)
    rate_limit(user.uid, "availability")
    await _candidate(job_id, candidate_id)
    if body.end_date < body.start_date or (body.end_date - body.start_date).days >= MAX_RANGE_DAYS:
        raise HTTPException(400, f"Pick a date range of 1 to {MAX_RANGE_DAYS} days")
    if body.work_end <= body.work_start:
        raise HTTPException(400, "Working hours must end after they start")
    people = await _interviewers(m["org_id"], body.interviewer_uids)
    zone = ZoneInfo(body.timezone)
    start = datetime.combine(body.start_date, time(0), zone).astimezone(timezone.utc)
    end = datetime.combine(body.end_date + timedelta(days=1), time(0), zone).astimezone(timezone.utc)
    busy, unchecked = await _busy_by_person(m["org_id"], people, start, end)
    slots = scheduling.free_slots([b for intervals in busy.values() for b in intervals], body.start_date,
                                  body.end_date, body.timezone, body.work_start, body.work_end,
                                  body.duration_minutes, body.include_weekends)
    return {"slots": [{"start": iso(s), "end": iso(e)} for s, e in slots],
            "checked": [{"uid": p["uid"], "name": p.get("name")} for p in people if p["uid"] in busy],
            "unchecked": unchecked, "timezone": body.timezone}


@router.post("/jobs/{job_id}/candidates/{candidate_id}/interviews")
async def book(job_id: str, candidate_id: str, body: BookIn,
               job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """Book a slot now on the caller's calendar and invite interviewers + candidate."""
    m = await require_scheduler(user)
    rate_limit(user.uid, "booking")
    await _organizer_connection(user.uid, m["org_id"])
    start = utc(body.start)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(400, "Pick a time in the future")
    people = await _interviewers(m["org_id"], body.interviewer_uids)
    busy = await _conflicts(m["org_id"], people, start, start + timedelta(minutes=body.duration_minutes))
    if busy:
        raise HTTPException(409, f"That time is no longer free for {', '.join(busy)}")
    iv = await _new_interview(job, candidate_id, body, m, user, "booking")
    try:
        return await _book(iv, start, user.uid)
    except ProviderError as exc:
        await db.interviews.delete_one({"_id": iv["_id"]})
        raise _provider_error(exc)


@router.post("/jobs/{job_id}/candidates/{candidate_id}/interviews/link")
async def create_link(job_id: str, candidate_id: str, body: LinkIn,
                      job: dict = Depends(require_job_owner), user: AuthUser = Depends(get_current_user)):
    """Offer slots to the candidate through a public link; the link is shown once (only its hash is kept)."""
    m = await require_scheduler(user)
    rate_limit(user.uid, "booking")
    await _organizer_connection(user.uid, m["org_id"])
    now = datetime.now(timezone.utc)
    slots = sorted({utc(s) for s in body.slots if utc(s) > now})
    if not slots:
        raise HTTPException(400, "Offer at least one time in the future")
    iv = await _new_interview(job, candidate_id, body, m, user, "proposed")
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(days=body.expires_in_days)
    iv = await db.interviews.find_one_and_update(
        {"_id": iv["_id"]},
        {"$set": {"token_hash": _hash(token), "offered_slots": [naive(s) for s in slots], "token_expires_at": naive(expires)}},
        return_document=ReturnDocument.AFTER)
    url = schedule_url(token)
    email = await _email_candidate(iv, "link", link=url)
    return {"interview": _out(iv), "url": url, "email": email}


@router.get("/interviews")
async def list_interviews(job_id: Optional[str] = None, mine: bool = False, user: AuthUser = Depends(get_current_user)):
    """Upcoming interviews of the workspace (scheduled, and proposed links not yet expired)."""
    m = await membership(user)
    now = datetime.utcnow()
    q = {"org_id": m["org_id"], "$or": [{"status": "scheduled", "end": {"$gte": now}},
                                        {"status": {"$in": ["proposed", "booking"]}, "token_expires_at": {"$gt": now}}]}
    if job_id:
        q["job_id"] = str(job_id)
    if mine:
        q = {"$and": [q, {"$or": [{"organizer_uid": user.uid}, {"interviewer_uids": user.uid}]}]}
    docs = await db.interviews.find(q).to_list(500)
    docs.sort(key=lambda d: d.get("start") or (d.get("offered_slots") or [d.get("created_at")])[0])
    return {"interviews": [_out(d) for d in docs]}


@router.patch("/interviews/{interview_id}")
async def reschedule(interview_id: str, body: RescheduleIn, user: AuthUser = Depends(get_current_user)):
    m, iv = await _interview(interview_id, user)
    rate_limit(user.uid, "booking")
    if iv["status"] != "scheduled":
        raise HTTPException(409, "Only scheduled interviews can be moved")
    start = utc(body.start)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(400, "Pick a time in the future")
    duration = body.duration_minutes or iv["duration_minutes"]
    end = start + timedelta(minutes=duration)
    busy = await _conflicts(m["org_id"], iv["interviewers"], start, end, ignore=(utc(iv["start"]), utc(iv["end"])))
    if busy:
        raise HTTPException(409, f"That time isn't free for {', '.join(busy)}")
    conn = await integrations.calendar_connection(iv["organizer_uid"], m["org_id"])
    if not conn:
        raise HTTPException(400, "The organizer's calendar is no longer connected")
    try:
        await scheduling.move_event(conn, iv["provider_event_id"], start, end)
    except ProviderError as exc:
        raise _provider_error(exc)
    iv = await db.interviews.find_one_and_update(
        {"_id": iv["_id"]},
        {"$set": {"start": naive(start), "end": naive(end), "duration_minutes": duration},
         **_history("rescheduled", user.uid, previous_start=iv["start"])},
        return_document=ReturnDocument.AFTER)
    return {"interview": _out(iv), "email": await _email_candidate(iv, "rescheduled"),
            "slack": await _notify_slack(iv, "rescheduled")}


@router.post("/interviews/{interview_id}/cancel")
async def cancel(interview_id: str, user: AuthUser = Depends(get_current_user)):
    m, iv = await _interview(interview_id, user)
    if iv["status"] not in ("proposed", "scheduled"):
        raise HTTPException(409, "This interview can't be cancelled")
    was_scheduled = iv["status"] == "scheduled"
    if was_scheduled and iv.get("provider_event_id"):
        conn = await integrations.calendar_connection(iv["organizer_uid"], m["org_id"])
        if conn:
            try:
                await scheduling.cancel_event(conn, iv["provider_event_id"])
            except ProviderError as exc:
                if "HTTP 404" not in str(exc) and "HTTP 410" not in str(exc):  # already deleted there
                    raise _provider_error(exc)
    iv = await db.interviews.find_one_and_update(
        {"_id": iv["_id"]}, {"$set": {"status": "cancelled"}, "$unset": {"token_hash": ""}, **_history("cancelled", user.uid)},
        return_document=ReturnDocument.AFTER)
    out = {"interview": _out(iv)}
    if was_scheduled:
        out["email"] = await _email_candidate(iv, "cancelled")
        out["slack"] = await _notify_slack(iv, "cancelled")
    return out


# ── Candidate's scheduling page (public) ────────────────────────────────

def _client_key(request: Request) -> str:
    return f"ip:{request.client.host if request.client else '?'}"


async def _by_token(token: str) -> dict:
    iv = await db.interviews.find_one({"token_hash": _hash(token)}) if 20 <= len(token) <= 100 else None
    if not iv or iv["status"] == "cancelled":
        raise HTTPException(404, "This scheduling link isn't valid")
    return iv


def _public_out(iv: dict) -> dict:
    """Only what the candidate needs: no ids, emails or other candidates' data."""
    now = datetime.now(timezone.utc)
    out = {"job_title": iv.get("job_title"), "workspace": iv.get("org_name"),
           "interviewers": [i.get("name") or "Interviewer" for i in iv.get("interviewers", [])],
           "duration_minutes": iv["duration_minutes"], "location_type": iv.get("location_type"),
           "status": "scheduled" if iv["status"] == "scheduled" else "open",
           "expires_at": iso(iv.get("token_expires_at"))}
    if iv["status"] == "scheduled":
        out.update(start=iso(iv["start"]), end=iso(iv["end"]), join_url=iv.get("join_url"))
    else:
        out["slots"] = [iso(s) for s in iv.get("offered_slots", []) if utc(s) > now]
    return out


@public_router.get("/{token}")
async def public_schedule(token: str, request: Request):
    rate_limit(_client_key(request), "public_schedule")
    iv = await _by_token(token)
    if iv["status"] != "scheduled" and utc(iv["token_expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(410, "This scheduling link has expired. Ask the recruiter for a new one.")
    return _public_out(iv)


@public_router.post("/{token}")
async def public_pick(token: str, body: PickIn, request: Request):
    """The candidate books one of the offered slots. Single use: the first successful pick wins."""
    rate_limit(_client_key(request), "public_schedule")
    iv = await _by_token(token)
    now = datetime.now(timezone.utc)
    if iv["status"] == "scheduled":
        raise HTTPException(409, "This interview is already booked")
    if utc(iv["token_expires_at"]) <= now:
        raise HTTPException(410, "This scheduling link has expired. Ask the recruiter for a new one.")
    start = utc(body.start)
    if start <= now or naive(start) not in iv.get("offered_slots", []):
        raise HTTPException(400, "Pick one of the offered times")
    # Claim the link so two picks can't both book
    claimed = await db.interviews.find_one_and_update({"_id": iv["_id"], "status": "proposed"},
                                                      {"$set": {"status": "booking"}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(409, "This interview is already being booked")
    await provider_keys.use_org(iv["org_id"])  # Composio fallback email uses the workspace's key
    try:
        busy = await _conflicts(iv["org_id"], iv["interviewers"], start, start + timedelta(minutes=iv["duration_minutes"]))
        if busy:
            await db.interviews.update_one({"_id": iv["_id"]}, {"$set": {"status": "proposed"},
                                                                "$pull": {"offered_slots": naive(start)}})
            raise HTTPException(409, "That time was just taken. Please pick another.")
        result = await _book(claimed, start, None, body.timezone)
    except ProviderError as exc:
        logger.warning("Self-scheduling booking failed for interview %s: %s", iv["_id"], exc)
        await db.interviews.update_one({"_id": iv["_id"]}, {"$set": {"status": "proposed"}})
        raise HTTPException(502, "We couldn't book this time. Please try again, or contact the recruiter.")
    return _public_out(await db.interviews.find_one({"_id": iv["_id"]})) | {"email_sent": result["email"]["sent"]}
