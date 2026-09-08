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
  isRetryable, retryDelay, MAX_RETRIES, refuseFor, REFUSAL_DEFAULT_SEC, REFUSAL_MAX_SEC,
  moveTo, applyOrder, dropIndexFor, landingIndex, orderRequest, configPut,
  footerRight, legendText, footerCounts,
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
    assert.equal(isRetryable('PUT', s, '/api/config'), false, 'a path cannot make a PUT safe');
  }
});

test('the ONE exception is the history search, which is a read wearing POST', () => {
  // 01.3 section 5 names it beside GET; convention section 17 calls it a read.
  // It is a POST only because the filter does not fit in a query string.
  assert.equal(isRetryable('POST', 503, '/api/history/search'), true);
  assert.equal(isRetryable('POST', 429, '/api/history/search'), true);
  assert.equal(isRetryable('POST', 0, '/api/history/search'), true);
  assert.equal(isRetryable('POST', 422, '/api/history/search'), false, '4xx is still 4xx');

  // and it is that path only -- not a prefix of it, not a sibling
  assert.equal(isRetryable('POST', 503, '/api/history'), false);
  assert.equal(isRetryable('POST', 503, '/api/history/search/all'), false);
  assert.equal(isRetryable('POST', 503, '/api/history/search?page=2'), true,
    'a query string does not change which endpoint it is');
});

test('Retry-After wins over the computed backoff', () => {
  assert.equal(retryDelay(1, 120), 120_000);
  assert.equal(retryDelay(3, 5), 5_000, 'the header must beat the exponential too');
  assert.equal(retryDelay(1, 0), 0, 'Retry-After: 0 means now, not "ignore me"');
});

test('backoff is the 0.5 -> 1 -> 2 s of 01.3 section 5, with jitter of +-20%', () => {
  // These three numbers are QUOTED from the spec, not read off the implementation.
  // Until 2026-09-08 both the code and this test said 1 -> 2 -> 4 with +-25 %, and
  // the suite was green the whole time: the test had transcribed the code.
  const mid = () => 0.5;                       // no jitter
  assert.equal(retryDelay(1, null, mid), 500);
  assert.equal(retryDelay(2, null, mid), 1000);
  assert.equal(retryDelay(3, null, mid), 2000);
  assert.equal(retryDelay(9, null, mid), 8000, 'must cap, not grow forever');

  // +-20 %: the spread is what stops several tabs, refused at the same instant,
  // from coming back at the same instant. Asserted as the RANGE the spec states --
  // an exact number here would be arithmetic done by hand (the first version of
  // this line said 2400 and the answer was 2399: rand() never reaches 1).
  for (const [attempt, base] of [[1, 500], [2, 1000], [3, 2000]]) {
    assert.equal(retryDelay(attempt, null, () => 0), Math.round(base * 0.8),
      `attempt ${attempt} at the bottom of the spread`);
    for (const r of [0, 0.001, 0.25, 0.5, 0.75, 0.999]) {
      const d = retryDelay(attempt, null, () => r);
      assert.ok(d >= base * 0.8 && d <= base * 1.2,
        `attempt ${attempt} with rand=${r} gave ${d}, outside +-20 % of ${base}`);
    }
  }
});

test('three attempts is the limit', () => {
  assert.equal(MAX_RETRIES, 3);
});

// ------------------------------- the refresh button after a 429 (T2.21) -----

test('only a 429 blocks the refresh button', () => {
  assert.equal(refuseFor(202, null), 0, '202 is the normal answer: queued');
  assert.equal(refuseFor(200, '30'), 0, 'a Retry-After on a success blocks nothing');
  assert.equal(refuseFor(503, '30'), 0, 'the button is not the retry policy');
  assert.equal(refuseFor(429, '30'), 30);
});

test('a 429 ALWAYS waits for something, whatever the header says', () => {
  // The endpoint has just said it is being asked too often. Waiting too long is a
  // nuisance; not waiting is the thing it complained about.
  for (const h of [null, undefined, '', '   ', 'soon', '12abc', '-5', 'NaN']) {
    assert.equal(refuseFor(429, h), REFUSAL_DEFAULT_SEC, `header ${JSON.stringify(h)}`);
  }
});

test('Retry-After may be an HTTP-date (RFC 9110 10.2.3), not only seconds', () => {
  // This is the case the inline version got wrong: Number(<date>) is NaN, and
  // setTimeout(fn, NaN) runs on the next tick -- so an unparsed header meant no wait.
  const now = Date.parse('2026-09-08T19:00:00Z');
  assert.equal(refuseFor(429, 'Tue, 08 Sep 2026 19:00:45 GMT', now), 45);
  assert.equal(refuseFor(429, 'Tue, 08 Sep 2026 18:59:00 GMT', now), REFUSAL_DEFAULT_SEC,
    'a date already past still leaves the 429 standing');
});

test('one absurd header cannot disable the button for the session', () => {
  assert.equal(refuseFor(429, '999999999'), REFUSAL_MAX_SEC);
  const now = Date.parse('2026-09-08T19:00:00Z');
  assert.equal(refuseFor(429, 'Fri, 08 Sep 2028 19:00:00 GMT', now), REFUSAL_MAX_SEC);
});

test('zero means now, and is not confused with a missing header', () => {
  assert.equal(refuseFor(429, '0'), 0, 'the server says it is ready again');
});

// -------------------------------------------------- account order (T2.22) --

test('the settings PUT is the same envelope, around whatever partial body (T2.25)', () => {
  const r = configPut('"e1"', { poll: { interval_sec: 900 } });
  assert.equal(r.method, 'PUT');
  assert.equal(r.headers['if-match'], '"e1"');
  assert.equal(r.headers.accept, 'application/json');
  assert.deepEqual(JSON.parse(r.body), { poll: { interval_sec: 900 } },
    'the body travels as given: deciding WHAT is partial is the panel\'s job, not this one\'s');
});

test('the order PUT is that envelope with one branch in it', () => {
  assert.deepEqual(orderRequest('"e1"', ['a@x']), configPut('"e1"', { ui: { accounts_order: ['a@x'] } }));
});

test('the order PUT carries If-Match and only the ui subtree (T2.22)', () => {
  const r = orderRequest('W/"abc123"', ['b@x', 'a@x']);
  assert.equal(r.method, 'PUT');
  assert.equal(r.headers['if-match'], 'W/"abc123"');
  assert.equal(r.headers['content-type'], 'application/json');
  assert.deepEqual(JSON.parse(r.body), { ui: { accounts_order: ['b@x', 'a@x'] } });
  assert.deepEqual(Object.keys(JSON.parse(r.body)), ['ui'],
    'a full config would make every save a chance to overwrite another tab');
});

test('no ETag means no If-Match, and the 428 that follows is the right answer', () => {
  // Not a hole: the server requires the precondition, so a page that cannot name the
  // version it edited gets refused instead of overwriting somebody blind.
  for (const missing of [null, undefined, '']) {
    const r = orderRequest(missing, ['a@x']);
    assert.ok(!('if-match' in r.headers), `etag ${JSON.stringify(missing)} must not send the header`);
  }
});

test('an empty order is a real value, not an omission', () => {
  // Dragging every account away is legal and means "no preferred order".
  assert.deepEqual(JSON.parse(orderRequest('e', []).body), { ui: { accounts_order: [] } });
});

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

// ------------------------------------------- the footer, 01.1 sec.1.2 -------

test('the right half says how often AND when, as the artboard does', () => {
  // The page printed only "polling every 300 s" until 2026-09-08. `next_poll_at` is
  // in the payload and in the fixture, and it is the half a person waiting for a
  // number actually wants.
  const at = new Date('2026-09-07T16:52:02Z');
  const hhmm = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  assert.equal(footerRight(300, '2026-09-07T16:52:02Z'), `polling every 300 s \u00b7 next ${hhmm}`);
});

test('an unusable next_poll_at drops the clause instead of guessing', () => {
  // `next NaN` is worse than no promise: it reads as a broken clock rather than as
  // an absent one.
  for (const bad of [null, undefined, '', 'soon', 'not-a-date']) {
    assert.equal(footerRight(300, bad), 'polling every 300 s', `next=${JSON.stringify(bad)}`);
  }
});

test('no interval at all means the polling is paused, not "every undefined s"', () => {
  assert.equal(footerRight(null, '2026-09-07T16:52:02Z'), 'polling paused');
  assert.equal(footerRight(0, null), 'polling paused');
});

test('the legend explains only the marks that are on screen', () => {
  const both = legendText({ timeBar: true, forecast: true });
  assert.match(both, /thin line = share of the window elapsed/);
  assert.match(both, /hatched = forecast at reset \(working hours only\)/);
  assert.ok(both.includes('\u00b7'), 'the two halves are separated as in sec.1.2');

  assert.equal(legendText({ timeBar: true, forecast: false }),
    'thin line = share of the window elapsed', 'no forecast, no hatch legend');
  assert.equal(legendText({ timeBar: false, forecast: true }),
    'hatched = forecast at reset (working hours only)');
  assert.equal(legendText({ timeBar: false, forecast: false }), '',
    'nothing drawn, nothing explained -- and the caller hides the separator on empty');
});

test('directories are counted DISTINCTLY: one parent folder holds several logins', () => {
  // `POST /api/folders/probe` exists to report the logins found inside one folder,
  // so two accounts naming the same directory is the normal case, not a corner. A
  // sum over accounts counted it twice; the fixture has no sharing and hid that.
  const shared = [
    { dirs: [{ id: 'd-1' }, { id: 'd-2' }] },
    { dirs: [{ id: 'd-2' }] },
  ];
  assert.equal(footerCounts(shared), '2 logins in 2 directories');
});

test('the footer counts read as English at one', () => {
  assert.equal(footerCounts([{ dirs: [{ id: 'd-1' }] }]), '1 login in 1 directory');
  assert.equal(footerCounts([]), '0 logins in 0 directories');
  assert.equal(footerCounts([{}]), '1 login in 0 directories', 'an account with no dirs');
});

test('a directory identified by path rather than id still counts once', () => {
  const byPath = [{ dirs: [{ path: 'D:/a' }] }, { dirs: [{ path: 'D:/a' }] }];
  assert.equal(footerCounts(byPath), '2 logins in 1 directory');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
