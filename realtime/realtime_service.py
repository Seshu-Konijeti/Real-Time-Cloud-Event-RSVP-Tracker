"""
Real-time service: in-process pub/sub broker feeding Server-Sent Events (SSE).

Flow: RSVP committed -> publish_update(event_id) -> every browser subscribed to
/api/events/<id>/stream receives the fresh counters instantly (server PUSH).

Scaling note: this broker lives in one process. For several server instances put
Redis Pub/Sub (or a managed service: API Gateway WebSocket, Supabase Realtime,
Firestore listeners) behind the same publish()/subscribe() interface.
"""
import json
import logging
import queue
import threading
from collections import defaultdict

log = logging.getLogger("realtime")


class Broker:
    def __init__(self):
        self._subs = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, key, maxsize=100):
        q = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subs[key].add(q)
        return q

    def unsubscribe(self, key, q):
        with self._lock:
            self._subs[key].discard(q)
            if not self._subs[key]:
                self._subs.pop(key, None)

    def subscriber_count(self, key):
        with self._lock:
            return len(self._subs.get(key, ()))

    def publish(self, key, payload):
        msg = json.dumps(payload)
        with self._lock:
            targets = list(self._subs.get(key, ()))
        for q in targets:
            try:
                q.put_nowait(msg)
            except queue.Full:
                # slow/dead client: drop this message, never block the RSVP request
                log.warning("subscriber queue full for %s; dropping message", key)


broker = Broker()


def publish_update(event_id):
    """Publish the latest analytics snapshot. Must NEVER break the caller."""
    try:
        from analytics.event_analytics import compute_snapshot
        snap = compute_snapshot(event_id)
        if snap:
            broker.publish(event_id, snap)
    except Exception:
        log.exception("realtime publish failed (ignored)")
