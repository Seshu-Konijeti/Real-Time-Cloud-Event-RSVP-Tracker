"""Announcements: organizer -> everyone who RSVPed (or is waitlisted)."""
from flask import Blueprint, request, jsonify

from database import db, Event, Announcement, RSVP
from auth import login_required
from cloud.notification_service import notify_audience
from cloud.database_service import log_audit
from realtime.realtime_service import broker

announcements_bp = Blueprint("announcements", __name__)


@announcements_bp.route("/events/<event_id>/announcements", methods=["POST"])
@login_required
def create_announcement(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if ev.organizer_id != user.id and user.role != "admin":
        return jsonify({"error": "forbidden", "message": "Not your event"}), 403
    d = request.get_json(silent=True) or {}
    title, message = (d.get("title") or "").strip(), (d.get("message") or "").strip()
    if not title or not message:
        return jsonify({"error": "validation_error", "message": "title and message are required"}), 400
    a = Announcement(event_id=event_id, title=title[:200], message=message)
    db.session.add(a)
    n = notify_audience(event_id, "organizer_announcement", f"{ev.event_name}: {title}")
    log_audit(user.id, "announcement", event_id)
    db.session.commit()
    broker.publish(event_id, {"event_id": event_id, "announcement": a.to_dict()})
    return jsonify({"announcement": a.to_dict(), "notified": n}), 201


@announcements_bp.route("/events/<event_id>/announcements", methods=["GET"])
def get_announcements(event_id):
    items = Announcement.query.filter_by(event_id=event_id).order_by(Announcement.created_at.desc()).all()
    return jsonify({"announcements": [a.to_dict() for a in items]})


@announcements_bp.route("/updates/me", methods=["GET"])
@login_required
def my_updates(user):
    """Announcements for events the current user RSVPed to."""
    ids = [r.event_id for r in RSVP.query.filter_by(user_id=user.id).all()]
    if not ids:
        return jsonify({"updates": []})
    rows = (db.session.query(Announcement, Event.event_name).join(Event, Event.id == Announcement.event_id)
            .filter(Announcement.event_id.in_(ids)).order_by(Announcement.created_at.desc()).limit(20).all())
    return jsonify({"updates": [dict(a.to_dict(), event_name=n) for a, n in rows]})
