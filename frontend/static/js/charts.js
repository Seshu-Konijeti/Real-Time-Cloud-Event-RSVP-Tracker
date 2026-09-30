// Tiny dependency-free canvas charts (works offline, no CDN).
const COLORS = { going: "#16a34a", maybe: "#d97706", not_going: "#dc2626", grey: "#e5e7eb", primary: "#4f46e5", text: "#1f2333" };

function _ctx(canvas) {
  const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const c = canvas.getContext("2d"); c.scale(dpr, dpr); c.clearRect(0, 0, w, h);
  c.font = "12px sans-serif"; c.fillStyle = COLORS.text; return { c, w, h };
}

function donutChart(canvas, parts) {   // parts: [{label,value,color}]
  const { c, w, h } = _ctx(canvas), total = parts.reduce((s, p) => s + p.value, 0);
  const cx = h / 2, cy = h / 2, r = h / 2 - 8;
  if (!total) { c.textAlign = "center"; c.fillText("No responses yet", w / 2, h / 2); return; }
  let a = -Math.PI / 2;
  parts.forEach(p => {
    const s = p.value / total * Math.PI * 2; c.beginPath(); c.moveTo(cx, cy);
    c.arc(cx, cy, r, a, a + s); c.closePath(); c.fillStyle = p.color; c.fill(); a += s;
  });
  c.beginPath(); c.arc(cx, cy, r * 0.58, 0, Math.PI * 2); c.fillStyle = "#fff"; c.fill();
  c.fillStyle = COLORS.text; c.textAlign = "center"; c.font = "bold 16px sans-serif"; c.fillText(total, cx, cy + 5);
  c.font = "12px sans-serif"; c.textAlign = "left";
  parts.forEach((p, i) => { c.fillStyle = p.color; c.fillRect(h + 10, 20 + i * 22, 12, 12);
    c.fillStyle = COLORS.text; c.fillText(`${p.label}: ${p.value}`, h + 28, 31 + i * 22); });
}

function barChart(canvas, bars, max) {   // bars: [{label,value,color}]
  const { c, w, h } = _ctx(canvas), m = max || Math.max(1, ...bars.map(b => b.value));
  const bw = Math.min(60, (w - 40) / bars.length - 12), base = h - 24;
  bars.forEach((b, i) => {
    const x = 30 + i * (bw + 16), bh = (b.value / m) * (base - 18);
    c.fillStyle = b.color; c.fillRect(x, base - bh, bw, bh);
    c.fillStyle = COLORS.text; c.textAlign = "center";
    c.fillText(b.value, x + bw / 2, base - bh - 4); c.fillText(b.label, x + bw / 2, h - 8);
  });
}

function gaugeBar(canvas, pct, label) {  // horizontal progress bar
  const { c, w, h } = _ctx(canvas);
  c.fillStyle = COLORS.grey; c.fillRect(10, h / 2 - 8, w - 20, 16);
  if (pct != null) { c.fillStyle = COLORS.primary; c.fillRect(10, h / 2 - 8, (w - 20) * Math.min(pct, 100) / 100, 16); }
  c.textAlign = "left"; c.fillStyle = COLORS.text;
  c.fillText(pct == null ? `${label}: n/a (invite people first)` : `${label}: ${pct}%`, 10, h / 2 - 16);
}

function lineChart(canvas, points) {     // points: [{label,value}]
  const { c, w, h } = _ctx(canvas);
  if (!points.length) { c.textAlign = "center"; c.fillText("No RSVP history yet", w / 2, h / 2); return; }
  const max = Math.max(1, ...points.map(p => p.value)), L = 34, B = h - 24, T = 12, R = w - 12;
  c.strokeStyle = COLORS.grey; c.beginPath(); c.moveTo(L, T); c.lineTo(L, B); c.lineTo(R, B); c.stroke();
  const xs = i => points.length === 1 ? (L + R) / 2 : L + (R - L) * i / (points.length - 1);
  const ys = v => B - (B - T) * v / max;
  c.strokeStyle = COLORS.primary; c.lineWidth = 2; c.beginPath();
  points.forEach((p, i) => i ? c.lineTo(xs(i), ys(p.value)) : c.moveTo(xs(i), ys(p.value))); c.stroke();
  c.fillStyle = COLORS.primary; points.forEach((p, i) => { c.beginPath(); c.arc(xs(i), ys(p.value), 3, 0, 7); c.fill(); });
  c.fillStyle = COLORS.text; c.textAlign = "right"; c.fillText(max, L - 4, T + 4); c.fillText(0, L - 4, B);
  c.textAlign = "center"; c.fillText(points[0].label.slice(5), L + 20, h - 8);
  if (points.length > 1) c.fillText(points[points.length - 1].label.slice(5), R - 20, h - 8);
}
