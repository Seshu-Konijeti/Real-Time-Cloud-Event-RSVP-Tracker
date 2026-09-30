# Test Matrix (generated from a real pytest run)

| Test ID | Scenario | Input | Expected Result | Actual Result | Pass/Fail |
|---|---|---|---|---|---|
| T01 | User registration | name,email,password | 201 and user returned | As expected | PASS |
| T02 | Duplicate registration | same email twice | 409 conflict | As expected | PASS |
| T03 | Login | valid and invalid password | 200 valid, 401 invalid | As expected | PASS |
| T04 | Organizer creates event | valid payload | 201, status PUBLISHED | As expected | PASS |
| T05 | Attendee blocked from organizer API | POST /events as attendee | 403 | As expected | PASS |
| T06 | Event retrieval | GET /events and /events/{id} | event present, unknown id 404 | As expected | PASS |
| T07 | Valid RSVP | GOING | 200, going=1, confirmation notification | As expected | PASS |
| T08 | Duplicate RSVP prevention | same RSVP twice + raw duplicate insert | count stays 1, DB rejects duplicate row | As expected | PASS |
| T09 | Update GOING to MAYBE | change RSVP | going 0, maybe 1 | As expected | PASS |
| T10 | Update MAYBE to GOING | change RSVP | going 1, maybe 0 | As expected | PASS |
| T11 | Cancel RSVP | DELETE /rsvp | going back to 0, second cancel 404 | As expected | PASS |
| T12 | Registration deadline | RSVP after deadline | 400 deadline_passed | As expected | PASS |
| T13 | Capacity enforcement | 3rd GOING on capacity 2 | 409 event_full, status FULL, waitlist 1 | As expected | PASS |
| T14 | Simultaneous final-seat requests | 12 threads, 3 seats | going never exceeds 3 | As expected | PASS |
| T15 | Waitlist FIFO promotion | GOING cancels | first waiting user promoted and notified | As expected | PASS |
| T16 | Announcement creation | organizer posts | 201, visible to attendees | As expected | PASS |
| T17 | Notification generation | announcement, venue change, mark read | notifications created and markable read | As expected | PASS |
| T18 | Unauthorized event modification | other organizer / attendee edits, cancels, deletes | 403 | As expected | PASS |
| T19 | Unauthorized RSVP modification | user B deletes/edits A's RSVP, forged counts | A's RSVP untouched, counters backend-owned | As expected | PASS |
| T20 | Real-time counter update | RSVP with a subscriber connected | subscriber receives pushed going=1 then going=2 | As expected | PASS |
| T21 | Analytics calculation | 4 invited, 2 responded (1 going,1 maybe), cap 4 | response 50%, conversion 50%, utilization 25%, seats 3 | As expected | PASS |
| T22 | Database failure | commit raises mid-RSVP | graceful 500 JSON, transaction rolled back, counters unchanged | As expected | PASS |
| T23 | Real-time connection failure | dead/slow subscriber, then reconnect | RSVP still succeeds, reconnect gets fresh state | As expected | PASS |
| T24 | Authentication token expiry | session cleared/expired | protected APIs return 401 until re-login | As expected | PASS |
| T25 | Event cancellation | organizer cancels | status CANCELLED, attendees notified, new RSVP rejected | As expected | PASS |
| EXTRA | test_X_admin_apis |  |  | As expected | PASS |
| EXTRA | test_X_capacity_increase_promotes_waitlist |  |  | As expected | PASS |
| EXTRA | test_X_csrf_header_required |  |  | As expected | PASS |
| EXTRA | test_X_draft_hidden_and_time_change_notifies |  |  | As expected | PASS |
| EXTRA | test_X_email_failure_does_not_block |  |  | As expected | PASS |
| EXTRA | test_X_idempotency_key_replay |  |  | As expected | PASS |
| EXTRA | test_X_rate_limit |  |  | As expected | PASS |
