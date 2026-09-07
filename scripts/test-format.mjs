// Tests for src/web/format.js — the arithmetic of a limit row (task T2.20).
//
//   node scripts/test-format.mjs
//
// These cover the parts that fail invisibly: cell geometry that must never draw a
// clipped cell, the elapsed share, and the duration wording. Both directions where
// it matters: the value asked for AND the value that must not appear.
import assert from 'node:assert/strict';
import {
  windowMs, elapsedShare, cellGeometry, formatDuration,
  formatResetMoment, formatReset, rowLabel, sortLimits, severityOf,
  isRetryable, retryDelay, MAX_RETRIES,
  moveTo, applyOrder, dropIndexFor, landingIndex,
} from '../src/web/format.js';

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

console.log('format.js');

// -- windows and the elapsed share ------------------------------------------

test('session window is 5h, weekly is 7d', () => {
  assert.equal(windowMs('session'), 5 * 3600_000);
  assert.equal(windowMs('weekly_all'), 7 * 86400_000);
  assert.equal(windowMs('weekly_scoped'), 7 * 86400_000);
});

test('elapsed share: start, middle and end of a session window', () => {
  const now = Date.parse('2026-09-07T12:00:00Z');
  const end = (h) => new Date(now + h * 3600_000).toISOString();
  assert.equal(elapsedShare('session', end(5), now), 0);      // just started
  assert.equal(elapsedShare('session', end(2.5), now), 0.5);  // halfway
  assert.equal(elapsedShare('session', end(0), now), 1);      // resetting now
});

test('elapsed share clamps instead of going negative or past one', () => {
  const now = Date.parse('2026-09-07T12:00:00Z');
  const past = new Date(now - 3600_000).toISOString();        // reset already gone
  const far = new Date(now + 99 * 3600_000).toISOString();    // impossibly far
  assert.equal(elapsedShare('session', past, now), 1);
  assert.equal(elapsedShare('session', far, now), 0);
});

test('elapsed share of a missing or unparsable reset is zero, not NaN', () => {
  assert.equal(elapsedShare('session', null), 0);
  assert.equal(elapsedShare('session', 'not a date'), 0);
});

// -- cell geometry: the rule is "whole cell or none" -------------------------

test('cells: a 342 px column holds 34 cells and the bar shrinks to fit them', () => {
  const g = cellGeometry(342, 74);
  assert.equal(g.cells, 34);
  assert.equal(g.barWidth, 34 * 10 - 2);
  assert.equal(g.filledCells, Math.round(0.74 * 34));   // 25
  assert.equal(g.fillWidth, 25 * 10 - 2);
});

test('cells: the fill is never a fraction of a cell', () => {
  // The invariant is "zero, or a whole number of cells" — zero is a legal width,
  // and the first version of this test forgot that and failed on 1 %.
  for (const pct of [1, 7, 33, 49, 51, 66, 99]) {
    const g = cellGeometry(342, pct);
    assert.ok(g.fillWidth === 0 || (g.fillWidth + 2) % 10 === 0,
      `pct=${pct} produced a clipped cell: ${g.fillWidth}px`);
  }
});

test('cells: usage below half a cell shows NOTHING — spec behaviour, recorded on purpose', () => {
  // 01.1 §2.2 says round(), so 1 % of 34 cells rounds to zero and the bar is empty
  // while the account has spent something. That is the spec, and it is deliberate
  // here rather than accidental: the percent column beside the bar still reads 1 %,
  // so the number is never hidden — only the bar rounds. If this ever reads wrong to
  // the owner, the change is round() -> "at least one cell when percent > 0", and it
  // belongs in the spec first.
  assert.equal(cellGeometry(342, 1).filledCells, 0);
  assert.equal(cellGeometry(342, 2).filledCells, 1, 'just above half a cell must light one');
});

test('cells: 0% draws nothing, 100% fills the whole bar', () => {
  assert.equal(cellGeometry(342, 0).fillWidth, 0);
  const full = cellGeometry(342, 100);
  assert.equal(full.fillWidth, full.barWidth);
});

test('cells: a column too narrow for one cell yields an empty geometry, not junk', () => {
  const g = cellGeometry(4, 50);
  assert.equal(g.cells, 0);
  assert.equal(g.barWidth, 0);
  assert.equal(g.fillWidth, 0);
});

test('ghost: drawn only ahead of the present, and never behind it', () => {
  const ahead = cellGeometry(342, 40, 70);
  assert.ok(ahead.ghostWidth > 0);
  assert.equal(ahead.ghostFrom, ahead.filledCells * 10);
  assert.equal(cellGeometry(342, 40, 40).ghostWidth, 0, 'equal forecast must draw nothing');
  assert.equal(cellGeometry(342, 40, 10).ghostWidth, 0, 'forecast behind must draw nothing');
  assert.equal(cellGeometry(342, 40, null).ghostWidth, 0, 'absent forecast must draw nothing');
});

// -- wording -----------------------------------------------------------------

test('duration: two largest units, minutes padded only after hours', () => {
  assert.equal(formatDuration(2 * 86400_000 + 17 * 3600_000), '2d 17h');
  assert.equal(formatDuration(3600_000 + 2 * 60_000), '1h 02m');
  assert.equal(formatDuration(45 * 60_000), '45m');
  assert.equal(formatDuration(5 * 60_000), '5m');          // NOT 05m: that reads as a clock
});

test('duration: never negative', () => {
  assert.equal(formatDuration(-5000), '0m');
});

test('reset moment: bare time today, weekday this week, day and month beyond six days', () => {
  const now = Date.parse('2026-09-07T12:00:00Z');
  const iso = (d) => new Date(now + d).toISOString();
  assert.match(formatResetMoment(iso(2 * 3600_000), now), /^\d{2}:\d{2}$/);
  assert.match(formatResetMoment(iso(2 * 86400_000), now), /^[A-Z][a-z]{2} \d{2}:\d{2}$/);
  assert.match(formatResetMoment(iso(8 * 86400_000), now), /^\d{1,2} [A-Z][a-z]{2} \d{2}:\d{2}$/);
});

test('reset caption pairs the moment with the remainder', () => {
  const now = Date.parse('2026-09-07T12:00:00Z');
  const at = new Date(now + 2 * 86400_000 + 17 * 3600_000).toISOString();
  assert.match(formatReset(at, now), /^[A-Z][a-z]{2} \d{2}:\d{2} \(2d 17h\)$/);
  assert.equal(formatReset(null, now), '—', 'a window with no reset must not print a fake one');
});

// -- labels, order, severity --------------------------------------------------

test('row label names the model for a scoped window', () => {
  assert.equal(rowLabel({ kind: 'session' }), 'session 5h');
  assert.equal(rowLabel({ kind: 'weekly_all' }), 'all 7d');
  assert.equal(rowLabel({ kind: 'weekly_scoped', model: 'Fable' }), 'Fable 7d');
  assert.equal(rowLabel({ kind: 'weekly_scoped', scope: { model: { display_name: 'Opus' } } }), 'Opus 7d');
  assert.equal(rowLabel({ kind: 'weekly_scoped' }), 'scoped 7d', 'a nameless scoped row must stay distinguishable');
});

test('order is session, all, then models alphabetically — and is stable', () => {
  const given = [
    { kind: 'weekly_scoped', model: 'Opus' },
    { kind: 'weekly_all' },
    { kind: 'weekly_scoped', model: 'Fable' },
    { kind: 'session' },
  ];
  assert.deepEqual(sortLimits(given).map(rowLabel),
    ['session 5h', 'all 7d', 'Fable 7d', 'Opus 7d']);
  assert.equal(given[0].model, 'Opus', 'sorting must not mutate the caller array');
});

test('locked is red at any percent', () => {
  assert.equal(severityOf({ percent: 40, severity: 'normal', locked_reason: 'usage_limit_reached' }), 'critical');
  assert.equal(severityOf({ percent: 95, severity: 'warning' }), 'warning');
  assert.equal(severityOf({ percent: 5 }), 'normal');
});

// -- retry policy (01.3 §5) ---------------------------------------------------

test('only reads retry, and a 4xx other than 429 never does', () => {
  assert.equal(isRetryable('GET', 500), true);
  assert.equal(isRetryable('GET', 503), true);
  assert.equal(isRetryable('GET', 429), true);
  assert.equal(isRetryable('GET', 0), true, 'a network failure must be retryable');
  assert.equal(isRetryable('GET', 404), false);
  assert.equal(isRetryable('GET', 422), false);
  assert.equal(isRetryable('GET', 412), false);
});

test('writes are never retried automatically, not even on 429 or 500', () => {
  for (const s of [429, 500, 503, 0]) {
    assert.equal(isRetryable('POST', s), false, `POST must not auto-retry on ${s}`);
    assert.equal(isRetryable('PUT', s), false, `PUT must not auto-retry on ${s}`);
  }
});

test('Retry-After wins over the computed backoff', () => {
  assert.equal(retryDelay(1, 120), 120_000);
  assert.equal(retryDelay(3, 5), 5_000, 'the header must beat the exponential too');
  assert.equal(retryDelay(1, 0), 0, 'Retry-After: 0 means now, not "ignore me"');
});

test('backoff grows, is capped, and carries jitter of ±25%', () => {
  const mid = () => 0.5;                       // no jitter
  assert.equal(retryDelay(1, null, mid), 1000);
  assert.equal(retryDelay(2, null, mid), 2000);
  assert.equal(retryDelay(3, null, mid), 4000);
  assert.equal(retryDelay(9, null, mid), 8000, 'must cap, not grow forever');
  assert.equal(retryDelay(1, null, () => 0), 750);
  assert.equal(retryDelay(1, null, () => 0.999), 1250);
});

test('three attempts is the limit', () => {
  assert.equal(MAX_RETRIES, 3);
});

// -------------------------------------------------- account order (T2.22) --

test('moveTo returns a new array and leaves the old one alone', () => {
  const src = ['a', 'b', 'c'];
  const out = moveTo(src, 0, 2);
  assert.deepEqual(out, ['b', 'c', 'a']);
  assert.deepEqual(src, ['a', 'b', 'c'], 'the caller keeps this one to roll back to');
});

test('moveTo clamps instead of dropping the item off the end', () => {
  assert.deepEqual(moveTo(['a', 'b', 'c'], 0, 99), ['b', 'c', 'a']);
  assert.deepEqual(moveTo(['a', 'b', 'c'], 2, -5), ['c', 'a', 'b']);
  assert.deepEqual(moveTo(['a', 'b', 'c'], 7, 0), ['a', 'b', 'c'], 'a bogus source is a no-op');
});

test('applyOrder: named first in order, the rest in discovery order', () => {
  const accs = [{ email: 'a@x' }, { email: 'b@x' }, { email: 'c@x' }, { email: 'd@x' }];
  assert.deepEqual(applyOrder(accs, ['c@x', 'a@x']).map((a) => a.email),
    ['c@x', 'a@x', 'b@x', 'd@x']);
});

test('applyOrder matches e-mails case-insensitively', () => {
  const accs = [{ email: 'A@X.com' }, { email: 'b@x.com' }];
  assert.deepEqual(applyOrder(accs, ['b@x.com', 'a@x.COM']).map((a) => a.email),
    ['b@x.com', 'A@X.com']);
});

test('applyOrder with no order at all changes nothing', () => {
  const accs = [{ email: 'b@x' }, { email: 'a@x' }];
  assert.deepEqual(applyOrder(accs, null).map((a) => a.email), ['b@x', 'a@x']);
  assert.deepEqual(applyOrder(accs, []).map((a) => a.email), ['b@x', 'a@x']);
});

test('applyOrder is stable: unlisted accounts do not shuffle between polls', () => {
  const accs = 'abcdefghij'.split('').map((c) => ({ email: `${c}@x` }));
  const once = applyOrder(accs, ['j@x']).map((a) => a.email);
  assert.deepEqual(once, ['j@x', ...'abcdefghi'.split('').map((c) => `${c}@x`)]);
});

test('dropIndexFor: the midpoint is the boundary', () => {
  const rects = [{ top: 0, bottom: 90 }, { top: 100, bottom: 190 }, { top: 200, bottom: 290 }];
  assert.equal(dropIndexFor(rects, 10), 0, 'above the first midpoint: before everything');
  assert.equal(dropIndexFor(rects, 44), 0);
  assert.equal(dropIndexFor(rects, 46), 1, 'past the first midpoint: after the first');
  assert.equal(dropIndexFor(rects, 160), 2);
  assert.equal(dropIndexFor(rects, 999), 3, 'below everything: at the end');
  assert.equal(dropIndexFor([], 50), 0, 'an empty list has exactly one slot');
});

test('landingIndex corrects only for a move downwards', () => {
  assert.equal(landingIndex(0, 2), 1, 'the list closes up behind the card as it leaves');
  assert.equal(landingIndex(3, 1), 1, 'moving up needs no correction');
  assert.equal(landingIndex(2, 2), 2, 'dropping into its own slot is a no-op');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
