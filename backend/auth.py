"""
Authentication & Authorization.

Authentication  -> "Who is the user?"      (register/login/session cookie)
Authorization   -> "What can they do?"     (role_required decorator)

For simplicity/local-run this uses Flask's signed session cookie
(itself HMAC-signed with SECRET_KEY, so it can't be tampered with by
the client). The cloud version (OPTION B/C) swaps this module for
Firebase Auth / Supabase Auth / AWS Cognito without touching any
other file, because every route below only depends on `current_user()`.
"""

from functools import wraps
from flask import Blueprint, request, jsonify, session
import os
from cloud.auth_service import hash_password, verify_password
from cloud.database_service import log_audit
from middleware import rate_limit

from database import db, User

auth_bp = Blueprint("auth", __name__)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "unauthorized", "message": "Login required"}), 401
        return f(user, *args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "unauthorized", "message": "Login required"}), 401
            if user.role not in roles:
                return jsonify({"error": "forbidden", "message": "Insufficient permissions"}), 403
            return f(user, *args, **kwargs)
        return wrapper
    return decorator


@auth_bp.route("/register", methods=["POST"])
@rate_limit("register", 10)
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "attendee")

    if role not in ("attendee", "organizer"):
        role = "attendee"
    if not name or not email or len(password) < 6:
        return jsonify({"error": "validation_error",
                         "message": "name, email and a 6+ char password are required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "conflict", "message": "Email already registered"}), 409

    user = User(name=name, email=email,
                password_hash=hash_password(password), role=role)
    db.session.add(user)
    db.session.flush()
    log_audit(user.id, "register", role)
    db.session.commit()

    session.permanent = True
    session["user_id"] = user.id
    return jsonify({"user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit("login", 10)
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(user.password_hash, password):
        log_audit(user.id if user else None, "login_failed", email)
        db.session.commit()
        return jsonify({"error": "invalid_credentials", "message": "Wrong email or password"}), 401

    session.permanent = True
    session["user_id"] = user.id
    log_audit(user.id, "login")
    db.session.commit()
    return jsonify({"user": user.to_dict()})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@auth_bp.route("/me", methods=["GET"])
def me():
    user = current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user.to_dict()})
