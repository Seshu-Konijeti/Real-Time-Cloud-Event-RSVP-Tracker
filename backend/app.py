"""
Real-Time Cloud-Based Event Planning & RSVP Tracker
Backend entrypoint (Flask application factory).

Run:
    python backend/app.py

This is OPTION A (beginner/local) of the project: Flask + SQLite +
frontend polling to simulate real-time updates. The same data model
and API surface maps directly onto OPTION B/C (FastAPI + Firestore/
Supabase + WebSockets) described in README.md / docs/architecture.md.
"""

import os
import sys
import logging
from datetime import timedelta
from flask import Flask, jsonify, send_from_directory
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import db, init_db
from auth import auth_bp
from routes_events import events_bp
from routes_rsvp import rsvp_bp
from routes_announcements import announcements_bp
from routes_notifications import notifications_bp
from routes_analytics import analytics_bp
from routes_admin import admin_bp
from routes_realtime import realtime_bp
from middleware import csrf_guard, security_headers

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)

    # ---- Configuration (never hardcode secrets: use env vars) ----
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # IMPORTANT: a relative "sqlite:///xxx.db" URI is resolved by Flask against
    # app.instance_path, which silently changes depending on HOW this file is
    # run (`python backend/app.py` vs imported as a module, e.g. by seed.py or
    # gunicorn) -- causing the server and the seed script to read/write two
    # different database files. To make this 100% predictable, any relative
    # sqlite path from DATABASE_URL is pinned to this file's own folder.
    db_url = os.environ.get("DATABASE_URL", "sqlite:///event_rsvp.db")
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        db_filename = db_url.replace("sqlite:///", "", 1)
        db_url = f"sqlite:///{os.path.join(BASE_DIR, db_filename)}"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

    if test_config:
        app.config.update(test_config)

    init_db(app)

    # ---- Register API blueprints ----
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(rsvp_bp, url_prefix="/api")
    app.register_blueprint(announcements_bp, url_prefix="/api")
    app.register_blueprint(notifications_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(realtime_bp, url_prefix="/api")
    app.before_request(csrf_guard)
    app.after_request(security_headers)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(Exception)
    def server_error(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"error": e.name.lower().replace(" ", "_"), "message": e.description}), e.code
        db.session.rollback()   # undo any half-finished transaction
        app.logger.exception("unhandled error")
        return jsonify({"error": "server_error", "message": "Something went wrong. Please retry."}), 500

    # ---- Serve the static frontend (so the whole thing runs as one app) ----
    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:path>")
    def frontend_files(path):
        full_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(full_path):
            return send_from_directory(FRONTEND_DIR, path)
        return send_from_directory(FRONTEND_DIR, "index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
