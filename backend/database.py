"""
Database layer: SQLAlchemy models + init helper.

Demonstrates (see README section "Cloud Computing Concepts"):
- Cloud Database (SQLite here locally; same schema maps to
  Postgres/Firestore/DynamoDB in the cloud versions)
- Primary keys / foreign keys / unique constraints / indexes
- Concurrency-safe capacity handling (atomic conditional UPDATE)
"""

import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


def new_id():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="attendee")  # attendee | organizer | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# EVENTS
# ---------------------------------------------------------------------------
class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    organizer_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    event_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    event_type = db.Column(db.String(50), default="general")

    event_date = db.Column(db.String(20), nullable=False)     # YYYY-MM-DD
    start_time = db.Column(db.String(10), nullable=False)     # HH:MM
    end_time = db.Column(db.String(10), nullable=False)       # HH:MM

    venue = db.Column(db.String(200), default="")
    online_link = db.Column(db.String(300), default="")

    maximum_capacity = db.Column(db.Integer, nullable=False, default=100)
    registration_deadline = db.Column(db.String(20), nullable=True)

    # Denormalized live counters -> updated ATOMICALLY (see rsvp logic).
    # This is the "source of truth" the frontend can never write to directly.
    going_count = db.Column(db.Integer, nullable=False, default=0)
    maybe_count = db.Column(db.Integer, nullable=False, default=0)
    not_going_count = db.Column(db.Integer, nullable=False, default=0)
    waitlist_count = db.Column(db.Integer, nullable=False, default=0)

    status = db.Column(db.String(20), nullable=False, default="PUBLISHED")
    # DRAFT | PUBLISHED | FULL | COMPLETED | CANCELLED

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "organizer_id": self.organizer_id,
            "event_name": self.event_name,
            "description": self.description,
            "event_type": self.event_type,
            "event_date": self.event_date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "venue": self.venue,
            "online_link": self.online_link,
            "maximum_capacity": self.maximum_capacity,
            "registration_deadline": self.registration_deadline,
            "going_count": self.going_count,
            "maybe_count": self.maybe_count,
            "not_going_count": self.not_going_count,
            "waitlist_count": self.waitlist_count,
            "available_seats": max(self.maximum_capacity - self.going_count, 0),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# RSVPS
# ---------------------------------------------------------------------------
class RSVP(db.Model):
    __tablename__ = "rsvps"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)  # GOING | MAYBE | NOT_GOING | WAITLISTED
    responded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user_rsvp"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "status": self.status,
            "responded_at": self.responded_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# WAITLIST (FIFO)
# ---------------------------------------------------------------------------
class Waitlist(db.Model):
    __tablename__ = "waitlist"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    position = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="WAITING")  # WAITING | PROMOTED

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_user_waitlist"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "joined_at": self.joined_at.isoformat(),
            "position": self.position,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# ANNOUNCEMENTS
# ---------------------------------------------------------------------------
class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=True)
    type = db.Column(db.String(40), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "type": self.type,
            "message": self.message,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# AUDIT LOG (optional, demonstrates monitoring/observability)
# ---------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    user_id = db.Column(db.String(36), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# INVITES (by email; response rate = responded invitees / invited)
# ---------------------------------------------------------------------------
class Invite(db.Model):
    __tablename__ = "invites"

    id = db.Column(db.String(36), primary_key=True, default=new_id)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    email = db.Column(db.String(160), nullable=False, index=True)
    invited_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_event_invite_email"),)

    def to_dict(self):
        return {"id": self.id, "event_id": self.event_id, "email": self.email,
                "invited_at": self.invited_at.isoformat()}


def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
