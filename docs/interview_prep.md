# Interview Preparation (10 questions). Answers match what is actually built. Parts in [brackets] apply only after you do them.

1. **Explain your project.**
It is a real-time event and RSVP tracker. Organizers create events and invite people; attendees choose Going, Maybe or Not Going. The organizer dashboard updates live because the server pushes changes over Server-Sent Events. The backend is a Flask REST API on a relational database. The hard parts I solved were keeping capacity correct when many people click at once, a FIFO waitlist that auto-promotes, role-based security, and notifications. I wrote 32 automated tests and CI, and prepared Docker/Render deployment [and deployed it at <URL>]. I also designed the AWS/Supabase versions.

2. **How does the cloud aspect show up?**
The app is stateless with central storage, so any device can use it and instances can be added behind a load balancer. Config comes from environment variables, the DB is swappable to managed Postgres by one URL, it ships as a Docker image and Render blueprint, and CI runs on GitHub. I documented how each part maps to managed services (Cognito, API Gateway, Lambda, DynamoDB, WebSocket API).

3. **How is real-time implemented and why SSE?**
After each committed RSVP the backend publishes a snapshot to a broker; every open `/stream` connection receives it. SSE is one-way, simple, auto-reconnects, and I only need server-to-client. On reconnect the server resends full state, and the client falls back to polling if SSE is unavailable. WebSockets would be the choice for two-way features; for scale I would use Redis pub/sub or a managed socket service.

4. **What is the race condition and how did you fix it?**
With capacity 100 and 99 going, two users click together. Check-then-insert lets both read 99 and both write, giving 101. I use one statement: `UPDATE events SET going_count = going_count + 1 WHERE id=? AND going_count < maximum_capacity`. The database checks and writes atomically, so only one succeeds; the loser gets rowcount 0 and is waitlisted. On Postgres I could also use `SELECT FOR UPDATE`; DynamoDB uses ConditionExpression. My test fires 12 threads at 3 seats and gets exactly 3 Going.

5. **How do you prevent duplicate RSVPs?**
A database `UNIQUE(event_id, user_id)` constraint, plus the API treats the same status twice as a no-op, and RSVP requests accept an Idempotency-Key so retries replay the first result. My test also tries a raw duplicate insert and the DB rejects it.

6. **How do authentication and authorization work?**
Passwords are hashed; login sets a signed HttpOnly session cookie. Decorators check login and role (401 vs 403), and routes check ownership so an organizer only manages their own events. RSVP endpoints only ever act on the logged-in user, so nobody can edit someone else's RSVP.

7. **Can a user tamper with counts from the browser?**
No. The API accepts only a status. Counters are changed only by backend atomic updates, and a test sends a forged `going_count: 999` that is ignored. The database is the source of truth.

8. **How would you scale to 100,000 RSVPs in five minutes?**
CDN for static files, load balancer with autoscaled stateless API, rate limiting, a queue to absorb the burst, managed Postgres with pooling, cached reads, and a managed WebSocket service. The single counter row is a hot spot, so I would shard the counter or hand out seat blocks per instance. My current in-process broker would move to Redis.

9. **What failures did you handle?**
DB failure rolls back and returns a JSON 500, and the app recovers (tested). Double clicks are guarded in the UI and idempotent on the server. If the stream drops, the browser reconnects and gets fresh state (tested with a dead subscriber). Email or notification failure is logged and never blocks the RSVP (tested).

10. **What would you improve and what are the limits?**
Redis-backed broker for multiple instances, Postgres in production, scheduled reminders, WebSockets, OAuth, load testing, and a React/FastAPI version. Current limits: single-instance real-time broker, SQLite by default, reminders on demand, not load tested.
