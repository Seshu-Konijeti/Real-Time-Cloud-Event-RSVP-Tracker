"""Seed dummy/synthetic data: python sample_data/seed.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from werkzeug.security import generate_password_hash
from app import create_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from database import db, User, Event

app = create_app()
with app.app_context():
    if not User.query.filter_by(email="organizer@demo.com").first():
        org = User(name="Demo Organizer", email="organizer@demo.com",
                   password_hash=generate_password_hash("demo123"), role="organizer")
        db.session.add(org)
        db.session.add(User(name="Demo Admin", email="admin@demo.com", password_hash=generate_password_hash("demo123"), role="admin"))
        for i in range(1, 6):
            db.session.add(User(name=f"Attendee {i}", email=f"attendee{i}@demo.com",
                                password_hash=generate_password_hash("demo123"), role="attendee"))
        db.session.commit()
        db.session.add(Event(organizer_id=org.id, event_name="Cloud Computing Workshop",
                             description="Hands-on intro to cloud concepts (dummy event).",
                             event_date="2027-01-15", start_time="10:00", end_time="13:00",
                             venue="Online", online_link="https://meet.example.com/demo",
                             maximum_capacity=100))
        db.session.add(Event(organizer_id=org.id, event_name="Tiny Meetup (capacity 2)",
                             description="Use this to test FULL + waitlist.",
                             event_date="2027-01-20", start_time="16:00", end_time="17:00",
                             venue="Room 101", maximum_capacity=2))
        db.session.commit()
    print("Seeded. Login: organizer@demo.com / demo123, attendee1..5@demo.com / demo123, admin@demo.com / demo123")
