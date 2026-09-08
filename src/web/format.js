// format.js — the pure arithmetic and wording of a limit row (task T2.20).
//
// Separated from app.js for one reason: these are the parts that can be WRONG in a
// way nobody sees. A misplaced rounding in the cell geometry or an off-by-one in the
// elapsed share looks plausible on screen and is only caught by a test — so they
// live here, take no DOM, and are exercised by scripts/test-format.mjs under node.
//
// Everything here follows subplan 01.1 §2. Where the spec gives a formula it is
// transcribed, not reinvented.

/** Window length in ms: five hours for the session, seven days for the weekly ones. */
export function windowMs(kind) {
  return kind === 'session' ? 5 * 3600_000 : 7 * 86400_000;
}

/**
 * Share of the window already elapsed, 0..1 (01.1 §2.6). The page computes this
 * itself from resets_at; the backend sends nothing for it.
 */
export function elapsedShare(kind, resetsAtIso, now = Date.now()) {
  if (!resetsAtIso) return 0;
  const end = Date.parse(resetsAtIso);
  if (Number.isNaN(end)) return 0;
  const w = windowMs(kind);
  return clamp((now - (end - w)) / w, 0, 1);
}

export function clamp(x, lo, hi) {
  return x < lo ? lo : x > hi ? hi : x;
}

/**
 * Cell geometry for the "cells" bar style (01.1 §2.2): a cell is either whole or
 * absent, never clipped. Step 10 px = 8 px cell + 2 px gap; the trailing gap is not
 * drawn, hence the -2.
 */
export function cellGeometry(widthPx, percent, forecastPercent = null) {
  const n = Math.max(0, Math.floor((widthPx + 2) / 10));
  if (n === 0) return { cells: 0, barWidth: 0, fillWidth: 0, filledCells: 0, ghostFrom: 0, ghostWidth: 0 };
  const filled = Math.round(clamp(percent, 0, 100) / 100 * n);
  const geo = {
    cells: n,
    barWidth: n * 10 - 2,
    filledCells: filled,
    fillWidth: filled === 0 ? 0 : filled * 10 - 2,
    ghostFrom: 0,
    ghostWidth: 0,
  };
  // The forecast ghost runs from the filled edge to the predicted cell, and only
  // when the prediction is ahead of the present (01.1 §2.2).
  if (forecastPercent != null && forecastPercent > percent) {
    const to = Math.round(clamp(forecastPercent, 0, 100) / 100 * n);
    if (to > filled) {
      geo.ghostFrom = filled * 10;
      geo.ghostWidth = (to - filled) * 10 - 2;
    }
  }
  return geo;
}

/**
 * Two largest units (01.1 §0): `2d 17h`, `1h 02m`, `45m`. Minutes are zero-padded
 * only when they follow hours — a bare `05m` would read as a clock.
 */
export function formatDuration(ms) {
  const total = Math.max(0, Math.round(ms / 1000));
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m`;
}

/**
 * The reset moment as the row shows it (01.1 §2.4): bare time today, weekday and
 * time within the week, day and month beyond six days.
 */
export function formatResetMoment(resetsAtIso, now = Date.now()) {
  if (!resetsAtIso) return '';
  const at = new Date(resetsAtIso);
  if (Number.isNaN(at.getTime())) return '';
  const hhmm = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  const sameDay = new Date(now).toDateString() === at.toDateString();
  if (sameDay) return hhmm;
  if (at.getTime() - now > 6 * 86400_000) {
    const day = at.getDate();
    const mon = at.toLocaleDateString('en', { month: 'short' });
    return `${day} ${mon} ${hhmm}`;
  }
  return `${at.toLocaleDateString('en', { weekday: 'short' })} ${hhmm}`;
}

/** `Tue 13:00 (2d 17h)` — the whole caption of the reset column. */
export function formatReset(resetsAtIso, now = Date.now()) {
  if (!resetsAtIso) return '—';
  const at = Date.parse(resetsAtIso);
  if (Number.isNaN(at)) return '—';
  return `${formatResetMoment(resetsAtIso, now)} (${formatDuration(at - now)})`;
}

/**
 * The row label (01.1 §2.1). `weekly_scoped` carries the model name; a scoped row
 * without one would be indistinguishable from another, so it falls back visibly.
 */
export function rowLabel(limit) {
  if (limit.kind === 'session') return 'session 5h';
  if (limit.kind === 'weekly_all') return 'all 7d';
  const model = limit.model || (limit.scope && limit.scope.model && limit.scope.model.display_name);
  return `${model || 'scoped'} 7d`;
}

/**
 * Fixed row order (01.1 §2.1): session, all models, then models alphabetically.
 * A stable order matters more than it looks — rows that reshuffle between polls
 * make a page impossible to read at a glance.
 */
export function sortLimits(limits) {
  const rank = (l) => (l.kind === 'session' ? 0 : l.kind === 'weekly_all' ? 1 : 2);
  return [...limits].sort((a, b) =>
    rank(a) - rank(b) || rowLabel(a).localeCompare(rowLabel(b)));
}

/**
 * Severity for colouring. The BACKEND decides it from the user's thresholds, and
 * the endpoint's own `server_severity` is kept for debugging only (01.1 §2.2).
 * `locked` is red at any percent — a locked account at 40 % is still locked.
 */
export function severityOf(limit) {
  if (limit.locked_reason) return 'critical';
  return limit.severity || 'normal';
}

/**
 * May this failure be retried automatically? (01.3 §5, convention §17.)
 *
 * Only reads. A 4xx other than 429 means the request itself is wrong, and repeating
 * it just spends the endpoint's patience — which on this project is not an
 * abstraction: the machine has already been rate-limited for exactly that.
 */
export function isRetryable(method, status, path = '') {
  // A search is a read: 01.3 section 5 names `POST /api/history/search` beside GET,
  // and convention section 17 says the same in general terms ("reads: GET, search,
  // count"). It is a POST only because its filter does not fit in a query string --
  // nothing about it changes state, and the contract declares it safe to repeat.
  // Every OTHER write stays out, with or without a 429.
  const safe = method === 'GET' || method === 'HEAD'
    || (method === 'POST' && path.split('?')[0] === '/api/history/search');
  if (!safe) return false;
  if (status === 429) return true;
  if (status >= 400 && status < 500) return false;
  return status >= 500 || status === 0;     // 0 = network failure, no response
}

/**
 * Delay before attempt N (1-based), in ms. `Retry-After` WINS over any computed
 * value — the server knows when it will be ready and we do not. Otherwise
 * exponential with jitter, so several tabs do not return in lockstep.
 *
 * `rand` is injectable purely so the jitter can be tested.
 */
export function retryDelay(attempt, retryAfterSeconds = null, rand = Math.random) {
  if (retryAfterSeconds != null && retryAfterSeconds >= 0) return retryAfterSeconds * 1000;
  const base = Math.min(500 * 2 ** (attempt - 1), 8000);
  return Math.round(base * (0.8 + rand() * 0.4));        // +-20 %
}

export const MAX_RETRIES = 3;

/** No `Retry-After` we can read means a full minute: the floor the backend enforces. */
export const REFUSAL_DEFAULT_SEC = 60;
/** And a ceiling, so one absurd header cannot disable the button for the session. */
export const REFUSAL_MAX_SEC = 3600;

/**
 * Seconds the "refresh" button stays blocked after a reply, 0 for "not blocked".
 *
 * Only a 429 blocks it. `Retry-After` may be delay-seconds OR an HTTP-date (RFC 9110
 * 10.2.3) -- both are read, and ANYTHING unreadable falls back to the default rather
 * than to zero. Falling back to zero is what the inline version did, via NaN, and it
 * turned the one case it could not parse into no wait at all.
 */
export function refuseFor(status, header, nowMs = Date.now()) {
  if (status !== 429) return 0;
  const raw = (header ?? '').toString().trim();
  if (raw === '') return REFUSAL_DEFAULT_SEC;

  // delay-seconds: the grammar is digits only, so "12abc" is not 12.
  if (/^\d+$/.test(raw)) return Math.min(Number(raw), REFUSAL_MAX_SEC);

  const at = Date.parse(raw);
  if (!Number.isNaN(at)) {
    // A date in the past means "now"; the 429 itself still stands, so wait the
    // default rather than nothing.
    const sec = Math.ceil((at - nowMs) / 1000);
    return sec <= 0 ? REFUSAL_DEFAULT_SEC : Math.min(sec, REFUSAL_MAX_SEC);
  }
  return REFUSAL_DEFAULT_SEC;
}

// ------------------------------------------------------- account order (§4) --

/**
 * Move item `from` to index `to`, returning a NEW array (01.1 §4.1).
 *
 * A copy rather than a splice in place, because the caller keeps the old array to
 * roll back to when the server refuses the new order — and an in-place move would
 * have destroyed exactly the thing the rollback needs.
 */
export function moveTo(list, from, to) {
  const out = [...list];
  if (from < 0 || from >= out.length) return out;
  const clamped = clamp(to, 0, out.length - 1);
  const [item] = out.splice(from, 1);
  out.splice(clamped, 0, item);
  return out;
}

/**
 * Accounts in the configured order (01.1 §4.2): e-mails listed in
 * `ui.accounts_order` first and in that order, everything else after, in the order
 * it was discovered. The key is the e-mail, lowercased — one account may sit in
 * several directories, and the config names it once.
 *
 * The backend already orders `accounts[]` this way (01.3 §3.3), so this exists for
 * the moment BETWEEN a drag and the server's answer: the page shows the new order at
 * once and the next snapshot confirms it. Without it a dropped card would jump back
 * for a second and then settle, which reads as a bug even when it is not.
 */
export function applyOrder(accounts, order) {
  if (!order || !order.length) return [...accounts];
  const rank = new Map(order.map((e, i) => [String(e).toLowerCase(), i]));
  const at = (a) => {
    const r = rank.get(String(a.email || '').toLowerCase());
    return r == null ? order.length : r;
  };
  // Index as the tiebreaker keeps it a STABLE sort even where the engine's is not,
  // so unlisted accounts stay in discovery order rather than shuffling per poll.
  return accounts
    .map((a, i) => [a, i])
    .sort((x, y) => at(x[0]) - at(y[0]) || x[1] - y[1])
    .map(([a]) => a);
}

/**
 * Which slot a pointer at `y` is over, given the cards' vertical extents (01.1 §4.1
 * draws the drop line between cards). `rects` are `{top, bottom}` in the same
 * coordinate space as `y`, in DOM order.
 *
 * The midpoint is the boundary: above it the card lands before, below it after. Any
 * other rule makes the drop line flicker when the pointer hovers an edge.
 */
export function dropIndexFor(rects, y) {
  for (let i = 0; i < rects.length; i++) {
    if (y < (rects[i].top + rects[i].bottom) / 2) return i;
  }
  return rects.length;
}

/**
 * The index the dragged card ends up at, given the SLOT the drop line sits in.
 *
 * These differ by one whenever the card moves down, because removing it first
 * shifts every later slot up. Getting this wrong moves a card one place short and
 * looks like the drag "not quite working" — the classic off-by-one of every
 * reorder list, which is why it is a named function with a test rather than an
 * expression inside an event handler.
 */
export function landingIndex(fromIndex, slot) {
  return slot > fromIndex ? slot - 1 : slot;
}
