"""
RSVP System + concurrency-safe capacity + FIFO waitlist + idempotency.

RACE CONDITION (interview favourite):
  naive:   if going < capacity:  going += 1        # read, THEN write
  Two requests both read 99 (<100) before either writes -> both succeed -> 101.
FIX: one atomic conditional UPDATE (cloud/database_service.atomic_increment).
The loser gets rowcount 0 and is waitlisted.
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify

from database import db, Event, RSVP, Waitlist
from auth import login_required
from middleware import rate_limit, idem_get, idem_put
from cloud.database_service import (atomic_increment, refresh_full_status, promote_from_waitlist,
                                    next_waitlist_position, log_audit)
from cloud.notification_service import notify
from realtime.realtime_service import publish_update

rsvp_bp = Blueprint("rsvp", __name__)
VALID = {"GOING", "MAYBE", "NOT_GOING"}
BUCKET = {"GOING": "going_count", "MAYBE": "maybe_count", "NOT_GOING": "not_going_count"}


def _remove_from_waitlist(event_id, user_id):
    wl = Waitlist.query.filter_by(event_id=event_id, user_id=user_id).first()
    if wl:
        db.session.delete(wl)
        atomic_increment(event_id, "waitlist_count", -1)
        return True
    return False


@rsvp_bp.route("/events/<event_id>/rsvp", methods=["POST", "PUT"])
@rate_limit("rsvp", 30)
@login_required
def set_rsvp(user, event_id):
    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        cached = idem_get(user.id, idem_key)
        if cached:                       # duplicate request -> replay the first answer
            return jsonify(cached[1]), cached[0]

    def respond(body, code=200):
        if idem_key:
            idem_put(user.id, idem_key, (code, body))
        return jsonify(body), code

    ev = db.session.get(Event, event_id)
    if not ev or ev.status == "DRAFT":
        return respond({"error": "not_found", "message": "Event not found"}, 404)
    if ev.status in ("CANCELLED", "COMPLETED"):
        return respond({"error": "event_closed", "message": f"Event is {ev.status.lower()}"}, 400)
    if ev.registration_deadline and date.today().isoformat() > ev.registration_deadline:
        return respond({"error": "deadline_passed", "message": "Registration deadline has passed"}, 400)

    new = ((request.get_json(silent=True) or {}).get("status") or "").upper()
    if new not in VALID:
        return respond({"error": "validation_error",
                        "message": "status must be GOING, MAYBE or NOT_GOING"}, 400)

    rsvp = RSVP.query.filter_by(event_id=event_id, user_id=user.id).first()
    old = rsvp.status if rsvp else None
    if old == new:                                   # idempotent: nothing to change
        return respond({"rsvp": rsvp.to_dict(), "event": ev.to_dict()})

    if new == "GOING":
        if not atomic_increment(event_id, "going_count", +1, guard_capacity=True):
            wl = Waitlist.query.filter_by(event_id=event_id, user_id=user.id).first()
            if not wl:
                wl = Waitlist(event_id=event_id, user_id=user.id,
                              position=next_waitlist_position(event_id), status="WAITING")
                db.session.add(wl)
                atomic_increment(event_id, "waitlist_count", +1)
                notify(user.id, event_id, "waitlisted", "Event is full - you joined the waitlist.")
            db.session.commit()
            refresh_full_status(event_id)
            publish_update(event_id)
            return respond({"error": "event_full",
                            "message": "Event is at capacity. You are on the waitlist.",
                            "waitlist": wl.to_dict()}, 409)
    else:
        _remove_from_waitlist(event_id, user.id)     # changed mind while waiting

    if old:
        atomic_increment(event_id, BUCKET[old], -1)
    if new != "GOING":
        atomic_increment(event_id, BUCKET[new], +1)
    _remove_from_waitlist(event_id, user.id) if new == "GOING" else None

    if rsvp:
        rsvp.status, rsvp.updated_at = new, datetime.utcnow()
    else:
        rsvp = RSVP(event_id=event_id, user_id=user.id, status=new)
        db.session.add(rsvp)
    notify(user.id, event_id, "rsvp_confirmation", f"Your RSVP has been recorded: {new}.")
    log_audit(user.id, "rsvp", f"{event_id}:{old}->{new}")
    db.session.commit()
    refresh_full_status(event_id)
    if old == "GOING" and new != "GOING":
        promote_from_waitlist(event_id)
    publish_update(event_id)
    ev = db.session.get(Event, event_id)
    return respond({"rsvp": rsvp.to_dict(), "event": ev.to_dict()})


@rsvp_bp.route("/events/<event_id>/rsvp", methods=["DELETE"])
@login_required
def cancel_rsvp(user, event_id):
    rsvp = RSVP.query.filter_by(event_id=event_id, user_id=user.id).first()
    waited = _remove_from_waitlist(event_id, user.id)
    if not rsvp and not waited:
        db.session.rollback()
        return jsonify({"error": "not_found", "message": "No RSVP to cancel"}), 404
    was_going = False
    if rsvp:
        atomic_increment(event_id, BUCKET[rsvp.status], -1)
        was_going = rsvp.status == "GOING"
        db.session.delete(rsvp)
    log_audit(user.id, "rsvp_cancel", event_id)
    db.session.commit()
    refresh_full_status(event_id)
    if was_going:
        promote_from_waitlist(event_id)
    publish_update(event_id)
    return jsonify({"message": "RSVP cancelled", "event": db.session.get(Event, event_id).to_dict()})


@rsvp_bp.route("/events/<event_id>/rsvps", methods=["GET"])
@login_required
def get_event_rsvps(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if ev.organizer_id != user.id and user.role != "admin":
        return jsonify({"error": "forbidden", "message": "Only the organizer can view attendees"}), 403
    from database import User
    rows = (db.session.query(RSVP, User.name, User.email).join(User, User.id == RSVP.user_id)
            .filter(RSVP.event_id == event_id).all())
    out = [dict(r.to_dict(), name=n, email=e) for r, n, e in rows]
    return jsonify({"rsvps": out})


@rsvp_bp.route("/rsvps/me", methods=["GET"])
@login_required
def get_my_rsvps(user):
    return jsonify({"rsvps": [r.to_dict() for r in RSVP.query.filter_by(user_id=user.id).all()],
                    "waitlist": [w.to_dict() for w in Waitlist.query.filter_by(user_id=user.id).all()]})
