"""Analytics calculations (pure reads over the database)."""
from datetime import date, datetime
from collections import OrderedDict
from sqlalchemy import and_

from database import db, Event, RSVP, Waitlist, Invite, User


def _pct(a, b):
    return round(a / b * 100, 1) if b else 0


def compute_snapshot(event_id):
    ev = db.session.get(Event, event_id)
    if not ev:
        return None
    waitlist = Waitlist.query.filter_by(event_id=event_id).count()
    invited = Invite.query.filter_by(event_id=event_id).count()
    responded_invited = (db.session.query(Invite)
                         .join(User, User.email == Invite.email)
                         .join(RSVP, and_(RSVP.user_id == User.id, RSVP.event_id == Invite.event_id))
                         .filter(Invite.event_id == event_id).count())
    total = ev.going_count + ev.maybe_count + ev.not_going_count
    return {
        "event_id": ev.id,
        "event_name": ev.event_name,
        "status": ev.status,
        "going": ev.going_count,
        "maybe": ev.maybe_count,
        "not_going": ev.not_going_count,
        "total_responses": total,
        "invited": invited,
        "responded_invited": responded_invited,
        # Response Rate = responded invitees / invited * 100 (None until invites exist)
        "response_rate_percent": _pct(responded_invited, invited) if invited else None,
        # Conversion = going / all responses * 100
        "rsvp_conversion_percent": _pct(ev.going_count, total),
        "maximum_capacity": ev.maximum_capacity,
        "available_seats": max(ev.maximum_capacity - ev.going_count, 0),
        "capacity_utilization_percent": _pct(ev.going_count, ev.maximum_capacity),
        "waitlist_size": waitlist,
        "as_of": datetime.utcnow().isoformat(),
    }


def rsvp_growth(event_id):
    """Cumulative RSVPs per hour bucket, split by current status."""
    rows = RSVP.query.filter_by(event_id=event_id).order_by(RSVP.responded_at.asc()).all()
    buckets = OrderedDict()
    for r in rows:
        k = r.responded_at.strftime("%Y-%m-%d %H:00")
        b = buckets.setdefault(k, {"new": 0})
        b["new"] += 1
    cum, out = 0, []
    for k, b in buckets.items():
        cum += b["new"]
        out.append({"bucket": k, "new": b["new"], "cumulative": cum})
    return out


def rsvp_timeline(event_id, limit=15):
    rows = (db.session.query(RSVP, User.name).join(User, User.id == RSVP.user_id)
            .filter(RSVP.event_id == event_id)
            .order_by(RSVP.updated_at.desc()).limit(limit).all())
    return [{"name": n, "status": r.status, "at": r.updated_at.isoformat()} for r, n in rows]


def organizer_summary(user_id):
    events = Event.query.filter_by(organizer_id=user_id).all()
    today = date.today().isoformat()
    going = sum(e.going_count for e in events)
    maybe = sum(e.maybe_count for e in events)
    notg = sum(e.not_going_count for e in events)
    ids = [e.id for e in events]
    invited = Invite.query.filter(Invite.event_id.in_(ids)).count() if ids else 0
    responded = (db.session.query(Invite)
                 .join(User, User.email == Invite.email)
                 .join(RSVP, and_(RSVP.user_id == User.id, RSVP.event_id == Invite.event_id))
                 .filter(Invite.event_id.in_(ids)).count()) if ids else 0
    return {
        "total_events": len(events),
        "upcoming_events": sum(1 for e in events if e.event_date >= today and e.status in ("PUBLISHED", "FULL")),
        "total_invitees": invited,
        "total_responses": going + maybe + notg,
        "going": going, "maybe": maybe, "not_going": notg,
        "response_rate_percent": _pct(responded, invited) if invited else None,
        "available_capacity": sum(max(e.maximum_capacity - e.going_count, 0) for e in events
                                  if e.status in ("PUBLISHED", "FULL")),
        "waitlist_size": sum(e.waitlist_count for e in events),
    }
