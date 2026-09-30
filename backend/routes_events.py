"""
Event Management Module.
createEvent / updateEvent / deleteEvent / cancelEvent / getEvent / getEvents /
getUpcomingEvents, plus invites and reminders.
"""
from datetime import datetime, date
from flask import Blueprint, request, jsonify

from database import db, Event, RSVP, Waitlist, Announcement, Notification, Invite, User
from auth import login_required, role_required
from cloud.database_service import (log_audit, promote_all_possible, refresh_full_status)
from cloud.notification_service import notify, notify_audience
from realtime.realtime_service import publish_update

events_bp = Blueprint("events", __name__)

STATUSES = {"DRAFT", "PUBLISHED", "FULL", "COMPLETED", "CANCELLED"}
EDITABLE = ("event_name", "description", "event_type", "event_date", "start_time", "end_time",
            "venue", "online_link", "maximum_capacity", "registration_deadline", "status")


def _valid_date(v):
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _validate(data, current=None):
    """Validate the merged view (current values overlaid by payload)."""
    errors = []
    merged = dict(current or {})
    merged.update(data)
    if not (merged.get("event_name") or "").strip():
        errors.append("event_name is required")
    if not _valid_date(merged.get("event_date")):
        errors.append("event_date must be YYYY-MM-DD")
    st, et = merged.get("start_time"), merged.get("end_time")
    if st and et and st >= et:
        errors.append("start_time must be before end_time")
    try:
        if int(merged.get("maximum_capacity", 100)) <= 0:
            errors.append("maximum_capacity must be a positive integer")
    except (TypeError, ValueError):
        errors.append("maximum_capacity must be a positive integer")
    dl = merged.get("registration_deadline")
    if dl:
        if not _valid_date(dl):
            errors.append("registration_deadline must be YYYY-MM-DD")
        elif _valid_date(merged.get("event_date")) and dl > merged["event_date"]:
            errors.append("registration_deadline cannot be after event_date")
    if "status" in data and data["status"] not in STATUSES:
        errors.append("invalid status")
    return errors


def _owner_or_admin(user, event):
    return event.organizer_id == user.id or user.role == "admin"


def _sync_completed():
    today = date.today().isoformat()
    (Event.query.filter(Event.event_date < today, Event.status.in_(["PUBLISHED", "FULL"]))
     .update({"status": "COMPLETED"}, synchronize_session=False))
    db.session.commit()


@events_bp.route("/events", methods=["POST"])
@role_required("organizer", "admin")
def create_event(user):
    data = request.get_json(silent=True) or {}
    errors = _validate(data)
    if errors:
        return jsonify({"error": "validation_error", "message": errors}), 400
    status = data.get("status", "PUBLISHED")
    if status not in ("DRAFT", "PUBLISHED"):
        status = "PUBLISHED"
    ev = Event(organizer_id=user.id, event_name=data["event_name"].strip(),
               description=data.get("description", ""), event_type=data.get("event_type", "general"),
               event_date=data["event_date"], start_time=data.get("start_time", "09:00"),
               end_time=data.get("end_time", "10:00"), venue=data.get("venue", ""),
               online_link=data.get("online_link", ""),
               maximum_capacity=int(data.get("maximum_capacity", 100)),
               registration_deadline=data.get("registration_deadline") or None, status=status)
    db.session.add(ev)
    db.session.flush()
    log_audit(user.id, "event_create", ev.id)
    db.session.commit()
    return jsonify({"event": ev.to_dict()}), 201


@events_bp.route("/events", methods=["GET"])
def get_events():
    _sync_completed()
    q = Event.query
    from auth import current_user
    viewer = current_user()
    status = request.args.get("status")
    if status:
        q = q.filter_by(status=status.upper())
    org = request.args.get("organizer_id")
    if org:
        q = q.filter_by(organizer_id=org)
    if request.args.get("upcoming") == "true":
        q = q.filter(Event.event_date >= date.today().isoformat())
    events = q.order_by(Event.event_date.asc(), Event.start_time.asc()).all()
    # DRAFT events are visible only to their organizer/admin
    events = [e for e in events if e.status != "DRAFT"
              or (viewer and (viewer.id == e.organizer_id or viewer.role == "admin"))]
    return jsonify({"events": [e.to_dict() for e in events]})


@events_bp.route("/events/upcoming", methods=["GET"])
def get_upcoming():
    _sync_completed()
    events = (Event.query.filter(Event.event_date >= date.today().isoformat(),
                                 Event.status.in_(["PUBLISHED", "FULL"]))
              .order_by(Event.event_date.asc()).all())
    return jsonify({"events": [e.to_dict() for e in events]})


@events_bp.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if ev.status == "DRAFT":
        from auth import current_user
        u = current_user()
        if not (u and _owner_or_admin(u, ev)):
            return jsonify({"error": "not_found", "message": "Event not found"}), 404
    return jsonify({"event": ev.to_dict()})


@events_bp.route("/events/<event_id>", methods=["PUT"])
@login_required
def update_event(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    data = request.get_json(silent=True) or {}
    data = {k: v for k, v in data.items() if k in EDITABLE}
    errors = _validate(data, ev.to_dict())
    if errors:
        return jsonify({"error": "validation_error", "message": errors}), 400
    if "maximum_capacity" in data and int(data["maximum_capacity"]) < ev.going_count:
        return jsonify({"error": "validation_error",
                        "message": ["maximum_capacity cannot be below current GOING count"]}), 400
    if data.get("status") == "CANCELLED":
        return jsonify({"error": "validation_error", "message": ["use /cancel to cancel an event"]}), 400

    place_changed = any(k in data and data[k] != getattr(ev, k) for k in ("venue", "online_link"))
    time_changed = any(k in data and data[k] != getattr(ev, k) for k in ("event_date", "start_time", "end_time"))
    cap_changed = "maximum_capacity" in data and int(data["maximum_capacity"]) != ev.maximum_capacity
    for k, v in data.items():
        setattr(ev, k, int(v) if k == "maximum_capacity" else v)
    log_audit(user.id, "event_update", f"{ev.id}:{sorted(data)}")
    db.session.commit()

    if place_changed:
        notify_audience(ev.id, "venue_change", f"{ev.event_name}: venue/link updated.")
    if time_changed:
        notify_audience(ev.id, "time_change",
                        f"{ev.event_name}: now {ev.event_date} {ev.start_time}-{ev.end_time}.")
    db.session.commit()
    if cap_changed:
        refresh_full_status(ev.id)
        promote_all_possible(ev.id)   # extra seats -> pull people off the waitlist
    publish_update(ev.id)
    return jsonify({"event": db.session.get(Event, ev.id).to_dict()})


@events_bp.route("/events/<event_id>/cancel", methods=["PUT"])
@login_required
def cancel_event(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    ev.status = "CANCELLED"
    notify_audience(ev.id, "event_cancellation", f"{ev.event_name} has been cancelled.")
    log_audit(user.id, "event_cancel", ev.id)
    db.session.commit()
    publish_update(ev.id)
    return jsonify({"event": ev.to_dict()})


@events_bp.route("/events/<event_id>", methods=["DELETE"])
@login_required
def delete_event(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    for model in (RSVP, Waitlist, Announcement, Notification, Invite):
        model.query.filter_by(event_id=event_id).delete()
    db.session.delete(ev)
    log_audit(user.id, "event_delete", event_id)
    db.session.commit()
    return jsonify({"message": "Event deleted"})


@events_bp.route("/events/<event_id>/invites", methods=["POST"])
@login_required
def invite(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    emails = (request.get_json(silent=True) or {}).get("emails") or []
    added = 0
    for raw in emails:
        email = str(raw).strip().lower()
        if "@" not in email or Invite.query.filter_by(event_id=event_id, email=email).first():
            continue
        db.session.add(Invite(event_id=event_id, email=email))
        added += 1
        target = User.query.filter_by(email=email).first()
        if target:
            notify(target.id, event_id, "invitation", f"You're invited: {ev.event_name} on {ev.event_date}.")
    log_audit(user.id, "invite", f"{event_id}:{added}")
    db.session.commit()
    publish_update(event_id)
    return jsonify({"added": added}), 201


@events_bp.route("/events/<event_id>/invites", methods=["GET"])
@login_required
def list_invites(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    return jsonify({"invites": [i.to_dict() for i in Invite.query.filter_by(event_id=event_id).all()]})


@events_bp.route("/events/<event_id>/reminder", methods=["POST"])
@login_required
def send_reminder(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if not _owner_or_admin(user, ev):
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    n = notify_audience(ev.id, "event_reminder",
                        f"Reminder: {ev.event_name} on {ev.event_date} at {ev.start_time}.",
                        include_waitlist=False)
    db.session.commit()
    return jsonify({"notified": n})
