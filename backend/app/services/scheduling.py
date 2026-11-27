"""
Interview scheduling: free/busy lookups, common free slots, and calendar events + mail
through the user's Google (Calendar, Gmail) or Microsoft (Graph) connection.

All datetimes here are timezone-aware UTC; MongoDB stores them naive UTC (``naive``).
"""
import base64
import uuid
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
from typing import Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.services.integrations import api

GOOGLE_CAL = "https://www.googleapis.com/calendar/v3"
GRAPH = "https://graph.microsoft.com/v1.0"
SLOT_STEP_MINUTES = 30
MAX_SLOTS = 200

Interval = Tuple[datetime, datetime]


def utc(dt: datetime) -> datetime:
    """Aware UTC; naive input is taken as UTC (how MongoDB returns it)."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def naive(dt: datetime) -> datetime:
    return utc(dt).replace(tzinfo=None)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return utc(dt).isoformat().replace("+00:00", "Z") if dt else None


def _parse(value: str) -> datetime:
    # Graph sends 7 fractional digits and no offset ("2026-11-27T09:00:00.0000000")
    if "." in value and not value.endswith("Z") and "+" not in value[19:]:
        value = value[:26]
    return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def free_slots(busy: Iterable[Interval], start_date: date, end_date: date, tz: str, work_start: time,
               work_end: time, duration: int, include_weekends: bool = False, now: Optional[datetime] = None,
               step: int = SLOT_STEP_MINUTES, limit: int = MAX_SLOTS) -> List[Interval]:
    """Start/end of every ``duration``-minute slot inside working hours (in ``tz``) that overlaps no busy interval."""
    zone, now = ZoneInfo(tz), utc(now or datetime.now(timezone.utc))
    busy = sorted((utc(s), utc(e)) for s, e in busy)
    length, slots, day = timedelta(minutes=duration), [], start_date
    while day <= end_date and len(slots) < limit:
        if include_weekends or day.weekday() < 5:
            # Local wall-clock times, so working hours stay right across DST changes
            start = datetime.combine(day, work_start, zone).astimezone(timezone.utc)
            close = datetime.combine(day, work_end, zone).astimezone(timezone.utc)
            while start + length <= close and len(slots) < limit:
                end = start + length
                if start > now and not any(s < end and start < e for s, e in busy):
                    slots.append((start, end))
                start += timedelta(minutes=step)
        day += timedelta(days=1)
    return slots


async def busy(conn: dict, start: datetime, end: datetime) -> List[Interval]:
    """Busy intervals on the connected user's primary calendar."""
    if conn["provider"] == "google":
        data = await api(conn, "POST", f"{GOOGLE_CAL}/freeBusy", "read free/busy",
                         json={"timeMin": iso(start), "timeMax": iso(end), "items": [{"id": "primary"}]})
        cal = (data.get("calendars") or {}).get("primary") or {}
        return [(_parse(b["start"]), _parse(b["end"])) for b in cal.get("busy", [])]
    data = await api(conn, "POST", f"{GRAPH}/me/calendar/getSchedule", "read free/busy",
                     headers={"Prefer": 'outlook.timezone="UTC"'},
                     json={"schedules": [conn["email"]], "availabilityViewInterval": 15,
                           "startTime": {"dateTime": naive(start).isoformat(), "timeZone": "UTC"},
                           "endTime": {"dateTime": naive(end).isoformat(), "timeZone": "UTC"}})
    items = ((data.get("value") or [{}])[0]).get("scheduleItems", [])
    return [(_parse(i["start"]["dateTime"]), _parse(i["end"]["dateTime"])) for i in items if i.get("status") != "free"]


def _graph_time(dt: datetime) -> dict:
    return {"dateTime": naive(dt).isoformat(), "timeZone": "UTC"}


async def create_event(conn: dict, summary: str, description: str, start: datetime, end: datetime,
                       attendees: List[dict], location_type: str, location_text: str) -> dict:
    """Event on the organizer's calendar that invites ``attendees`` [{email, name}]. Returns {event_id, join_url}."""
    video = location_type == "video"
    if conn["provider"] == "google":
        body = {"summary": summary, "description": description, "start": {"dateTime": iso(start)},
                "end": {"dateTime": iso(end)}, "attendees": [{"email": a["email"], "displayName": a.get("name") or ""} for a in attendees]}
        if video:
            body["conferenceData"] = {"createRequest": {"requestId": uuid.uuid4().hex,
                                                        "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
        elif location_text:
            body["location"] = location_text
        data = await api(conn, "POST", f"{GOOGLE_CAL}/calendars/primary/events", "create the event",
                         params={"conferenceDataVersion": 1, "sendUpdates": "all"}, json=body)
        return {"event_id": data.get("id"), "join_url": data.get("hangoutLink")}
    body = {"subject": summary, "body": {"contentType": "text", "content": description},
            "start": _graph_time(start), "end": _graph_time(end),
            "attendees": [{"emailAddress": {"address": a["email"], "name": a.get("name") or ""}, "type": "required"} for a in attendees]}
    if video:
        body.update(isOnlineMeeting=True, onlineMeetingProvider="teamsForBusiness")
    elif location_text:
        body["location"] = {"displayName": location_text}
    data = await api(conn, "POST", f"{GRAPH}/me/events", "create the event", json=body)
    return {"event_id": data.get("id"), "join_url": (data.get("onlineMeeting") or {}).get("joinUrl")}


async def move_event(conn: dict, event_id: str, start: datetime, end: datetime) -> None:
    if conn["provider"] == "google":
        await api(conn, "PATCH", f"{GOOGLE_CAL}/calendars/primary/events/{event_id}", "move the event",
                  params={"sendUpdates": "all"}, json={"start": {"dateTime": iso(start)}, "end": {"dateTime": iso(end)}})
    else:
        await api(conn, "PATCH", f"{GRAPH}/me/events/{event_id}", "move the event",
                  json={"start": _graph_time(start), "end": _graph_time(end)})


async def cancel_event(conn: dict, event_id: str) -> None:
    """Delete the event; the provider sends attendees a cancellation."""
    if conn["provider"] == "google":
        await api(conn, "DELETE", f"{GOOGLE_CAL}/calendars/primary/events/{event_id}", "cancel the event",
                  params={"sendUpdates": "all"})
    else:
        await api(conn, "POST", f"{GRAPH}/me/events/{event_id}/cancel", "cancel the event",
                  json={"comment": "This interview was cancelled."})


async def send_mail(conn: dict, to: str, subject: str, text: str) -> None:
    """Plain-text email from the connected account (Gmail API or Graph sendMail)."""
    subject = " ".join(subject.splitlines())
    if conn["provider"] == "google":
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg.set_content(text)
        await api(conn, "POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", "send the email",
                  json={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()})
    else:
        await api(conn, "POST", f"{GRAPH}/me/sendMail", "send the email",
                  json={"message": {"subject": subject, "body": {"contentType": "Text", "content": text},
                                    "toRecipients": [{"emailAddress": {"address": to}}]}, "saveToSentItems": True})


def local_time(dt: datetime, tz: str) -> str:
    return utc(dt).astimezone(ZoneInfo(tz)).strftime("%A %d %B %Y, %H:%M") + f" ({tz})"


if __name__ == "__main__":
    # Monday 2026-11-30, 09:00-11:00 Kolkata, busy 10:00-10:30 local (04:30-05:00 UTC)
    b = [(datetime(2026, 11, 30, 4, 30, tzinfo=timezone.utc), datetime(2026, 11, 30, 5, tzinfo=timezone.utc))]
    s = free_slots(b, date(2026, 11, 30), date(2026, 11, 30), "Asia/Kolkata", time(9), time(11), 30,
                   now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert [x[0].strftime("%H:%M") for x in s] == ["03:30", "04:00", "05:00"], s
    print("scheduling self-check OK")
