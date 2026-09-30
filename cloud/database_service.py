"""
Database service: concurrency-safe counters, waitlist promotion, audit log.

ATOMIC CONDITIONAL UPDATE is the core of race-condition safety:
    UPDATE events SET going_count = going_count + 1
    WHERE id = :id AND going_count < maximum_capacity
The check and the write happen as ONE statement under the database's row lock,
so two simultaneous "last seat" requests cannot both succeed (rowcount 0 = lost).
Cloud equivalents: Postgres SELECT..FOR UPDATE, Firestore transaction,
DynamoDB ConditionExpression.
"""
from datetime import datetime
from sqlalchemy import text

from database import db, Event, RSVP, Waitlist, AuditLog
from cloud.notification_service import notify

ALLOWED_COLUMNS = {"going_count", "maybe_count", "not_going_count", "waitlist_count"}


def atomic_increment(event_id, column, delta=1, guard_capacity=False):
    if column not in ALLOWED_COLUMNS:          # column name is never user input
        raise ValueError("invalid column")
    if guard_capacity and delta > 0:
        sql = text(f"UPDATE events SET {column} = {column} + :d "
                   f"WHERE id = :id AND going_count < maximum_capacity")
    else:  # portable clamp at zero (works on SQLite and Postgres)
        sql = text(f"UPDATE events SET {column} = CASE WHEN {column} + :d < 0 THEN 0 "
                   f"ELSE {column} + :d END WHERE id = :id")
    db.session.flush()
    res = db.session.execute(sql, {"d": delta, "id": event_id})
    db.session.expire_all()
    return res.rowcount == 1


def refresh_full_status(event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return
    if ev.going_count >= ev.maximum_capacity and ev.status == "PUBLISHED":
        ev.status = "FULL"
    elif ev.going_count < ev.maximum_capacity and ev.status == "FULL":
        ev.status = "PUBLISHED"
    db.session.commit()


def next_waitlist_position(event_id):
    last = (Waitlist.query.filter_by(event_id=event_id)
            .order_by(Waitlist.position.desc()).first())
    return (last.position + 1) if last else 1


def promote_from_waitlist(event_id):
    """FIFO: promote the earliest waiting user if a seat is genuinely free."""
    entry = (Waitlist.query.filter_by(event_id=event_id, status="WAITING")
             .order_by(Waitlist.position.asc()).first())
    if not entry:
        return None
    if not atomic_increment(event_id, "going_count", +1, guard_capacity=True):
        return None
    atomic_increment(event_id, "waitlist_count", -1)
    uid = entry.user_id
    db.session.delete(entry)
    rsvp = RSVP.query.filter_by(event_id=event_id, user_id=uid).first()
    if rsvp:
        old = rsvp.status
        if old == "MAYBE":
            atomic_increment(event_id, "maybe_count", -1)
        elif old == "NOT_GOING":
            atomic_increment(event_id, "not_going_count", -1)
        rsvp.status, rsvp.updated_at = "GOING", datetime.utcnow()
    else:
        db.session.add(RSVP(event_id=event_id, user_id=uid, status="GOING"))
    notify(uid, event_id, "waitlist_promotion", "A seat opened up - you are now marked GOING!")
    db.session.commit()
    refresh_full_status(event_id)
    return uid


def promote_all_possible(event_id):
    n = 0
    while promote_from_waitlist(event_id):
        n += 1
    return n


def log_audit(user_id, action, details=""):
    db.session.add(AuditLog(user_id=user_id, action=action, details=str(details)[:500]))
