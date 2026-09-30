"""
Notification service: in-app notifications (always) + optional email (SMTP).

Email is best-effort: failures are logged and NEVER block the main request
(failure-handling requirement). SMS/push would plug in at _send_external().
"""
import logging
import os
import smtplib
from email.message import EmailMessage

from database import db, Notification, RSVP, Waitlist, User

log = logging.getLogger("notifications")


def _send_email(to_email, subject, body):
    if os.environ.get("EMAIL_ENABLED", "false").lower() != "true":
        return False
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "no-reply@example.com")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=5) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True


def notify(user_id, event_id, ntype, message):
    """Queue an in-app notification (caller commits) and try email."""
    db.session.add(Notification(user_id=user_id, event_id=event_id, type=ntype, message=message[:300]))
    try:
        user = db.session.get(User, user_id)
        if user:
            _send_email(user.email, "Event update", message)
    except Exception:
        log.exception("email delivery failed; in-app notification kept")


def audience_ids(event_id, include_waitlist=True):
    ids = {r.user_id for r in RSVP.query.filter(
        RSVP.event_id == event_id, RSVP.status.in_(["GOING", "MAYBE"])).all()}
    if include_waitlist:
        ids |= {w.user_id for w in Waitlist.query.filter_by(event_id=event_id).all()}
    return ids


def notify_audience(event_id, ntype, message, include_waitlist=True):
    ids = audience_ids(event_id, include_waitlist)
    for uid in ids:
        notify(uid, event_id, ntype, message)
    return len(ids)
