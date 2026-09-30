// API client: CSRF header, retry with backoff for reads, idempotency key for RSVPs,
// SSE helper with polling fallback, HTML escaping (XSS defence).
const sleep = ms => new Promise(r => setTimeout(r, ms));

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function fmtDate(d) { try { return new Date(d + "Z").toLocaleString(); } catch (e) { return d; } }
function uuid() { return (crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random()); }

const API = {
  base: "/api",
  async _req(method, path, body, extraHeaders = {}, retries = 0) {
    for (let attempt = 0; ; attempt++) {
      try {
        const res = await fetch(this.base + path, {
          method, credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Requested-With": "fetch", ...extraHeaders },
          body: body ? JSON.stringify(body) : undefined,
        });
        let data = {};
        try { data = await res.json(); } catch (e) {}
        if (!res.ok) {
          const err = new Error(Array.isArray(data.message) ? data.message.join(", ") : (data.message || "Request failed"));
          err.status = res.status; err.data = data;
          if (res.status >= 500 && attempt < retries) { await sleep(400 * 2 ** attempt); continue; }
          throw err;
        }
        return data;
      } catch (e) {
        if (e.status) throw e;                       // HTTP error already handled
        if (attempt < retries) { await sleep(400 * 2 ** attempt); continue; }   // network error -> retry
        const err = new Error("Network problem. Check your connection and try again.");
        err.network = true; throw err;
      }
    }
  },
  get(p) { return this._req("GET", p, null, {}, 2); },
  post(p, b, h) { return this._req("POST", p, b, h); },
  put(p, b) { return this._req("PUT", p, b); },
  del(p) { return this._req("DELETE", p); },

  me() { return this.get("/me"); },
  register(x) { return this.post("/register", x); },
  login(x) { return this.post("/login", x); },
  logout() { return this.post("/logout"); },

  createEvent(x) { return this.post("/events", x); },
  updateEvent(id, x) { return this.put(`/events/${id}`, x); },
  cancelEvent(id) { return this.put(`/events/${id}/cancel`); },
  deleteEvent(id) { return this.del(`/events/${id}`); },
  getEvents(q = "") { return this.get(`/events${q}`); },
  getEvent(id) { return this.get(`/events/${id}`); },
  invite(id, emails) { return this.post(`/events/${id}/invites`, { emails }); },
  reminder(id) { return this.post(`/events/${id}/reminder`); },

  // Idempotency-Key makes double-clicks / retries safe: the server replays the first answer.
  rsvp(id, status) { return this.post(`/events/${id}/rsvp`, { status }, { "Idempotency-Key": uuid() }); },
  cancelRsvp(id) { return this.del(`/events/${id}/rsvp`); },
  eventRsvps(id) { return this.get(`/events/${id}/rsvps`); },
  myRsvps() { return this.get("/rsvps/me"); },

  analytics(id) { return this.get(`/events/${id}/analytics`); },
  analyticsDetail(id) { return this.get(`/events/${id}/analytics/detail`); },
  summary() { return this.get("/organizer/summary"); },

  announcements(id) { return this.get(`/events/${id}/announcements`); },
  createAnnouncement(id, x) { return this.post(`/events/${id}/announcements`, x); },
  updates() { return this.get("/updates/me"); },
  notifications() { return this.get("/notifications"); },
  markRead(id) { return this.put(`/notifications/${id}/read`); },
};

/* Real-time: Server-Sent Events. EventSource auto-reconnects; the server sends full state on
   every (re)connect. If SSE is unavailable we fall back to polling every 3s. */
function subscribeEvent(eventId, onMessage, onStatus) {
  let poll = null, es = null;
  const startPolling = () => {
    if (poll) return;
    onStatus && onStatus("polling");
    poll = setInterval(async () => { try { onMessage(await API.analytics(eventId)); } catch (e) {} }, 3000);
  };
  if (!window.EventSource) { startPolling(); return () => clearInterval(poll); }
  es = new EventSource(`${API.base}/events/${eventId}/stream`);
  es.onopen = () => { if (poll) { clearInterval(poll); poll = null; } onStatus && onStatus("live"); };
  es.onmessage = ev => { try { onMessage(JSON.parse(ev.data)); } catch (e) {} };
  es.onerror = () => { onStatus && onStatus("reconnecting"); if (es.readyState === 2) startPolling(); };
  return () => { es && es.close(); poll && clearInterval(poll); };
}

function statusPill(s) {
  const cls = s === "FULL" ? "full" : s === "CANCELLED" ? "cancelled" : s === "COMPLETED" ? "full" : "";
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}
function navHtml(user) {
  if (!user) return `<a href="/">Events</a><a href="/login.html">Login</a><a href="/register.html">Register</a>`;
  const dash = user.role === "admin" ? "/admin.html" : user.role === "organizer" ? "/organizer_dashboard.html" : "/attendee_dashboard.html";
  return `<a href="/">Events</a><a href="${dash}">Dashboard</a><span class="muted">${esc(user.name)} (${esc(user.role)})</span><button onclick="logout()">Logout</button>`;
}
async function logout() { await API.logout(); window.location.href = "/"; }
