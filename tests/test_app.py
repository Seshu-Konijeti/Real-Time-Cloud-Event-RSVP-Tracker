"""
Automated test suite. Test IDs T01-T25 map to the test matrix (docs/test_matrix.md).
Docstring format:  Scenario | Input | Expected
"""
import os, sys, json, threading
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "backend")); sys.path.insert(0, ROOT)
import pytest
from sqlalchemy.exc import IntegrityError
from app import create_app
from database import db, Event, RSVP
from middleware import reset_rate_limits
from realtime.realtime_service import broker
import cloud.notification_service as ns


@pytest.fixture()
def app(tmp_path):
    reset_rate_limits()
    yield create_app({"TESTING": True, "RATELIMIT_ENABLED": False,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'t.db'}"})


def anon(app):
    c = app.test_client()
    c.environ_base["HTTP_X_REQUESTED_WITH"] = "fetch"
    return c


def user(app, name, role="attendee"):
    c = anon(app)
    r = c.post("/api/register", json={"name": name, "email": f"{name}@t.com", "password": "secret1", "role": role})
    assert r.status_code == 201, r.get_json()
    return c


def mkevent(org, cap=100, **kw):
    p = {"event_name": "Workshop", "event_date": "2030-01-01", "start_time": "10:00",
         "end_time": "11:00", "maximum_capacity": cap}
    p.update(kw)
    r = org.post("/api/events", json=p)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["event"]["id"]


def rsvp(c, eid, status, **kw):
    return c.post(f"/api/events/{eid}/rsvp", json={"status": status}, **kw)


def stats(c, eid):
    return c.get(f"/api/events/{eid}/analytics").get_json()



def test_T01_register(app):
    """User registration | name,email,password | 201 and user returned"""
    r = anon(app).post("/api/register", json={"name": "a", "email": "a@t.com", "password": "secret1"})
    assert r.status_code == 201 and r.get_json()["user"]["role"] == "attendee"


def test_T02_duplicate_registration(app):
    """Duplicate registration | same email twice | 409 conflict"""
    user(app, "a")
    r = anon(app).post("/api/register", json={"name": "a", "email": "a@t.com", "password": "secret1"})
    assert r.status_code == 409


def test_T03_login(app):
    """Login | valid and invalid password | 200 valid, 401 invalid"""
    user(app, "a")
    c = anon(app)
    assert c.post("/api/login", json={"email": "a@t.com", "password": "bad"}).status_code == 401
    assert c.post("/api/login", json={"email": "a@t.com", "password": "secret1"}).status_code == 200


def test_T04_organizer_creates_event(app):
    """Organizer creates event | valid payload | 201, status PUBLISHED"""
    o = user(app, "o", "organizer")
    r = o.post("/api/events", json={"event_name": "W", "event_date": "2030-01-01",
                                    "start_time": "10:00", "end_time": "11:00", "maximum_capacity": 5})
    assert r.status_code == 201 and r.get_json()["event"]["status"] == "PUBLISHED"
    bad = o.post("/api/events", json={"event_name": "W", "event_date": "2030-01-01",
                                      "start_time": "12:00", "end_time": "11:00"})
    assert bad.status_code == 400


def test_T05_attendee_cannot_create_event(app):
    """Attendee blocked from organizer API | POST /events as attendee | 403"""
    a = user(app, "a")
    assert a.post("/api/events", json={"event_name": "x", "event_date": "2030-01-01"}).status_code == 403


def test_T06_event_retrieval(app):
    """Event retrieval | GET /events and /events/{id} | event present, unknown id 404"""
    o = user(app, "o", "organizer"); eid = mkevent(o)
    pub = anon(app)
    assert any(e["id"] == eid for e in pub.get("/api/events").get_json()["events"])
    assert pub.get(f"/api/events/{eid}").status_code == 200
    assert pub.get("/api/events/nope").status_code == 404


def test_T07_valid_rsvp(app):
    """Valid RSVP | GOING | 200, going=1, confirmation notification"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    assert rsvp(a, eid, "GOING").status_code == 200
    assert stats(a, eid)["going"] == 1
    assert any(n["type"] == "rsvp_confirmation" for n in a.get("/api/notifications").get_json()["notifications"])


def test_T08_duplicate_rsvp_prevented(app):
    """Duplicate RSVP prevention | same RSVP twice + raw duplicate insert | count stays 1, DB rejects duplicate row"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    rsvp(a, eid, "GOING"); rsvp(a, eid, "GOING")
    assert stats(a, eid)["going"] == 1
    with app.app_context():
        r = RSVP.query.filter_by(event_id=eid).first()
        db.session.add(RSVP(event_id=eid, user_id=r.user_id, status="MAYBE"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_T09_going_to_maybe(app):
    """Update GOING to MAYBE | change RSVP | going 0, maybe 1"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    rsvp(a, eid, "GOING"); rsvp(a, eid, "MAYBE")
    s = stats(a, eid); assert (s["going"], s["maybe"]) == (0, 1)


def test_T10_maybe_to_going(app):
    """Update MAYBE to GOING | change RSVP | going 1, maybe 0"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    rsvp(a, eid, "MAYBE"); rsvp(a, eid, "GOING")
    s = stats(a, eid); assert (s["going"], s["maybe"]) == (1, 0)


def test_T11_cancel_rsvp(app):
    """Cancel RSVP | DELETE /rsvp | going back to 0, second cancel 404"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    rsvp(a, eid, "GOING")
    assert a.delete(f"/api/events/{eid}/rsvp").status_code == 200
    assert stats(a, eid)["going"] == 0
    assert a.delete(f"/api/events/{eid}/rsvp").status_code == 404


def test_T12_registration_deadline(app):
    """Registration deadline | RSVP after deadline | 400 deadline_passed"""
    o = user(app, "o", "organizer"); eid = mkevent(o, registration_deadline="2000-01-01"); a = user(app, "a")
    r = rsvp(a, eid, "GOING")
    assert r.status_code == 400 and r.get_json()["error"] == "deadline_passed"


def test_T13_capacity_enforcement(app):
    """Capacity enforcement | 3rd GOING on capacity 2 | 409 event_full, status FULL, waitlist 1"""
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=2)
    us = [user(app, f"u{i}") for i in range(3)]
    assert rsvp(us[0], eid, "GOING").status_code == 200
    assert rsvp(us[1], eid, "GOING").status_code == 200
    r = rsvp(us[2], eid, "GOING")
    assert r.status_code == 409 and r.get_json()["error"] == "event_full"
    s = stats(o, eid)
    assert s["going"] == 2 and s["waitlist_size"] == 1 and s["status"] == "FULL"


def test_T14_simultaneous_final_seat(app):
    """Simultaneous final-seat requests | 12 threads, 3 seats | going never exceeds 3"""
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=3)
    cs = [user(app, f"u{i}") for i in range(12)]
    ts = [threading.Thread(target=lambda c=c: rsvp(c, eid, "GOING")) for c in cs]
    [t.start() for t in ts]; [t.join() for t in ts]
    with app.app_context():
        assert db.session.get(Event, eid).going_count == 3
    assert stats(o, eid)["waitlist_size"] == 9


def test_T15_waitlist_promotion(app):
    """Waitlist FIFO promotion | GOING cancels | first waiting user promoted and notified"""
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=1)
    a, b, c = user(app, "a"), user(app, "b"), user(app, "c")
    rsvp(a, eid, "GOING"); rsvp(b, eid, "GOING"); rsvp(c, eid, "GOING")   # b then c waiting
    a.delete(f"/api/events/{eid}/rsvp")
    s = stats(o, eid); assert s["going"] == 1 and s["waitlist_size"] == 1
    assert any(n["type"] == "waitlist_promotion" for n in b.get("/api/notifications").get_json()["notifications"])
    assert not any(n["type"] == "waitlist_promotion" for n in c.get("/api/notifications").get_json()["notifications"])


def test_T16_announcement(app):
    """Announcement creation | organizer posts | 201, visible to attendees"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a"); rsvp(a, eid, "GOING")
    r = o.post(f"/api/events/{eid}/announcements", json={"title": "Venue", "message": "Room 5"})
    assert r.status_code == 201
    assert a.get(f"/api/events/{eid}/announcements").get_json()["announcements"][0]["title"] == "Venue"
    assert a.get("/api/updates/me").get_json()["updates"][0]["event_name"] == "Workshop"


def test_T17_notification_generation(app):
    """Notification generation | announcement, venue change, mark read | notifications created and markable read"""
    o = user(app, "o", "organizer"); eid = mkevent(o, venue="A"); a = user(app, "a"); rsvp(a, eid, "GOING")
    o.post(f"/api/events/{eid}/announcements", json={"title": "Hi", "message": "m"})
    o.put(f"/api/events/{eid}", json={"venue": "B"})
    types = [n["type"] for n in a.get("/api/notifications").get_json()["notifications"]]
    assert "organizer_announcement" in types and "venue_change" in types
    nid = a.get("/api/notifications").get_json()["notifications"][0]["id"]
    assert a.put(f"/api/notifications/{nid}/read").status_code == 200
    assert a.get("/api/notifications").get_json()["unread_count"] >= 1


def test_T18_unauthorized_event_modification(app):
    """Unauthorized event modification | other organizer / attendee edits, cancels, deletes | 403"""
    o1, o2, a = user(app, "o1", "organizer"), user(app, "o2", "organizer"), user(app, "a")
    eid = mkevent(o1)
    assert o2.put(f"/api/events/{eid}", json={"event_name": "hack"}).status_code == 403
    assert o2.put(f"/api/events/{eid}/cancel").status_code == 403
    assert o2.delete(f"/api/events/{eid}").status_code == 403
    assert a.put(f"/api/events/{eid}", json={"event_name": "hack"}).status_code == 403
    assert a.get(f"/api/events/{eid}/rsvps").status_code == 403
    assert anon(app).put(f"/api/events/{eid}", json={}).status_code == 401


def test_T19_unauthorized_rsvp_modification(app):
    """Unauthorized RSVP modification | user B deletes/edits A's RSVP, forged counts | A's RSVP untouched, counters backend-owned"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a, b = user(app, "a"), user(app, "b")
    rsvp(a, eid, "GOING")
    assert b.delete(f"/api/events/{eid}/rsvp").status_code == 404      # B has no RSVP; cannot touch A's
    assert stats(a, eid)["going"] == 1
    r = b.post(f"/api/events/{eid}/rsvp", json={"status": "MAYBE", "going_count": 999, "user_id": "x"})
    assert r.status_code == 200
    s = stats(a, eid); assert (s["going"], s["maybe"]) == (1, 1)         # forged fields ignored
    assert anon(app).post(f"/api/events/{eid}/rsvp", json={"status": "GOING"}).status_code == 401


def test_T20_realtime_counter_update(app):
    """Real-time counter update | RSVP with a subscriber connected | subscriber receives pushed going=1 then going=2"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a, b = user(app, "a"), user(app, "b")
    q = broker.subscribe(eid)
    try:
        rsvp(a, eid, "GOING"); rsvp(b, eid, "MAYBE"); rsvp(b, eid, "GOING")
        msgs = [json.loads(q.get_nowait()) for _ in range(q.qsize())]
        assert msgs[0]["going"] == 1 and msgs[-1]["going"] == 2 and msgs[-1]["maybe"] == 0
    finally:
        broker.unsubscribe(eid, q)


def test_T21_analytics_calculation(app):
    """Analytics calculation | 4 invited, 2 responded (1 going,1 maybe), cap 4 | response 50%, conversion 50%, utilization 25%, seats 3"""
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=4)
    a, b = user(app, "a"), user(app, "b"); user(app, "c"); user(app, "d")
    assert o.post(f"/api/events/{eid}/invites",
                  json={"emails": ["a@t.com", "b@t.com", "c@t.com", "d@t.com"]}).get_json()["added"] == 4
    rsvp(a, eid, "GOING"); rsvp(b, eid, "MAYBE")
    s = stats(o, eid)
    assert s["response_rate_percent"] == 50.0 and s["rsvp_conversion_percent"] == 50.0
    assert s["capacity_utilization_percent"] == 25.0 and s["available_seats"] == 3
    d = o.get(f"/api/events/{eid}/analytics/detail").get_json()
    assert d["growth"][-1]["cumulative"] == 2 and len(d["timeline"]) == 2
    summ = o.get("/api/organizer/summary").get_json()
    assert summ["total_events"] == 1 and summ["going"] == 1 and summ["total_invitees"] == 4


def test_T22_database_failure(app, monkeypatch):
    """Database failure | commit raises mid-RSVP | graceful 500 JSON, transaction rolled back, counters unchanged"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    def boom(*x, **y): raise RuntimeError("db down")
    monkeypatch.setattr(db.session, "commit", boom)
    r = rsvp(a, eid, "GOING")
    assert r.status_code == 500 and r.get_json()["error"] == "server_error"
    monkeypatch.undo()
    assert stats(a, eid)["going"] == 0
    assert rsvp(a, eid, "GOING").status_code == 200                       # recovers after DB is back


def test_T23_realtime_connection_failure(app):
    """Real-time connection failure | dead/slow subscriber, then reconnect | RSVP still succeeds, reconnect gets fresh state"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    dead = broker.subscribe(eid, maxsize=1)                                 # never read: fills up
    try:
        assert rsvp(a, eid, "GOING").status_code == 200
        assert rsvp(a, eid, "MAYBE").status_code == 200                     # queue full -> dropped, no error
    finally:
        broker.unsubscribe(eid, dead)
    assert broker.subscriber_count(eid) == 0
    resp = o.get(f"/api/events/{eid}/stream", buffered=False)               # client reconnects
    chunks = resp.response
    next(chunks)                                                            # retry hint
    first = next(chunks).decode()
    assert '"maybe": 1' in first
    resp.close()


def test_T24_token_expiry(app):
    """Authentication token expiry | session cleared/expired | protected APIs return 401 until re-login"""
    a = user(app, "a")
    assert a.get("/api/rsvps/me").status_code == 200
    with a.session_transaction() as s:
        s.clear()
    r = a.get("/api/rsvps/me")
    assert r.status_code == 401
    assert a.post("/api/login", json={"email": "a@t.com", "password": "secret1"}).status_code == 200
    assert a.get("/api/rsvps/me").status_code == 200


def test_T25_event_cancellation(app):
    """Event cancellation | organizer cancels | status CANCELLED, attendees notified, new RSVP rejected"""
    o = user(app, "o", "organizer"); eid = mkevent(o); a, b = user(app, "a"), user(app, "b")
    rsvp(a, eid, "GOING")
    assert o.put(f"/api/events/{eid}/cancel").get_json()["event"]["status"] == "CANCELLED"
    assert any(n["type"] == "event_cancellation" for n in a.get("/api/notifications").get_json()["notifications"])
    assert rsvp(b, eid, "GOING").status_code == 400


# ---------------- extra hardening tests ----------------
def test_X_csrf_header_required(app):
    c = app.test_client()
    assert c.post("/api/login", json={"email": "a", "password": "b"}).status_code == 403


def test_X_rate_limit(tmp_path):
    reset_rate_limits()
    app = create_app({"TESTING": True, "RATELIMIT_ENABLED": True, "RATELIMIT_LOGIN": 3,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'r.db'}"})
    c = anon(app)
    codes = [c.post("/api/login", json={"email": "x@t.com", "password": "y"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3] == 429
    reset_rate_limits()


def test_X_idempotency_key_replay(app):
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=1); a, b = user(app, "a"), user(app, "b")
    h = {"Idempotency-Key": "abc-123"}
    r1 = rsvp(a, eid, "GOING", headers=h); r2 = rsvp(a, eid, "GOING", headers=h)
    assert r1.status_code == r2.status_code == 200 and stats(a, eid)["going"] == 1
    w1 = rsvp(b, eid, "GOING", headers={"Idempotency-Key": "k2"}); w2 = rsvp(b, eid, "GOING", headers={"Idempotency-Key": "k2"})
    assert w1.status_code == w2.status_code == 409 and stats(a, eid)["waitlist_size"] == 1


def test_X_email_failure_does_not_block(app, monkeypatch):
    def boom(*a, **k): raise RuntimeError("smtp down")
    monkeypatch.setattr(ns, "_send_email", boom)
    o = user(app, "o", "organizer"); eid = mkevent(o); a = user(app, "a")
    assert rsvp(a, eid, "GOING").status_code == 200


def test_X_capacity_increase_promotes_waitlist(app):
    o = user(app, "o", "organizer"); eid = mkevent(o, cap=1)
    a, b = user(app, "a"), user(app, "b"); rsvp(a, eid, "GOING"); rsvp(b, eid, "GOING")
    assert o.put(f"/api/events/{eid}", json={"maximum_capacity": 2}).status_code == 200
    s = stats(o, eid); assert s["going"] == 2 and s["waitlist_size"] == 0
    assert o.put(f"/api/events/{eid}", json={"maximum_capacity": 1}).status_code == 400


def test_X_admin_apis(app):
    a = user(app, "a"); o = user(app, "o", "organizer")
    assert a.get("/api/admin/stats").status_code == 403 and o.get("/api/admin/stats").status_code == 403
    with app.app_context():
        from database import User
        u = User.query.filter_by(email="a@t.com").first(); u.role = "admin"; db.session.commit()
    assert a.get("/api/admin/stats").get_json()["users"] == 2
    eid = mkevent(o)
    assert a.put(f"/api/admin/events/{eid}/moderate", json={"status": "CANCELLED"}).status_code == 200
    assert a.get("/api/admin/audit").status_code == 200


def test_X_draft_hidden_and_time_change_notifies(app):
    o = user(app, "o", "organizer"); eid = mkevent(o, status="DRAFT"); a = user(app, "a")
    assert a.get(f"/api/events/{eid}").status_code == 404 and o.get(f"/api/events/{eid}").status_code == 200
    assert rsvp(a, eid, "GOING").status_code == 404
    o.put(f"/api/events/{eid}", json={"status": "PUBLISHED"})
    rsvp(a, eid, "GOING")
    o.put(f"/api/events/{eid}", json={"start_time": "12:00", "end_time": "13:00"})
    assert any(n["type"] == "time_change" for n in a.get("/api/notifications").get_json()["notifications"])
    assert o.post(f"/api/events/{eid}/reminder").get_json()["notified"] == 1
