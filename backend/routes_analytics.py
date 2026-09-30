"""Analytics endpoints (polling fallback + dashboards)."""
from flask import Blueprint, jsonify

from database import db, Event
from auth import login_required, role_required
from analytics.event_analytics import compute_snapshot, rsvp_growth, rsvp_timeline, organizer_summary

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/events/<event_id>/analytics", methods=["GET"])
def event_analytics(event_id):
    snap = compute_snapshot(event_id)
    if not snap:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    return jsonify(snap)


@analytics_bp.route("/events/<event_id>/analytics/detail", methods=["GET"])
@login_required
def event_analytics_detail(user, event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    if ev.organizer_id != user.id and user.role != "admin":
        return jsonify({"error": "forbidden", "message": "Only the organizer can view details"}), 403
    return jsonify({"snapshot": compute_snapshot(event_id), "growth": rsvp_growth(event_id),
                    "timeline": rsvp_timeline(event_id)})


@analytics_bp.route("/organizer/summary", methods=["GET"])
@role_required("organizer", "admin")
def summary(user):
    return jsonify(organizer_summary(user.id))
