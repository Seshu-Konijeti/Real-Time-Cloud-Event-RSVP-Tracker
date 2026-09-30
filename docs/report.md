# Project Report - Real-Time Cloud-Based Event Planning & RSVP Tracker

**Author:** Konijeti Venkata Seshu Babu, B.Tech ECE, SRKR Engineering College   **Course:** Cloud Computing

## Abstract
This project implements an event planning platform where organizers publish events and attendees RSVP with Going, Maybe or Not Going. RSVP counts are pushed live to organizer dashboards using Server-Sent Events. Capacity is enforced with atomic conditional database updates so concurrent requests cannot oversell seats; overflow users join a FIFO waitlist. The system includes role-based access, notifications, analytics, an admin console, security controls, automated tests and deployment files. A cloud-provider design (managed database, serverless, WebSocket) is documented.

## 1. Introduction
Event organizers need a single source of truth for who is attending. Cloud computing provides central, always-available, scalable infrastructure for this.

## 2. Problem Statement
Manual RSVP tracking is slow, error-prone, not live, and cannot enforce capacity or broadcast changes reliably.

## 3. Objectives
Central event storage; live RSVP tracking; concurrency-safe capacity; roles and authorization; notifications and announcements; analytics; testable, deployable, documented system.

## 4. Existing System
Chat groups, spreadsheets and forms: duplicate entries, stale counts, overbooking, no automatic updates.

## 5. Proposed System
Web application with REST API, relational database, push-based real-time updates, waitlist and analytics.

## 6. Industry Relevance
Used in event/ticketing platforms, conferences, festivals, corporate and community events. Benefits listed in README.

## 7. Cloud Computing Concepts
SaaS/PaaS/IaaS mapping, managed databases, RBAC, REST, event-driven design, CI/CD, secrets, logging, scalability (README concept table).

## 8. Real-Time Computing Concepts
Polling vs SSE vs WebSockets; the implementation uses SSE with reconnect and polling fallback.

## 9. Technology Stack
HTML/CSS/JS, Flask, SQLAlchemy, SQLite/Postgres, SSE, pytest, gunicorn, Docker, GitHub Actions.

## 10. Architecture
Browser -> Flask REST API -> DB (atomic updates) -> broker -> SSE -> browsers. See `architecture.md`.

## 11. Database Design
Tables users, events, rsvps, waitlist, invites, announcements, notifications, audit_logs; FK, UNIQUE(event_id,user_id), indexes; denormalised counters (README ER text).

## 12. Authentication
Hashed passwords, signed HttpOnly cookie, login_required / role_required decorators, ownership checks.

## 13. Event Management
CRUD, draft/publish, cancel, automatic COMPLETED, validation, change notifications.

## 14. RSVP Workflow
Validate -> atomic update -> write RSVP -> notify -> commit -> publish. One RSVP per user per event.

## 15. Real-Time Updates
`/api/events/{id}/stream`; every RSVP change publishes a snapshot; browsers update without refresh.

## 16. Capacity Management
Conditional UPDATE `WHERE going_count < maximum_capacity`; FULL status; capacity increases promote the waitlist.

## 17. Concurrency Control
Naive check-then-write causes a race (99 -> 101). The atomic statement removes the gap. Verified by a 12-thread test on 3 seats.

## 18. Waitlist
FIFO position, auto-promotion with notification, removal when the user changes their mind.

## 19. Notifications
Eight in-app types, optional email, failures isolated.

## 20. Analytics
Response rate, conversion, utilization, seats, waitlist, growth, timeline, five charts.

## 21. API Design
25+ REST endpoints (README table).

## 22. Implementation
Modules: `backend/` (routes), `cloud/` (DB, auth, notification services), `realtime/`, `analytics/`, `frontend/`.

## 23. Testing
32 automated tests including the 25 specified scenarios; matrix in `test_matrix.md`; all pass. Live SSE and gunicorn were verified manually with curl.

## 24. Cloud Deployment
Render blueprint / Docker provided. [Add: deployed URL and date once you deploy.] AWS/Azure/GCP designs described.

## 25. Security
CSRF guard, rate limiting, headers/CSP, escaping, RBAC, audit log, backend as source of truth for counts.

## 26. Scalability
See README/architecture: LB, autoscaling, cache, queue, sharded counters, managed WebSockets.

## 27. Failure Handling
Rollback, retries, idempotency, reconnect, graceful errors, isolated notification failures.

## 28. Results
32/32 tests passed; real-time push confirmed (0 -> 1 -> 2 Going); no oversell under concurrency.

## 29. Advantages
Live view, no overbooking, role security, extensible to managed cloud services, fully testable offline.

## 30. Limitations
Single-instance broker, SQLite default, on-demand reminders, not load tested, cloud deployment pending.

## 31. Future Scope
Redis/WebSockets, Postgres, scheduled reminders, SMS/push, OAuth, load testing, React/FastAPI.

## 32. Conclusion
The project demonstrates core cloud application patterns - central data, REST, RBAC, real-time push, safe concurrency and CI - in a form that runs locally for free and maps directly onto managed cloud services.
