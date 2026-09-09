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
/**
 * The zone captions are drawn in: the BACKEND's, which arrives as `SnapshotView.tz`.
 *
 * ONE SETTER RATHER THAN AN ARGUMENT THREADED THROUGH FOUR SIGNATURES. The zone is a
 * property of the whole page, not of a row, and the chain to a caption is
 * renderList -> renderAccount -> renderRow -> formatReset. Passing it down means four
 * places to forget it in, and forgetting it is exactly the defect this replaces --
 * `tz` was carried in every snapshot and read by nothing.
 *
 * A caller may still pass a zone explicitly, which is what the tests and probes do;
 * null means "whatever the page is set to", and an unset page means the viewer's own
 * zone, as before.
 */
let captionZone = null;

export function setCaptionZone(tz) {
  captionZone = tz || null;
}

export function getCaptionZone() {
  return captionZone;
}

/**
 * A clock caption in the page's zone. Every "19:47" on this page goes through here.
 *
 * WHY A FUNCTION AND NOT `toLocaleTimeString` AT EACH SITE. There were ten of those,
 * in three syntaxes, and the audit that found them had to classify each one by hand
 * as a caption or an axis. Captions belong in the backend's zone and axes in the
 * browser's -- plan 01 §3.4, verbatim: "готовые подписи `*_label` считаются в поясе
 * бэкенда, оси графиков страница строит в поясе браузера". A shared function makes
 * the caption case the easy one to reach for; the axis case stays an explicit,
 * visible choice in chart.js rather than an accident.
 */
export function captionTime(d) {
  const at = d instanceof Date ? d : new Date(d);
  if (Number.isNaN(at.getTime())) return '';
  const opts = { hour: '2-digit', minute: '2-digit', hour12: false };
  return at.toLocaleTimeString('en', captionZone ? { ...opts, timeZone: captionZone } : opts);
}

/** The same, with the date, for tables that span days. */
export function captionDateTime(d) {
  const at = d instanceof Date ? d : new Date(d);
  if (Number.isNaN(at.getTime())) return '';
  const opts = { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false };
  return at.toLocaleString('en', captionZone ? { ...opts, timeZone: captionZone } : opts);
}

export function formatResetMoment(resetsAtIso, now = Date.now(), tz = captionZone) {
  if (!resetsAtIso) return '';
  const at = new Date(resetsAtIso);
  if (Number.isNaN(at.getTime())) return '';

  // THE ZONE IS THE BACKEND'S, NOT THE BROWSER'S, and `tz` is how it arrives:
  // SnapshotView.tz says so in as many words -- "IANA zone of the BACKEND, for
  // captions; the page draws axes in the browser's zone". 01.1 line 11 says every
  // time example is in the backend machine's zone, and line 44 puts reset captions
  // among the values that come from the backend.
  //
  // Until 2026-09-09 this function called toLocaleTimeString with no zone, so it
  // rendered wherever the viewer happened to be. `tz` was carried in every snapshot,
  // assigned to state.tz, and read by nothing. A viewer three hours away read a
  // reset time three hours wrong, with no way to tell.
  //
  // An unknown zone falls back to the browser's rather than throwing: a wrong-looking
  // caption beats a blank row, and it is what happened before anyway.
  const zoned = (opts) => {
    if (!tz) return opts;
    try {
      // Reject a bad zone here rather than at every call site below.
      new Intl.DateTimeFormat('en', { timeZone: tz });
      return { ...opts, timeZone: tz };
    } catch {
      return opts;
    }
  };

  const hhmm = at.toLocaleTimeString('en', zoned({ hour: '2-digit', minute: '2-digit', hour12: false }));

  // "Same day" must also be asked in that zone -- 23:30 UTC and 02:30 in Moscow are
  // the same instant on different days, and the caption says which.
  const dayOf = (d) => d.toLocaleDateString('en-CA', zoned({
    year: 'numeric', month: '2-digit', day: '2-digit' }));
  if (dayOf(at) === dayOf(new Date(now))) return hhmm;

  if (at.getTime() - now > 6 * 86400_000) {
    const day = at.toLocaleDateString('en', zoned({ day: 'numeric' }));
    const mon = at.toLocaleDateString('en', zoned({ month: 'short' }));
    return `${day} ${mon} ${hhmm}`;
  }
  return `${at.toLocaleDateString('en', zoned({ weekday: 'short' }))} ${hhmm}`;
}

/** `Tue 13:00 (2d 17h)` — the whole caption of the reset column. */
export function formatReset(resetsAtIso, now = Date.now(), tz = captionZone) {
  if (!resetsAtIso) return '—';
  const at = Date.parse(resetsAtIso);
  if (Number.isNaN(at)) return '—';
  // The moment comes from the backend's zone; the countdown is recomputed here every
  // minute (01.1 lines 124 and 148 -- "locally, without asking the backend"). That is
  // why the page does not simply print the backend's `reset_label`, which bundles the
  // two: its countdown would be as old as the last poll.
  return `${formatResetMoment(resetsAtIso, now, tz)} (${formatDuration(at - now)})`;
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
 *
 * `retryAfterSeconds` must come from the parser of the same name, never from
 * `Number(header)`: the header may be an HTTP-date, and `Number` turns that into
 * NaN, which lands here as "no header" and backs off in half a second while the
 * server asked for five minutes.
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
 * `Retry-After` in seconds, or null when there is nothing readable to obey.
 *
 * THE ONE PLACE THE HEADER IS READ. It has two legal forms (RFC 9110 10.2.3):
 * delay-seconds, or an HTTP-date. Anywhere that reads only one of them silently
 * ignores the server half the time.
 *
 * Measured 2026-09-08, before this function existed as a shared door: the GET path
 * did `Number(header)`, which is NaN for a date, and fell through to exponential
 * backoff -- 500 ms. The button path parsed the date properly -- 300 000 ms. The same
 * header, a 600-fold difference, and the short one is the server being ignored
 * rather than obeyed. probes/hunt-conventions-retry-after/measure.mjs is that
 * measurement, and it stays runnable.
 *
 * Returns null rather than a default, so each caller states its own fallback: the
 * button waits a minute, a GET backs off exponentially. Those are different
 * policies and they should be visible as such, but they must read the SAME header.
 */
export function retryAfterSeconds(header, nowMs = Date.now()) {
  const raw = (header ?? '').toString().trim();
  if (raw === '') return null;

  // delay-seconds: the grammar is digits only, so "12abc" is not 12 and "-5" is not
  // a delay. Zero is legal and means "ready now" -- an answer, not an absence.
  if (/^\d+$/.test(raw)) return Math.min(Number(raw), REFUSAL_MAX_SEC);

  // An HTTP-date is a DEADLINE, so report the honest distance to it and let each
  // caller decide. A deadline already past comes back NEGATIVE rather than zero,
  // because the two are not the same answer: an explicit `Retry-After: 0` is the
  // server saying it is ready, while a stale date is a header that arrived late and
  // says nothing reliable about now. Collapsing them made the button obey a
  // half-hour-old date as though the server had just cleared it.
  const at = Date.parse(raw);
  if (!Number.isNaN(at)) {
    const sec = Math.ceil((at - nowMs) / 1000);
    return sec <= 0 ? sec : Math.min(sec, REFUSAL_MAX_SEC);
  }
  return null;
}

/**
 * Seconds the "refresh" button stays blocked after a reply, 0 for "not blocked".
 *
 * Only a 429 blocks it. The header is read by `retryAfterSeconds` -- this function
 * only decides the POLICY: anything unreadable, and anything that says "now", still
 * waits the default, because the 429 itself stands. Falling back to zero is what the
 * inline version did, via NaN, and it turned the one case it could not parse into no
 * wait at all.
 */
export function refuseFor(status, header, nowMs = Date.now()) {
  if (status !== 429) return 0;
  const sec = retryAfterSeconds(header, nowMs);
  // UNREADABLE and ZERO are different answers and must stay different. Null means
  // the server said nothing we can act on, so the default minute applies. Zero means
  // the server said "ready now" -- an explicit `Retry-After: 0`, or a date already
  // past -- and obeying it is obeying the server. Folding the two together is what
  // this refactor did for about four minutes, and test-format.mjs said so.
  if (sec === null) return REFUSAL_DEFAULT_SEC;
  // A deadline already past: the 429 itself still stands, so wait the default
  // rather than nothing. An explicit zero is different and passes straight through.
  if (sec < 0) return REFUSAL_DEFAULT_SEC;
  return Math.min(sec, REFUSAL_MAX_SEC);
}

/**
 * The right half of the footer (01.1 sec.1.2): `polling every 300 s . next 19:52`.
 *
 * The interval says how often; `next_poll_at` says WHEN, which is the half a person
 * waiting for a number actually wants. Absent or unreadable, the clause is dropped
 * rather than guessed -- `next NaN` is worse than no promise at all.
 */
export function footerRight(intervalSec, nextPollAt) {
  if (!intervalSec) return 'polling paused';
  const head = `polling every ${intervalSec} s`;
  if (!nextPollAt) return head;
  const at = new Date(nextPollAt);
  if (Number.isNaN(at.getTime())) return head;
  return `${head} \u00b7 next ${captionTime(at)}`;
}

/**
 * The legend, built from what is actually DRAWN rather than from the config
 * (01.1 sec.1.2: the hatch half only when the forecast is on). A legend explaining a
 * mark that is not on screen teaches the reader to distrust the other half of it.
 */
export function legendText({ timeBar, forecast }) {
  const parts = [];
  if (timeBar) parts.push('thin line = share of the window elapsed');
  if (forecast) parts.push('hatched = forecast at reset (working hours only)');
  return parts.join(' \u00b7 ');
}

/**
 * Logins and the directories holding them, counted DISTINCTLY (01.1 sec.1.2).
 *
 * A sum over accounts double-counts a parent folder that holds several logins, and
 * such a folder is not hypothetical: `POST /api/folders/probe` exists to report the
 * logins found inside one. The fixture happens to have no sharing, so a sum passes
 * there and misreports the moment somebody points the tool at their real folder.
 */
export function footerCounts(accounts) {
  const n = accounts.length;
  const dirs = new Set();
  for (const a of accounts) for (const d of a.dirs || []) dirs.add(d.id || d.path || String(d));
  const k = dirs.size;
  return `${n} login${n === 1 ? '' : 's'} in ${k} director${k === 1 ? 'y' : 'ies'}`;
}

// ------------------------------------------------------- account order (§4) --

/**
 * The `PUT /api/config` that saves an account order (01.3 sec.3.8).
 *
 * `If-Match` is not optional. The endpoint answers 428 without it, which is the safe
 * failure: two tabs dragging cards at once must not silently overwrite each other,
 * and a page that cannot name the version it edited has no business writing. When
 * the GET carried no ETag the header is omitted deliberately -- the 428 that follows
 * is the correct outcome, not a bug to paper over with a blind write.
 *
 * A PARTIAL tree: only `ui.accounts_order`. Sending the whole config back would make
 * every save a chance to overwrite a setting somebody changed in another tab.
 */
export function configPut(etag, body) {
  return {
    method: 'PUT',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      ...(etag ? { 'if-match': etag } : {}),
    },
    body: JSON.stringify(body),
  };
}

/** The order save is one such PUT with a body of exactly one branch. */
export function orderRequest(etag, emails) {
  return configPut(etag, { ui: { accounts_order: emails } });
}

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
