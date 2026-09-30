"""In-app notifications for the current user."""

from flask import Blueprint, jsonify

from database import db, Notification
from auth import login_required

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/notifications", methods=["GET"])
@login_required
def list_notifications(user):
    items = (Notification.query.filter_by(user_id=user.id)
             .order_by(Notification.created_at.desc()).limit(50).all())
    unread = Notification.query.filter_by(user_id=user.id, read=False).count()
    return jsonify({"notifications": [n.to_dict() for n in items], "unread_count": unread})


@notifications_bp.route("/notifications/<notification_id>/read", methods=["PUT"])
@login_required
def mark_read(user, notification_id):
    n = Notification.query.get(notification_id)
    if not n or n.user_id != user.id:
        return jsonify({"error": "not_found", "message": "Notification not found"}), 404
    n.read = True
    db.session.commit()
    return jsonify({"notification": n.to_dict()})
