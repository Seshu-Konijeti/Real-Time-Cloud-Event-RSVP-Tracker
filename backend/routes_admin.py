"""Admin-only APIs: platform stats, user management, event moderation."""
from flask import Blueprint, request, jsonify

from database import db, User, Event, RSVP, AuditLog
from auth import role_required
from cloud.database_service import log_audit

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/stats", methods=["GET"])
@role_required("admin")
def stats(user):
    return jsonify({"users": User.query.count(), "events": Event.query.count(),
                    "rsvps": RSVP.query.count(),
                    "organizers": User.query.filter_by(role="organizer").count(),
                    "cancelled_events": Event.query.filter_by(status="CANCELLED").count()})


@admin_bp.route("/admin/users", methods=["GET"])
@role_required("admin")
def users(user):
    return jsonify({"users": [u.to_dict() for u in User.query.order_by(User.created_at.desc()).all()]})


@admin_bp.route("/admin/users/<uid>/role", methods=["PUT"])
@role_required("admin")
def set_role(user, uid):
    role = (request.get_json(silent=True) or {}).get("role")
    if role not in ("attendee", "organizer", "admin"):
        return jsonify({"error": "validation_error", "message": "invalid role"}), 400
    target = db.session.get(User, uid)
    if not target:
        return jsonify({"error": "not_found", "message": "User not found"}), 404
    target.role = role
    log_audit(user.id, "admin_set_role", f"{uid}:{role}")
    db.session.commit()
    return jsonify({"user": target.to_dict()})


@admin_bp.route("/admin/events/<event_id>/moderate", methods=["PUT"])
@role_required("admin")
def moderate(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("DRAFT", "PUBLISHED", "CANCELLED"):
        return jsonify({"error": "validation_error", "message": "status must be DRAFT, PUBLISHED or CANCELLED"}), 400
    ev.status = status
    log_audit(user.id, "admin_moderate", f"{event_id}:{status}")
    db.session.commit()
    return jsonify({"event": ev.to_dict()})


@admin_bp.route("/admin/audit", methods=["GET"])
@role_required("admin")
def audit(user):
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify({"audit": [{"user_id": r.user_id, "action": r.action, "details": r.details,
                               "at": r.created_at.isoformat()} for r in rows]})
