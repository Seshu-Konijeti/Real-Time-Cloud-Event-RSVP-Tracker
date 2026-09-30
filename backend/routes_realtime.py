"""Server-Sent Events stream: /api/events/<id>/stream (server -> browser push)."""
import json
import queue
from flask import Blueprint, Response, jsonify

from database import db, Event
from analytics.event_analytics import compute_snapshot
from realtime.realtime_service import broker

realtime_bp = Blueprint("realtime", __name__)


@realtime_bp.route("/events/<event_id>/stream", methods=["GET"])
def stream(event_id):
    if not db.session.get(Event, event_id):
        return jsonify({"error": "not_found", "message": "Event not found"}), 404
    first = compute_snapshot(event_id)
    q = broker.subscribe(event_id)

    def gen():
        try:
            yield "retry: 3000\n\n"                       # browser auto-reconnects after 3s
            yield f"data: {json.dumps(first)}\n\n"        # initial state on (re)connect
            while True:
                try:
                    yield f"data: {q.get(timeout=15)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            broker.unsubscribe(event_id, q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
