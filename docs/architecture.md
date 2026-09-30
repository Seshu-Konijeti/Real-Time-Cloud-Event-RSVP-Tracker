# Architecture, Stack Options and Explanations

## Simple explanation
It is like a shared digital guest list. Everyone RSVPs from their own phone or laptop; the organizer watches Going / Maybe / Not Going numbers change live, and the system stops taking more people than the room holds.

## Technical explanation
Browser clients call a stateless REST API. The API validates, changes the database inside a transaction using atomic conditional updates, then publishes an event to a broker. Each browser holding an open Server-Sent Events stream receives the fresh counters. Event data lives in one central database, so any device sees the same truth.

## Workflow
Organizer -> creates event -> DB -> published -> attendees view -> attendee picks RSVP -> API validates -> RSVP stored + counters updated atomically -> commit -> real-time publish -> organizer dashboard counters change (Going/Maybe/Not Going).

## Why cloud
Central access from any device, elastic scaling for popular events, managed database/auth/monitoring, pay-per-use, no hardware. "Real-time" here means changes reach viewers within ~1 second by push instead of on manual refresh.

## Concurrent RSVPs and scaling a popular event
Requests are independent stateless calls; correctness comes from the database atomic update, not from the app. Scale out API instances behind a load balancer, keep the DB as the single source of truth, add cache/queue for bursts (see README "Scalability").

## Three implementation options
| | A - Local (BUILT) | B - Recommended cloud (designed) | C - Advanced (designed) |
|---|---|---|---|
| Frontend | HTML/CSS/JS | React on Vercel/Netlify | React/Next on S3 + CloudFront |
| Backend | Flask | FastAPI on Render/Railway | API Gateway + Lambda |
| Auth | Session cookie | Supabase Auth / Firebase Auth | Cognito |
| Database | SQLite (Postgres ready) | Supabase Postgres / Firestore | DynamoDB or RDS |
| Real-time | SSE (poll fallback) | Supabase Realtime / Firestore listeners | API Gateway WebSocket API |
| Notifications | in-app + SMTP | Supabase functions / email API | SNS + SES |
| Difficulty | Easy | Medium | Hard |
| Cost | Free | Free tiers | Free tier then pay-per-use |
| Limits | single instance broker, SQLite | vendor lock-in, free-tier sleep | complexity, IAM learning curve |
| Concepts shown | REST, RBAC, atomic concurrency, SSE, CI | + managed DB/auth, realtime DB, PaaS | + serverless, API gateway, CDN, autoscaling |
**Recommendation for a student:** finish A (done), then migrate to B by replacing `cloud/auth_service.py` and `DATABASE_URL`, and swapping the SSE client for the provider's realtime subscription. C is a design exercise.

## Industry relevance
Event platforms, conferences, college fests, corporate events, webinars, workshops, meetups, training, weddings, community events, ticketing and networking events all need shared state, capacity limits and updates. Business benefits: centralised management, live attendance tracking, remote access, less manual coordination, automated RSVPs, scalable attendee management, real-time updates, analytics.

## Scalability (100 / 10,000 / 1,000,000 users; 100,000 RSVPs in 5 minutes)
- 100: one instance. 10,000: managed Postgres, 2-3 instances, LB, Redis pub/sub, CDN. 1,000,000: autoscaling containers/serverless, read replicas, cached reads, queues, managed WebSocket fan-out.
- 100,000 in 5 min (~330 req/s): CDN for static, LB + autoscaling API, rate limits, queue to absorb bursts, event stream for updates, WebSocket service for push.
- Hot spot: every Going request updates one counter row. Reduce by sharding the counter into N rows (sum on read), pre-allocating seat blocks per instance, or serialising through a queue per event.

## Failure handling design
Retries with backoff, reconnecting streams, idempotency keys, transactions and rollback, graceful JSON errors, structured logs.
