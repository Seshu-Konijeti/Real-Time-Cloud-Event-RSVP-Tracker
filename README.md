# Real-Time Cloud-Based Event Planning & RSVP Tracker

> Real-time cloud-based event planning and RSVP platform featuring event management, live RSVP tracking, authentication with roles, race-condition-safe capacity control, FIFO waitlist, notifications, analytics, and a scalable cloud architecture.

**Status:** fully working locally (Flask + SQLite + Server-Sent Events), 32 automated tests passing, deployable to Render/Docker. Cloud-provider versions (Supabase/Firebase, AWS) are designed in `docs/` but were not built or deployed by the author yet. All data is dummy/synthetic.

## Overview
Organizers create events and invite people; attendees RSVP Going / Maybe / Not Going. Organizer dashboards and event pages update the instant anyone RSVPs (server push, no refresh).

## Problem Statement
Manual event coordination (chat groups, spreadsheets, forms) has no live attendance view, allows overbooking, and makes updates (venue/time changes) hard to broadcast.

## Objectives
Centralised event data, live RSVP counts, safe capacity limits under concurrent users, role-based access, automatic notifications, analytics, and a design that scales on cloud infrastructure.

## Features
| Area | Implemented |
|---|---|
| Auth | Register/login/logout, hashed passwords, signed HttpOnly session cookie, roles attendee/organizer/admin |
| Events | Create, edit, publish/draft, cancel, delete, upcoming list, auto COMPLETED, validation (dates, times, capacity, deadline) |
| RSVP | Going/Maybe/Not Going, update, clear, one per user per event (DB UNIQUE), deadline, idempotency key |
| Capacity | Atomic conditional UPDATE, FULL status, never oversells (thread test) |
| Waitlist | FIFO, auto-promotion on cancel/switch/capacity increase, promotion notification |
| Real-time | SSE push (`/api/events/{id}/stream`), auto-reconnect, polling fallback |
| Invites | Invite by email; response rate = responded invitees / invited |
| Announcements | Organizer posts; fan-out notification to Going/Maybe/waitlisted |
| Notifications | RSVP confirmation, invitation, reminder, venue change, time change, cancellation, waitlist promotion, announcement; optional email |
| Analytics | Totals, response rate, conversion, capacity utilization, seats, waitlist, growth curve, timeline; 5 canvas charts |
| Admin | Platform stats, user roles, moderation, audit log |
| Security | CSRF header guard, rate limiting, security headers/CSP, output escaping, RBAC + ownership checks, audit log |

## Industry Relevance
The same pattern (central store, transactional capacity, push updates, notifications) powers Eventbrite/Meetup-style ticketing, conferences, college festivals, corporate events, webinars, workshops, training programs, weddings and community events. Business value: centralised management, live attendance tracking, remote access, less manual coordination, automated RSVP handling, scalable attendee management, real-time updates, analytics.

## Cloud Computing Concepts (where each appears)
| Concept | Where in this project |
|---|---|
| Cloud hosting / PaaS | Render blueprint `render.yaml`, `Procfile`, `Dockerfile` |
| SaaS | The app itself is used through a browser by many tenants/users |
| IaaS | Docker image can run on any VM (EC2/Compute Engine) |
| Cloud / relational DB | SQLAlchemy models; SQLite locally, Postgres via `DATABASE_URL` |
| Real-time DB concept | `realtime/realtime_service.py` broker (Firestore listeners / Supabase Realtime are the managed equivalent) |
| Authentication / Authorization / RBAC | `backend/auth.py` (`login_required`, `role_required`) + ownership checks in routes |
| REST APIs | All `/api/*` routes |
| WebSockets vs SSE | SSE implemented; WebSocket compared below |
| Serverless / Cloud Functions / API Gateway | Design in `aws/README.md` (each route maps to one Lambda) |
| Event-driven architecture | RSVP -> publish -> subscribers; RSVP cancel -> waitlist promotion -> notification |
| Scalability / Elasticity / HA / Load balancing | `docs/architecture.md` scaling plan (stateless API, autoscaling, LB) |
| CDN | Static frontend served from CDN in the design |
| Caching | Event list / snapshot caching described; hot-row mitigation |
| Env vars / Secrets | `.env.example`, `SECRET_KEY`, no credentials in code |
| Logging / Monitoring | Python logging, `audit_logs` table, CloudWatch/Grafana in design |
| Backup | Managed DB snapshots (Render/Supabase) |
| CI/CD | `.github/workflows/ci.yml` runs pytest on every push |

## Real-Time Architecture
```
Attendee A --\
Attendee B ---+--> Flask API --> DB transaction --> RSVP + counters
Attendee C --/         |                                  |
                       |  publish_update(event_id)        |
                       v                                  v
                 Broker (pub/sub) --> SSE stream --> Organizer dashboard + event pages
```
Flow: user submits RSVP -> backend validates -> atomic conditional UPDATE -> RSVP row written -> commit -> `publish_update` -> every connected browser receives new counters -> counters change, no refresh.

| Approach | How | Pros | Cons |
|---|---|---|---|
| Polling | Client asks every N s | Trivial | Delay, wasted requests |
| SSE (built) | Server pushes over one HTTP stream | Simple, auto-reconnect, works through proxies | One-way only |
| WebSocket / realtime DB | Two-way persistent socket / managed subscription | Lowest latency, two-way | More infra, connection scaling |

## Technology Stack
Option A (built): HTML/CSS/JS, Flask, SQLAlchemy, SQLite, SSE, pytest, gunicorn, Docker, GitHub Actions.
Option B (designed): React + FastAPI + Supabase/Firestore + realtime subscription. Option C (designed): S3/CloudFront + API Gateway + Lambda + DynamoDB + WebSocket API + Cognito + SNS/SES + CloudWatch. Details and trade-offs: `docs/architecture.md`.

## User Roles
| Permission | Attendee | Organizer | Admin |
|---|---|---|---|
| Register/login, view events | Yes | Yes | Yes |
| RSVP / update / clear own RSVP | Yes | Yes | Yes |
| View own RSVPs, notifications, updates | Yes | Yes | Yes |
| Create event | No | Yes | Yes |
| Edit / cancel / delete event | No | Own only | Any |
| View attendee list, analytics detail | No | Own only | Any |
| Invite, remind, announce | No | Own only | Any |
| Manage users / moderate / audit log | No | No | Yes |

## Event Management
Fields: event_id, organizer_id, event_name, description, event_type, event_date, start_time, end_time, venue, online_link, maximum_capacity, registration_deadline, status (DRAFT, PUBLISHED, FULL, COMPLETED, CANCELLED), created_at, updated_at. Validation: valid date, start < end, capacity > 0, deadline <= event date, capacity cannot drop below current Going.

## RSVP System
Statuses GOING / MAYBE / NOT_GOING (plus waitlist). `UNIQUE(event_id, user_id)` guarantees one RSVP per user per event at the database level; repeating the same status is a no-op (idempotent).

## Capacity Management and Concurrency
Naive code `if going < capacity: going += 1` reads then writes. Two requests can both read 99 and both write, giving 101. Fix (`cloud/database_service.py`):
```sql
UPDATE events SET going_count = going_count + 1
WHERE id = :id AND going_count < maximum_capacity
```
One statement, checked and written atomically under the database row lock. `rowcount == 0` means the seat was lost -> waitlist. Postgres alternative: `SELECT ... FOR UPDATE` in a transaction; Firestore: transaction; DynamoDB: `ConditionExpression`. Proven by test T14 (12 threads, 3 seats -> exactly 3 Going, 9 waitlisted). SQLite serializes writers; on Postgres the same statement is row-locked.

## Waitlist
FIFO by `position`. When a Going user cancels or switches away (or capacity is raised) the earliest waiting user is promoted, marked GOING and notified.

## Cloud Database
```
users(id PK, name, email UNIQUE, password_hash, role, created_at)
events(id PK, organizer_id FK->users, ... counters going/maybe/not_going/waitlist, status)
rsvps(id PK, event_id FK, user_id FK, status, responded_at, updated_at, UNIQUE(event_id,user_id))
waitlist(id PK, event_id FK, user_id FK, position, joined_at, status, UNIQUE(event_id,user_id))
invites(id PK, event_id FK, email, UNIQUE(event_id,email))
announcements(id PK, event_id FK, title, message, created_at)
notifications(id PK, user_id FK, event_id FK, type, message, read, created_at)
audit_logs(id PK, user_id, action, details, created_at)

users 1--* events (creates)     users *--* events via rsvps (RSVPs)     events 1--* rsvps / waitlist / invites / announcements
```
Indexes on every foreign key and on `users.email`. Denormalised counters on `events` make live reads O(1); they are only changed by the atomic updates above. NoSQL mapping: `events/{id}` doc with counters, `events/{id}/rsvps/{userId}` subcollection (document id = userId gives uniqueness), transactions for capacity.

## Authentication and Authorization
Authentication = who are you (login, signed cookie). Authorization = what may you do (role decorators + ownership). Rules enforced server-side: nobody edits another user's RSVP (RSVP endpoints only act on the logged-in user), organizers manage only their events, attendees get 403 on organizer APIs, admin APIs are admin-only.

## Notifications
In-app notifications for: RSVP confirmation, invitation, reminder, venue change, time change, cancellation, waitlist promotion, organizer announcement. Optional email via SMTP env vars; email failure never blocks the request. SMS/push would plug into `cloud/notification_service.py`.

## Analytics
Response rate = responded invitees / invited x 100 (e.g. 350/500 = 70%). Conversion = Going / all responses. Capacity utilization = Going / capacity. Also seats available, waitlist size, RSVP growth (cumulative per hour), timeline. Code: `analytics/event_analytics.py`.

## REST APIs
CSRF: all POST/PUT/DELETE need header `X-Requested-With: fetch` (the bundled frontend adds it).
| Method | Endpoint | Auth | Success | Errors |
|---|---|---|---|---|
| POST | /api/register {name,email,password,role} | public | 201 user | 400 validation, 409 duplicate, 429 |
| POST | /api/login {email,password} | public | 200 user | 401, 429 |
| POST | /api/logout | any | 200 | |
| GET | /api/me | any | 200 user or null | |
| POST | /api/events | organizer/admin | 201 event | 400, 401, 403 |
| GET | /api/events?upcoming=true&status=&organizer_id= | public | 200 list | |
| GET | /api/events/upcoming | public | 200 list | |
| GET | /api/events/{id} | public | 200 | 404 |
| PUT | /api/events/{id} | owner/admin | 200 | 400, 401, 403, 404 |
| PUT | /api/events/{id}/cancel | owner/admin | 200 | 401, 403, 404 |
| DELETE | /api/events/{id} | owner/admin | 200 | 401, 403, 404 |
| POST/PUT | /api/events/{id}/rsvp {status} (+Idempotency-Key) | logged in | 200 rsvp+event | 400 deadline/closed/validation, 401, 404, 409 event_full (waitlisted), 429 |
| DELETE | /api/events/{id}/rsvp | logged in | 200 | 404 |
| GET | /api/events/{id}/rsvps | owner/admin | 200 list | 403 |
| GET | /api/rsvps/me | logged in | 200 rsvps+waitlist | 401 |
| GET | /api/events/{id}/analytics | public | 200 snapshot | 404 |
| GET | /api/events/{id}/analytics/detail | owner/admin | 200 growth+timeline | 403 |
| GET | /api/events/{id}/stream | public | SSE stream | 404 |
| POST/GET | /api/events/{id}/invites | owner/admin | 201 / 200 | 403 |
| POST | /api/events/{id}/reminder | owner/admin | 200 | 403 |
| POST/GET | /api/events/{id}/announcements | owner (post) / public | 201 / 200 | 400, 403 |
| GET | /api/updates/me | logged in | 200 | 401 |
| GET | /api/notifications, PUT /api/notifications/{id}/read | logged in | 200 | 404 |
| GET | /api/organizer/summary | organizer/admin | 200 | 403 |
| GET/PUT | /api/admin/stats, /users, /users/{id}/role, /events/{id}/moderate, /audit | admin | 200 | 403 |

## Folder Structure
```
Cloud-Event-RSVP-Tracker/
  frontend/            static pages + static/js (api.js, charts.js) + static/css
  backend/             app.py, auth.py, routes_*.py, database.py (models), middleware.py
  realtime/            realtime_service.py  (pub/sub broker for SSE)
  cloud/               database_service.py, auth_service.py, notification_service.py
  analytics/           event_analytics.py
  tests/               test_app.py (T01-T25 + extras)
  sample_data/         seed.py (dummy users/events)
  tools/               run_test_matrix.py (generates docs/test_matrix.md)
  docs/                architecture, report, test matrix, proof plan, interview prep
  aws/                 Option C design notes
  screenshots/         put your proof screenshots here
  Procfile render.yaml Dockerfile .github/workflows/ci.yml
  requirements.txt .env.example .gitignore README.md
```

## Installation
```
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env   then edit SECRET_KEY
python sample_data/seed.py       # optional dummy data
python backend/app.py
```
Open http://localhost:5000. Seed logins (password `demo123`): organizer@demo.com, attendee1..5@demo.com, admin@demo.com.

## Environment Variables
`SECRET_KEY`, `DATABASE_URL`, `FLASK_DEBUG`, `PORT`, `COOKIE_SECURE`, `EMAIL_ENABLED`, `SMTP_HOST/PORT/USER/PASSWORD/FROM`. Never commit `.env`.

## Local Simulation (13 steps)
1. `python backend/app.py`  2. Frontend is served by the same app at http://localhost:5000  3. Register an organizer (or use seed)
4. Create "Cloud Computing Workshop", capacity 100  5. Open Organizer Dashboard -> "Live dashboard": Going/Maybe/Not going = 0
6. Attendee A (incognito) registers, opens the event, clicks Going -> organizer shows Going = 1
7. Attendee B (other browser) clicks Maybe -> Maybe = 1
8. B switches Maybe -> Going -> organizer shows Going = 2, Maybe = 0, no refresh
9. Organizer sends an announcement  10. Attendees see it under Announcements and Notifications
11. B clears RSVP -> Going = 1  12. Use "Tiny Meetup (capacity 2)": third Going click -> "event is full, waitlisted"; someone cancels -> promotion
13. Log in as a different organizer and try to edit the event, or call the API without login -> 403 / 401

Multi-window demo: Window 1 organizer dashboard, Window 2 attendee A, Window 3 attendee B (incognito or another browser so sessions do not clash). A Going -> organizer updates; B Going -> updates again; A Maybe -> counts change instantly.

## Cloud Deployment
**Approach A (student, free tier) - Render + optional Supabase Postgres**
1. Push to GitHub. 2. Render -> New -> Blueprint -> pick the repo (uses `render.yaml`). 3. Set `DATABASE_URL` to a Postgres URL (Render Postgres or Supabase) for persistent data; without it SQLite resets on redeploy. 4. Deploy, open the URL, run the simulation. 5. Docker alternative: `docker build -t rsvp . && docker run -p 8080:8080 -e SECRET_KEY=xyz rsvp`.
Keep `--workers 1 --threads 32` (in-process SSE broker). To run many workers/instances, replace the broker with Redis pub/sub.
Note: Postgres needs `pip install psycopg2-binary`, and the atomic UPDATE SQL used here is standard so it works unchanged. Postgres deployment is untested by the author.
**Approach B (enterprise):** see `aws/README.md` and `docs/architecture.md`.

## Testing
`pytest -q` runs 32 tests (T01-T25 from the spec + 7 hardening tests). `python tools/run_test_matrix.py` regenerates `docs/test_matrix.md` (Test ID, scenario, input, expected, actual, pass/fail) from a real run. CI runs pytest on each push.

## Security
Passwords hashed (werkzeug); HttpOnly, SameSite=Lax cookies (Secure in production); RBAC + ownership checks; SQL injection avoided via ORM and bound parameters (column names for counters are whitelisted); XSS: all user text is escaped (`esc()`) before `innerHTML`, plus CSP and nosniff headers; CSRF header guard; per-IP/user rate limits on login, register, RSVP; no secrets in code; audit log; HTTPS/encryption in transit and at rest come from the hosting platform. **Users cannot change counts from the browser:** the API accepts only a status; counters are written solely by backend atomic updates (test T19 sends forged `going_count`, it is ignored).

## Scalability
100 users: single instance. 10,000: managed Postgres + 2-3 autoscaled instances behind a load balancer + Redis pub/sub for SSE + CDN for static files. 1,000,000: serverless/containers autoscaling, read replicas, cached snapshots, sharded/queued counter writes, managed WebSocket fan-out. 100,000 RSVPs in 5 minutes (~330/s): rate limiting, queue (SQS/Redis) to smooth bursts, one atomic counter row is the hot spot -> split into N shard counters or reserve seat blocks per instance, serve reads from cache, push updates through a managed socket service.

## Failure Handling
| Failure | Handling |
|---|---|
| DB fails | transaction rollback, JSON 500, app recovers (T22) |
| RSVP timeout / network | client retries reads with backoff; RSVP carries Idempotency-Key |
| Double click | UI busy lock + idempotent server (X test) |
| SSE disconnect | browser auto-reconnects, server resends full state; polling fallback (T23) |
| Notification / email fails | logged, request still succeeds (X test) |
| Refresh mid-RSVP | server state is truth; UI re-reads on load |
| Duplicate request | same status is a no-op, UNIQUE constraint (T08) |

## Screenshots
Store in `screenshots/`; checklist and file names in `docs/github_and_proof.md`. (Add your own after running the app.)

## Results
32/32 tests pass; live SSE verified under gunicorn (counts pushed 0 -> 1 -> 2); 12 concurrent requests for 3 seats never oversold.

## Limitations
In-process SSE broker (single instance); SQLite by default; session cookies (no OAuth/JWT); reminders are sent on demand (no scheduler); CSP still allows inline scripts; not load tested; cloud-provider deployments not done by the author.

## Future Improvements
Redis broker, Postgres in production, WebSocket version, scheduled reminders, SMS/push, ticket QR check-in, OAuth login, load tests, React/FastAPI rewrite (Option B).

## Learning Outcomes
Cloud architecture and service models, REST design, RBAC, transactional/atomic concurrency control, real-time push, testing, CI/CD, security basics, failure handling.

## Author
Konijeti Venkata Seshu Babu - B.Tech ECE, SRKR Engineering College
