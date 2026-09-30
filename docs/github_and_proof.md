# GitHub Strategy, Proof Plan, Resume and LinkedIn

## Repository
Name: `Real-Time-Cloud-Event-RSVP-Tracker`
Description: Real-time cloud-based event planning and RSVP platform featuring event management, live RSVP tracking, cloud authentication, capacity control, notifications, analytics, and scalable cloud architecture.
Topics: cloud-computing event-management rsvp realtime python fastapi react websocket cloud-database rest-api serverless authentication (only keep fastapi/react/websocket/serverless if you add them; the built version uses flask + server-sent-events)

```
git init
git add .
git commit -m "Initialize real-time cloud event tracker"
git branch -M main
git remote add origin <repository-url>
git push -u origin main
```
Your GitHub username in profile: Seshu-Konijeti.

## Recommended commit messages (commit each as you really finish it; do not fake dates)
Create cloud event platform architecture | Implement authentication and roles | Add event management module | Implement RSVP workflow | Integrate cloud database | Add real-time RSVP updates | Implement capacity-safe transactions | Add optional waitlist | Build organizer dashboard | Add announcements and notifications | Implement event analytics | Add security controls | Add automated tests | Deploy application to cloud | Complete README and documentation

## 14-day plan
| Day | Do | Files | Commit | Screenshot | Proves |
|---|---|---|---|---|---|
| 1 | Architecture + repo | README, docs/architecture.md, folders | Create cloud event platform architecture | 01_folder_structure | Planned design |
| 2 | Auth + roles | backend/auth.py, cloud/auth_service.py | Implement authentication and roles | 03_register, 04_login | Authentication/RBAC |
| 3 | Event management | routes_events.py, database.py | Add event management module | 06_create_event, 07_published_event | CRUD + validation |
| 4 | RSVP system | routes_rsvp.py | Implement RSVP workflow | 09_rsvp_going, 12_db_rsvp_record | RSVP rules, unique row |
| 5 | Database | database.py, seed.py | Integrate cloud database | 12_db_rsvp_record | Schema and data |
| 6 | Real-time | realtime/, routes_realtime.py | Add real-time RSVP updates | 10_realtime_update, 11_multi_browser | Push updates |
| 7 | Capacity | cloud/database_service.py | Implement capacity-safe transactions | 15_capacity, 16_full_status, 18_race_test | Race-condition safety |
| 8 | Waitlist | promote_from_waitlist | Add optional waitlist | 17_waitlist | FIFO promotion |
| 9 | Organizer dashboard | organizer_dashboard.html, charts.js | Build organizer dashboard | 05_organizer_dashboard | Live charts |
| 10 | Notifications | notification_service.py | Add announcements and notifications | 18_announcement, 19_notification | Event-driven updates |
| 11 | Analytics | analytics/ | Implement event analytics | 20_rsvp_analytics | Metrics |
| 12 | Security + concurrency tests | middleware.py, tests/ | Add security controls; Add automated tests | 22_unauthorized_403, 23_pytest_pass | Security, testing |
| 13 | Deploy | render.yaml, Dockerfile | Deploy application to cloud | 24_deployment_dashboard, 25_live_app | Cloud deployment |
| 14 | Docs | README, report | Complete README and documentation | 26_github_commits, 27_repo, 28_readme | Documentation |

## Screenshot checklist (professional filenames)
01_folder_structure.png, 02_architecture_diagram.png, 03_register_page.png, 04_login_page.png, 05_organizer_dashboard.png, 06_create_event.png, 07_published_event.png, 08_attendee_dashboard.png, 09_event_details.png, 10_rsvp_going.png, 11_rsvp_maybe.png, 12_realtime_count_update.png, 13_multi_browser_demo.png, 14_rsvp_database_record.png, 15_capacity_utilization.png, 16_full_event_status.png, 17_waitlist.png, 18_announcement.png, 19_notification.png, 20_rsvp_analytics.png, 21_concurrency_test.png, 22_unauthorized_action_rejected.png, 23_automated_tests_pass.png, 24_cloud_deployment_dashboard.png, 25_live_application.png, 26_github_commits.png, 27_github_repository.png, 28_readme_preview.png

## Resume (adjust to what you truly complete)
- Built a real-time event and RSVP platform (Flask, SQL, Server-Sent Events) that pushes live Going/Maybe/Not Going counts to organizer dashboards without page refresh.
- Eliminated seat overbooking under concurrent requests using atomic conditional updates; verified with a multi-threaded test (12 requests, 3 seats, zero oversell).
- Implemented RBAC, FIFO waitlist auto-promotion, notifications, analytics charts, rate limiting and CSRF protection; 32 automated pytest tests with GitHub Actions CI.
Two-line description: Real-time event planning and RSVP tracker with live attendance dashboards, concurrency-safe capacity control and waitlist. Flask, SQLAlchemy, SSE, pytest, Docker, CI.
LinkedIn: I built a cloud-oriented Real-Time Event Planning and RSVP Tracker for my Cloud Computing course. Organizers create events and watch RSVPs update live; attendees RSVP from any device. The interesting part was concurrency: I fixed the "last seat" race condition with an atomic conditional database update and proved it with a multi-threaded test. Also built role-based access, FIFO waitlist, notifications, analytics, CI, and Docker/Render deployment files. Code on GitHub.
Skills: Python, Flask, REST APIs, SQL/SQLAlchemy, real-time systems (SSE), concurrency control, RBAC, testing (pytest), CI/CD, Docker, cloud architecture.
