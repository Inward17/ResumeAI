"""
Interview scheduling (app/services/scheduling.py, app/routes/scheduling_routes.py):
free-slot intersection, booking, self-scheduling links, reschedule/cancel and access checks.
Provider HTTP goes to tests.test_user_connections.FakeProviders.
"""
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlsplit

import pytest

from tests.conftest import create_owned_job
from tests.test_user_connections import _env, add_member, connect_calendar, fake, org_of, sign_in_as  # noqa: F401 (fixtures)


def next_monday(weeks=1) -> date:
    today = datetime.now(timezone.utc).date()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7) + timedelta(weeks=weeks - 1)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), timezone.utc)


def z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
async def setup(client, mock_db, owned_job_id):
    """Workspace with the signed-in organizer (Google) + Ana (Microsoft) + Ben (no calendar), and one candidate."""
    org_id = await org_of(client, mock_db)
    await mock_db.org_members.update_one({"uid": "test-user"}, {"$set": {"name": "Test User", "email": "tester@example.com"}})
    await add_member(mock_db, org_id, "ana", email="ana@example.com", name="Ana Example")
    await add_member(mock_db, org_id, "ben", email="ben@example.com", name="Ben Example")
    await connect_calendar(mock_db, "test-user", org_id, token="org-token", email="tester@example.com")
    await connect_calendar(mock_db, "ana", org_id, provider="microsoft", token="ana-token", email="ana@example.com")
    await mock_db.applications.insert_one({"job_id": owned_job_id, "candidate_id": "cand-1", "status": "Shortlisted"})
    await mock_db.candidates.insert_one({"candidate_id": "cand-1", "parsed": {"personal_info": {
        "full_name": "Casey Candidate", "email": "casey@example.com", "phone_number": "+1 555 0100"}}})
    await mock_db.jobs.update_one({}, {"$set": {"job_title": "Backend Engineer"}})
    return {"org_id": org_id, "job_id": owned_job_id, "base": f"/api/jobs/{owned_job_id}/candidates/cand-1/interviews"}


def gmail_text(request) -> str:
    import base64, json
    from email import message_from_bytes, policy
    raw = base64.urlsafe_b64decode(json.loads(request.content)["raw"])
    return message_from_bytes(raw, policy=policy.default).get_content()


def book_body(start, **extra):
    return {"interviewer_uids": ["test-user", "ana"], "duration_minutes": 60, "timezone": "Europe/London",
            "start": z(start), **extra}


class TestFreeSlots:
    def test_timezone_working_hours_weekends_and_past(self):
        from app.services.scheduling import free_slots
        fri = date(2026, 12, 4)  # Friday; Kolkata is UTC+5:30
        busy = [(at(fri, 4, 30), at(fri, 5, 0))]
        slots = free_slots(busy, fri, fri + timedelta(days=3), "Asia/Kolkata", time(9), time(11), 30,
                           now=at(fri, 3, 45))
        # 09:00 IST (03:30 UTC) is in the past, 10:00 IST is busy, Sat/Sun skipped, Mon has all four
        assert [z(s) for s, _ in slots] == [z(at(fri, 4)), z(at(fri, 5)),
                                            *[z(at(fri + timedelta(days=3), h, m)) for h, m in ((3, 30), (4, 0), (4, 30), (5, 0))]]
        assert all(e - s == timedelta(minutes=30) for s, e in slots)

    def test_slot_must_fit_and_weekends_optional(self):
        from app.services.scheduling import free_slots
        sat = date(2026, 12, 5)
        assert free_slots([], sat, sat, "UTC", time(9), time(10), 60, now=at(sat, 0)) == []
        assert [z(s) for s, _ in free_slots([], sat, sat, "UTC", time(9), time(10), 60, include_weekends=True,
                                             now=at(sat, 0))] == [z(at(sat, 9))]
        assert free_slots([], sat, sat, "UTC", time(9), time(10), 90, include_weekends=True, now=at(sat, 0)) == []

    def test_dst_change_keeps_local_hours(self):
        from app.services.scheduling import free_slots
        # London moves to BST on 2027-03-28: 09:00 local is 09:00 UTC before, 08:00 UTC after
        before, after = date(2027, 3, 26), date(2027, 3, 29)
        s1 = free_slots([], before, before, "Europe/London", time(9), time(10), 60, now=at(before, 0))
        s2 = free_slots([], after, after, "Europe/London", time(9), time(10), 60, now=at(before, 0))
        assert s1[0][0].hour == 9 and s2[0][0].hour == 8


class TestAvailability:
    async def test_intersection_and_unconnected_interviewers_reported(self, client, setup, fake):
        mon = next_monday()
        fake.busy["org-token"] = [(at(mon, 9), at(mon, 10))]
        fake.busy["ana-token"] = [(at(mon, 11), at(mon, 12, 30))]
        resp = await client.post(f"{setup['base']}/availability", json={
            "interviewer_uids": ["test-user", "ana", "ben"], "duration_minutes": 60, "timezone": "UTC",
            "start_date": mon.isoformat(), "end_date": mon.isoformat(), "work_start": "09:00", "work_end": "14:00"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert [s["start"] for s in body["slots"]] == [z(at(mon, 10)), z(at(mon, 12, 30)), z(at(mon, 13))]
        assert {c["uid"] for c in body["checked"]} == {"test-user", "ana"}
        assert body["unchecked"] == [{"uid": "ben", "name": "Ben Example", "reason": "No calendar connected"}]
        assert fake.calls("graph.microsoft.com", "getSchedule") and fake.calls("www.googleapis.com", "freeBusy")

    async def test_expired_calendar_is_reported(self, client, setup, fake, mock_db):
        await mock_db.user_connections.update_one({"uid": "ana"}, {"$set": {"status": "expired"}})
        mon = next_monday()
        resp = await client.post(f"{setup['base']}/availability", json={
            "interviewer_uids": ["ana"], "duration_minutes": 30, "timezone": "UTC",
            "start_date": mon.isoformat(), "end_date": mon.isoformat()})
        assert "Microsoft calendar access expired" in resp.json()["unchecked"][0]["reason"]

    async def test_bad_input(self, client, setup):
        mon = next_monday()
        base = {"interviewer_uids": ["ana"], "duration_minutes": 30, "start_date": mon.isoformat(), "end_date": mon.isoformat()}
        assert (await client.post(f"{setup['base']}/availability", json={**base, "timezone": "Mars/Base"})).status_code == 422
        assert (await client.post(f"{setup['base']}/availability", json={**base, "end_date": (mon - timedelta(days=1)).isoformat()})).status_code == 400
        assert (await client.post(f"{setup['base']}/availability", json={**base, "interviewer_uids": ["stranger"]})).status_code == 400


class TestBooking:
    async def test_book_creates_event_emails_and_notifies(self, client, setup, fake, mock_db):
        from app.services import provider_keys
        await mock_db.slack_connections.insert_one({"org_id": setup["org_id"], "bot_token": provider_keys.encrypt("xoxb-test"),
                                                    "channel_id": "C0123456"})
        start = at(next_monday(), 14)
        resp = await client.post(setup["base"], json=book_body(start))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        iv = body["interview"]
        assert iv["status"] == "scheduled" and iv["start"] == z(start) and iv["end"] == z(start + timedelta(hours=1))
        assert iv["join_url"] == "https://meet.google.com/abc-defg-hij" and iv["provider"] == "google"

        event = next(r for r in fake.calls("www.googleapis.com", "/events") if r.method == "POST")
        import json
        sent = json.loads(event.content)
        assert {a["email"] for a in sent["attendees"]} == {"tester@example.com", "ana@example.com", "casey@example.com"}
        assert "conferenceData" in sent and event.url.params["sendUpdates"] == "all"
        assert event.headers["authorization"] == "Bearer org-token"

        assert body["email"]["sent"] is True and body["email"]["via"] == "google"
        assert fake.calls("gmail.googleapis.com")
        assert body["slack"]["sent"] is True and body["candidate_status"] == "Interview"
        assert (await mock_db.applications.find_one({"candidate_id": "cand-1"}))["status"] == "Interview"
        stored = await mock_db.interviews.find_one({})
        assert stored["provider_event_id"] == "g-evt" and stored["history"][-1]["action"] == "scheduled"

    async def test_conflict_is_refused(self, client, setup, fake, mock_db):
        start = at(next_monday(), 14)
        fake.busy["ana-token"] = [(start + timedelta(minutes=30), start + timedelta(hours=2))]
        resp = await client.post(setup["base"], json=book_body(start))
        assert resp.status_code == 409 and "Ana Example" in resp.json()["detail"]
        assert not [r for r in fake.calls("www.googleapis.com", "/events") if r.method == "POST"]
        assert await mock_db.interviews.count_documents({}) == 0

    async def test_needs_organizer_calendar_and_future_time(self, client, setup, mock_db):
        assert (await client.post(setup["base"], json=book_body(at(date(2020, 1, 6), 9)))).status_code == 400
        await mock_db.user_connections.delete_many({"uid": "test-user"})
        resp = await client.post(setup["base"], json=book_body(at(next_monday(), 14)))
        assert resp.status_code == 400 and "Settings > Integrations" in resp.json()["detail"]

    async def test_provider_failure_leaves_no_interview(self, client, setup, fake, mock_db):
        from app.services import integrations
        async def boom(*a, **k):
            raise integrations.ProviderError("Google couldn't create the event (HTTP 500).")
        from unittest.mock import patch
        with patch("app.services.scheduling.create_event", boom):
            resp = await client.post(setup["base"], json=book_body(at(next_monday(), 14)))
        assert resp.status_code == 502 and "HTTP 500" in resp.json()["detail"]
        assert await mock_db.interviews.count_documents({}) == 0

    async def test_email_falls_back_to_copyable_text(self, client, setup, fake, mock_db):
        from unittest.mock import AsyncMock, patch
        from app.services import integrations
        with patch("app.services.scheduling.send_mail", AsyncMock(side_effect=integrations.ProviderError("Gmail down"))):
            body = (await client.post(setup["base"], json=book_body(at(next_monday(), 14)))).json()
        email = body["email"]
        assert email["sent"] is False and email["to"] == "casey@example.com"
        assert "Backend Engineer" in email["body"] and "meet.google.com" in email["body"] and "(Europe/London)" in email["body"]


class TestSelfScheduling:
    async def make_link(self, client, setup, slots):
        resp = await client.post(f"{setup['base']}/link", json={
            "interviewer_uids": ["test-user", "ana"], "duration_minutes": 45, "timezone": "UTC",
            "slots": [z(s) for s in slots]})
        assert resp.status_code == 200, resp.text
        return resp.json()

    async def test_link_flow(self, client, anon_client, setup, fake, mock_db):
        mon = next_monday()
        slots = [at(mon, 10), at(mon, 15)]
        out = await self.make_link(client, setup, slots)
        token = urlsplit(out["url"]).path.rsplit("/", 1)[-1]
        assert out["url"].endswith(f"/schedule/{token}") and out["interview"]["status"] == "proposed"
        assert out["email"]["sent"] is True and out["url"] in gmail_text(fake.calls("gmail.googleapis.com")[0])
        stored = await mock_db.interviews.find_one({})
        assert token not in str(stored) and stored["token_hash"]

        page = await anon_client.get(f"/api/public/schedule/{token}")
        assert page.status_code == 200
        data = page.json()
        assert data["slots"] == [z(s) for s in slots] and data["job_title"] == "Backend Engineer"
        assert data["interviewers"] == ["Test User", "Ana Example"]
        text = page.text
        for secret in ("example.com", "cand-1", setup["job_id"], setup["org_id"], "Casey", "+1 555"):
            assert secret not in text

        assert (await anon_client.post(f"/api/public/schedule/{token}", json={"start": z(at(mon, 11))})).status_code == 400
        picked = await anon_client.post(f"/api/public/schedule/{token}", json={"start": z(slots[1]), "timezone": "Asia/Kolkata"})
        assert picked.status_code == 200, picked.text
        assert picked.json()["status"] == "scheduled" and picked.json()["start"] == z(slots[1])
        assert (await mock_db.interviews.find_one({}))["end"] == (slots[1] + timedelta(minutes=45)).replace(tzinfo=None)
        assert "(Asia/Kolkata)" in gmail_text(fake.calls("gmail.googleapis.com")[-1])

        again = await anon_client.post(f"/api/public/schedule/{token}", json={"start": z(slots[0])})
        assert again.status_code == 409
        assert len([r for r in fake.calls("www.googleapis.com", "/events") if r.method == "POST"]) == 1
        assert (await anon_client.get(f"/api/public/schedule/{token}")).json()["status"] == "scheduled"

    async def test_conflict_on_recheck_removes_slot(self, client, anon_client, setup, fake, mock_db):
        mon = next_monday()
        out = await self.make_link(client, setup, [at(mon, 10), at(mon, 15)])
        token = urlsplit(out["url"]).path.rsplit("/", 1)[-1]
        fake.busy["ana-token"] = [(at(mon, 10), at(mon, 11))]  # Ana booked something meanwhile
        resp = await anon_client.post(f"/api/public/schedule/{token}", json={"start": z(at(mon, 10))})
        assert resp.status_code == 409
        page = (await anon_client.get(f"/api/public/schedule/{token}")).json()
        assert page["status"] == "open" and page["slots"] == [z(at(mon, 15))]

    async def test_expired_and_unknown_links(self, client, anon_client, setup, fake, mock_db):
        mon = next_monday()
        out = await self.make_link(client, setup, [at(mon, 10)])
        token = urlsplit(out["url"]).path.rsplit("/", 1)[-1]
        await mock_db.interviews.update_one({}, {"$set": {"token_expires_at": datetime.utcnow() - timedelta(minutes=1)}})
        assert (await anon_client.get(f"/api/public/schedule/{token}")).status_code == 410
        assert (await anon_client.post(f"/api/public/schedule/{token}", json={"start": z(at(mon, 10))})).status_code == 410
        assert (await anon_client.get("/api/public/schedule/" + "x" * 43)).status_code == 404

    async def test_cancelled_link_stops_working(self, client, anon_client, setup, fake):
        out = await self.make_link(client, setup, [at(next_monday(), 10)])
        token = urlsplit(out["url"]).path.rsplit("/", 1)[-1]
        assert (await client.post(f"/api/interviews/{out['interview']['id']}/cancel")).status_code == 200
        assert (await anon_client.get(f"/api/public/schedule/{token}")).status_code == 404

    async def test_public_page_is_rate_limited(self, anon_client, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
        codes = [(await anon_client.get("/api/public/schedule/" + "y" * 43)).status_code for _ in range(4)]
        assert codes == [404, 404, 404, 429]


class TestRescheduleCancel:
    async def booked(self, client, setup, start):
        return (await client.post(setup["base"], json=book_body(start))).json()["interview"]

    async def test_reschedule_moves_event(self, client, setup, fake, mock_db):
        start = at(next_monday(), 14)
        iv = await self.booked(client, setup, start)
        fake.busy["org-token"] = [(start, start + timedelta(hours=1))]  # its own event doesn't count
        new = start + timedelta(days=1)
        resp = await client.patch(f"/api/interviews/{iv['id']}", json={"start": z(new)})
        assert resp.status_code == 200, resp.text
        assert resp.json()["interview"]["start"] == z(new)
        patch_call = next(r for r in fake.calls("www.googleapis.com", "/events/g-evt") if r.method == "PATCH")
        assert z(new) in patch_call.content.decode()
        assert (await mock_db.interviews.find_one({}))["history"][-1]["action"] == "rescheduled"

    async def test_reschedule_conflict(self, client, setup, fake):
        start = at(next_monday(), 14)
        iv = await self.booked(client, setup, start)
        new = start + timedelta(days=1)
        fake.busy["ana-token"] = [(new, new + timedelta(hours=1))]
        assert (await client.patch(f"/api/interviews/{iv['id']}", json={"start": z(new)})).status_code == 409

    async def test_cancel_deletes_event(self, client, setup, fake, mock_db):
        iv = await self.booked(client, setup, at(next_monday(), 14))
        resp = await client.post(f"/api/interviews/{iv['id']}/cancel")
        assert resp.status_code == 200 and resp.json()["interview"]["status"] == "cancelled"
        assert [r for r in fake.calls("www.googleapis.com", "/events/g-evt") if r.method == "DELETE"]
        assert (await client.post(f"/api/interviews/{iv['id']}/cancel")).status_code == 409
        assert (await client.get("/api/interviews")).json()["interviews"] == []

    async def test_cancel_when_event_already_gone(self, client, setup, fake):
        iv = await self.booked(client, setup, at(next_monday(), 14))
        fake.event_status = 410
        assert (await client.post(f"/api/interviews/{iv['id']}/cancel")).status_code == 200


class TestListAndAccess:
    async def test_list_mine_and_by_job(self, client, setup, fake, mock_db):
        from app.auth import AuthUser
        await client.post(setup["base"], json=book_body(at(next_monday(), 14), interviewer_uids=["ana"]))
        assert len((await client.get("/api/interviews")).json()["interviews"]) == 1
        assert len((await client.get(f"/api/interviews?job_id={setup['job_id']}")).json()["interviews"]) == 1
        assert (await client.get("/api/interviews?job_id=other")).json()["interviews"] == []
        sign_in_as(AuthUser(uid="ben", email="ben@example.com", provider="google.com"))
        assert len((await client.get("/api/interviews")).json()["interviews"]) == 1
        assert (await client.get("/api/interviews?mine=true")).json()["interviews"] == []
        sign_in_as(AuthUser(uid="ana", email="ana@example.com", provider="google.com"))
        assert len((await client.get("/api/interviews?mine=true")).json()["interviews"]) == 1

    async def test_other_workspace_is_404(self, client, setup, fake, mock_db):
        from app.auth import AuthUser
        iv = (await client.post(setup["base"], json=book_body(at(next_monday(), 14)))).json()["interview"]
        sign_in_as(AuthUser(uid="mallory", email="mallory@example.com", provider="google.com"))
        await client.get("/api/integrations/me")  # gets her own workspace
        assert (await client.get("/api/interviews")).json()["interviews"] == []
        assert (await client.patch(f"/api/interviews/{iv['id']}", json={"start": z(at(next_monday(2), 9))})).status_code == 404
        assert (await client.post(f"/api/interviews/{iv['id']}/cancel")).status_code == 404
        mon = next_monday()
        resp = await client.post(f"{setup['base']}/availability", json={
            "interviewer_uids": ["ana"], "duration_minutes": 30, "start_date": mon.isoformat(), "end_date": mon.isoformat()})
        assert resp.status_code == 404
        assert (await client.post(setup["base"], json=book_body(at(mon, 14)))).status_code == 404

    async def test_candidate_must_have_applied(self, client, setup, mock_db, fake):
        other = await create_owned_job(mock_db, owner_uid="someone-else")
        await mock_db.applications.insert_one({"job_id": other, "candidate_id": "theirs"})
        resp = await client.post(f"/api/jobs/{setup['job_id']}/candidates/theirs/interviews", json=book_body(at(next_monday(), 14)))
        assert resp.status_code == 404

    async def test_interviewer_from_another_workspace_is_refused(self, client, setup, mock_db, fake):
        await add_member(mock_db, "other-org", "eve", email="eve@example.com")
        resp = await client.post(setup["base"], json=book_body(at(next_monday(), 14), interviewer_uids=["eve"]))
        assert resp.status_code == 400

    async def test_api_keys_cannot_schedule(self, client, setup):
        from app.auth import AuthUser
        sign_in_as(AuthUser(uid="test-user", provider="api_key", org_id=setup["org_id"]))
        assert (await client.post(setup["base"], json=book_body(at(next_monday(), 14)))).status_code == 403
        mon = next_monday()
        assert (await client.post(f"{setup['base']}/availability", json={
            "interviewer_uids": ["ana"], "start_date": mon.isoformat(), "end_date": mon.isoformat()})).status_code == 403
