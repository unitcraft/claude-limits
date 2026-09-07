// chart.js — the geometry of a history chart (task T2.23), and nothing else.
//
// Pure: takes numbers and ISO stamps, returns numbers and path strings. No DOM, no
// fetch, no document. Tested under node by scripts/test-chart.mjs.
//
// It lives apart from the renderer for the reason format.js does: a chart that is
// wrong by a few pixels still LOOKS like a chart. A line that ignores a gap, a lock
// band drawn a day off, a reset vertical at the wrong hour — every one of those
// passes an eye check and is caught only by asserting the coordinates.
//
// Everything here follows subplan 01.1 §6.4.

/**
 * The drawing box, in the fixed viewBox of §6.4. The SVG is 280x84 and stretches to
 * the column's width; the plot itself stops short of the bottom so the x labels have
 * their own band rather than overprinting the line.
 */
export const BOX = { w: 280, h: 84, top: 3, bottom: 66, labelY: 79 };

/** Time -> x. Outside the range it still returns a number: callers clip, not guess. */
export function xOf(at, from, to, box = BOX) {
  const t = typeof at === 'number' ? at : Date.parse(at);
  const a = typeof from === 'number' ? from : Date.parse(from);
  const b = typeof to === 'number' ? to : Date.parse(to);
  if (!Number.isFinite(t) || !(b > a)) return 0;
  return ((t - a) / (b - a)) * box.w;
}

/** Percent -> y. 100 % is the TOP of the plot area (§6.4), so the axis is inverted. */
export function yOf(percent, box = BOX) {
  const p = Math.max(0, Math.min(100, Number(percent) || 0));
  return box.bottom - (p / 100) * (box.bottom - box.top);
}

const round = (n) => Math.round(n * 10) / 10;

/**
 * Are these two points separated by a gap? A gap is an interval the backend reports
 * in `gaps[]` (429, network) — the line must BREAK there rather than draw a straight
 * segment across it (§6.4). Drawing through would invent a measurement that was
 * never taken, and it is exactly the hours a person wants to know about.
 */
function spansGap(t1, t2, gaps) {
  for (const g of gaps) {
    const gf = Date.parse(g.from);
    const gt = g.to ? Date.parse(g.to) : Infinity;
    if (gf < t2 && gt > t1) return true;
  }
  return false;
}

/**
 * The polyline through the samples, as an SVG path. Straight between samples, no
 * interpolation (§6.4). Returns '' for nothing to draw — an empty `d` renders as
 * nothing, which is the honest picture of an account with no history.
 */
export function linePath(points, range, gaps = [], box = BOX) {
  if (!points || !points.length) return '';
  const parts = [];
  let prev = null;
  for (const p of points) {
    const t = Date.parse(p.at);
    if (!Number.isFinite(t)) continue;
    const x = round(xOf(t, range.from, range.to, box));
    const y = round(yOf(p.percent, box));
    const restart = prev === null || spansGap(prev, t, gaps);
    parts.push(`${restart ? 'M' : 'L'}${x} ${y}`);
    prev = t;
  }
  return parts.join(' ');
}

/**
 * The filled area under the line: the same path, closed down to the baseline.
 *
 * Each unbroken RUN is closed separately. Closing the whole thing once would sweep
 * the fill straight across a gap — the very thing linePath just refused to do, given
 * back by the shading.
 */
export function areaPath(points, range, gaps = [], box = BOX) {
  const line = linePath(points, range, gaps, box);
  if (!line) return '';
  const runs = line.split(/(?=M)/).map((s) => s.trim()).filter(Boolean);
  const out = [];
  for (const run of runs) {
    const coords = run.match(/-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?/g) || [];
    if (coords.length < 2) continue;                  // a lone sample fills nothing
    const firstX = coords[0].split(/\s+/)[0];
    const lastX = coords[coords.length - 1].split(/\s+/)[0];
    out.push(`${run} L${lastX} ${box.bottom} L${firstX} ${box.bottom} Z`);
  }
  return out.join(' ');
}

/**
 * An interval -> a rectangle, clipped to the range. Used for the red `locked` bands
 * and the amber `gap` bands (§6.4). An interval entirely outside the range yields
 * null rather than a zero-width rectangle, so callers can drop it.
 *
 * `to: null` means "still going" and is clipped to the right edge — an open lock is
 * the case a person most needs to see, and it must not vanish for lacking an end.
 */
export function bandRect(interval, range, box = BOX) {
  const a = Date.parse(range.from);
  const b = Date.parse(range.to);
  const f = Math.max(a, Date.parse(interval.from));
  const t = Math.min(b, interval.to ? Date.parse(interval.to) : b);
  if (!Number.isFinite(f) || !Number.isFinite(t) || t <= f) return null;
  const x = round(xOf(f, a, b, box));
  const w = round(xOf(t, a, b, box) - x);
  return { x, width: Math.max(0.5, w), y: box.top, height: box.bottom - box.top };
}

/** Reset moments as x positions, dropping any that fall outside the range (§6.4). */
export function resetLines(resets, range, box = BOX) {
  const a = Date.parse(range.from);
  const b = Date.parse(range.to);
  return (resets || [])
    .map((r) => Date.parse(r))
    .filter((t) => Number.isFinite(t) && t > a && t < b)
    .map((t) => round(xOf(t, a, b, box)));
}

/**
 * A reset inferred from the samples: `percent` falling by more than 30 points
 * between neighbours (§6.4). The backend sends `resets[]` when it knows them; this
 * covers the window whose `resets_at` was never seen, which is every window observed
 * across a restart.
 */
export function inferredResets(points, threshold = 30) {
  const out = [];
  for (let i = 1; i < (points || []).length; i++) {
    const drop = (points[i - 1].percent || 0) - (points[i].percent || 0);
    if (drop > threshold) out.push(points[i].at);
  }
  return out;
}

/**
 * X-axis captions (§6.4): five of them, the last always `now`. The four before it are
 * evenly spaced moments formatted by the range — hours for a day, weekdays for a
 * week, month and day for a month.
 */
export function xTicks(range, kind = '7d', fmt = defaultTickFormat) {
  const a = Date.parse(range.from);
  const b = Date.parse(range.to);
  if (!(b > a)) return [];
  const ticks = [];
  for (let i = 0; i < 4; i++) {
    const t = a + ((b - a) * i) / 4;
    ticks.push({ x: round(xOf(t, a, b)), at: new Date(t).toISOString(), label: fmt(t, kind) });
  }
  ticks.push({ x: BOX.w, at: range.to, label: 'now' });
  return ticks;
}

export function defaultTickFormat(t, kind) {
  const d = new Date(t);
  if (kind === '24h') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  if (kind === '30d') return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  return d.toLocaleDateString('en', { weekday: 'short' });
}

/**
 * The sample nearest a given x, for the hover readout (§6.4: "the point snaps to the
 * nearest sample, no interpolation"). Returns null when there is nothing to snap to.
 */
export function nearestPoint(points, x, range, box = BOX) {
  if (!points || !points.length) return null;
  let best = null;
  let bestDx = Infinity;
  for (let i = 0; i < points.length; i++) {
    const px = xOf(points[i].at, range.from, range.to, box);
    const dx = Math.abs(px - x);
    if (dx < bestDx) { bestDx = dx; best = { index: i, point: points[i], x: round(px) }; }
  }
  return best;
}

/**
 * Group flat `series[]` by account (§6.5: "the series are flat, the page groups them
 * by account_id"). The same join the snapshot needs, and the same trap: assuming the
 * backend nests them draws every card empty.
 */
export function seriesByAccount(series) {
  const out = new Map();
  for (const s of series || []) {
    if (!out.has(s.account_id)) out.set(s.account_id, []);
    out.get(s.account_id).push(s);
  }
  return out;
}

/**
 * The occupancy strip of a folder (§7.3): who was logged in, when, across the whole
 * range — with the UNCOVERED stretches filled in as `no login` rather than left out.
 *
 * The holes are the point. A folder whose login expired two weeks ago has nothing in
 * its journal for those weeks, and a strip that simply ends there looks identical to
 * a strip that runs to the edge under a working login. So the gaps are materialised,
 * with `email: null`, and the renderer paints them grey.
 *
 * `records` are the entries of `occupancy[]` for ONE folder; `to: null` means still
 * current and is clipped to the end of the range.
 */
export function occupancySegments(records, range, box = BOX) {
  const a = Date.parse(range.from);
  const b = Date.parse(range.to);
  if (!(b > a)) return [];

  const spans = (records || [])
    .map((r) => ({
      email: r.email || null,
      token_state: r.token_state || null,
      account_id: r.account_id || null,
      from: Math.max(a, Date.parse(r.from)),
      to: Math.min(b, r.to ? Date.parse(r.to) : b),
    }))
    .filter((s) => Number.isFinite(s.from) && Number.isFinite(s.to) && s.to > s.from)
    .sort((x, y) => x.from - y.from);

  const out = [];
  let cursor = a;
  const push = (from, to, span) => {
    if (to <= from) return;
    const x = round(xOf(from, a, b, box));
    out.push({
      x,
      width: Math.max(0.5, round(xOf(to, a, b, box) - x)),
      from: new Date(from).toISOString(),
      to: new Date(to).toISOString(),
      email: span ? span.email : null,
      token_state: span ? span.token_state : null,
      account_id: span ? span.account_id : null,
    });
  };

  for (const span of spans) {
    push(cursor, Math.min(span.from, b), null);       // the hole before this login
    push(Math.max(cursor, span.from), span.to, span);
    cursor = Math.max(cursor, span.to);
  }
  push(cursor, b, null);                              // and the hole at the end
  return out;
}

/**
 * Colours for accounts, fixed by e-mail at first appearance (§7.1, palette §8) and
 * unchanged by any filter. A colour that moves between accounts when the data is
 * re-fetched makes a month of history unreadable at a glance, which is the only way
 * anyone reads it.
 */
export function accountColors(records) {
  const out = new Map();
  let i = 0;
  for (const r of records || []) {
    const email = r.email;
    if (!email || out.has(email)) continue;
    out.set(email, `var(--series-${(i % 3) + 1})`);
    i += 1;
  }
  return out;
}

/**
 * The three columns of a card (§6.3), in fixed order: the session window, all models,
 * then one line per model. A card always has three columns even when a series is
 * missing — a plan without a per-model limit still gets its column, with the dotted
 * baseline the spec asks for, rather than a hole in the grid.
 */
export function columnsOf(seriesOfAccount) {
  const of = (kind) => (seriesOfAccount || []).filter((s) => s.kind === kind);
  const perModel = of('weekly_scoped')
    .slice()
    .sort((a, b) => String(a.model || '').localeCompare(String(b.model || '')));
  return [
    { key: 'session', title: 'session · 24 h', series: of('session') },
    { key: 'weekly_all', title: 'all models · 7 d', series: of('weekly_all') },
    { key: 'per_model', title: 'per model · 7 d', series: perModel },
  ];
}
