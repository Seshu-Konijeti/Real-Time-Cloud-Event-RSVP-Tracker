"""Security / reliability middleware: rate limiting, CSRF guard, idempotency, headers."""
import time
import threading
from collections import defaultdict, deque, OrderedDict
from functools import wraps
from flask import request, jsonify, current_app, session

_hits = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(name, default_limit, per=60):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **k):
            if not current_app.config.get("RATELIMIT_ENABLED", True):
                return f(*a, **k)
            limit = current_app.config.get(f"RATELIMIT_{name.upper()}", default_limit)
            key = (name, session.get("user_id") or request.remote_addr)
            now = time.time()
            with _lock:
                q = _hits[key]
                while q and now - q[0] > per:
                    q.popleft()
                if len(q) >= limit:
                    return jsonify({"error": "rate_limited", "message": "Too many requests, slow down"}), 429
                q.append(now)
            return f(*a, **k)
        return wrapper
    return deco


def reset_rate_limits():
    with _lock:
        _hits.clear()


def csrf_guard():
    """State-changing API calls must carry a custom header. Browsers will not add it
    on cross-site form posts, and cross-origin fetch needs a CORS preflight (we allow none)."""
    if request.path.startswith("/api/") and request.method in ("POST", "PUT", "DELETE"):
        if request.headers.get("X-Requested-With") != "fetch":
            return jsonify({"error": "csrf", "message": "Missing X-Requested-With header"}), 403


def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
    return resp


_idem = OrderedDict()
_idem_lock = threading.Lock()


def idem_get(user_id, key):
    with _idem_lock:
        return _idem.get((user_id, key))


def idem_put(user_id, key, value, cap=1000):
    with _idem_lock:
        _idem[(user_id, key)] = value
        while len(_idem) > cap:
            _idem.popitem(last=False)
