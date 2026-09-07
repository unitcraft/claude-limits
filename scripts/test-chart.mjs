// Tests for src/web/chart.js — the geometry of a history chart (task T2.23).
//
//   node scripts/test-chart.mjs
//
// A chart that is wrong still looks like a chart. These assert the coordinates, and
// especially the two things an eye cannot check: that the line BREAKS across a gap
// instead of inventing a measurement, and that a lock still running is drawn to the
// right edge rather than dropped for having no end.
import assert from 'node:assert/strict';
import {
  BOX, xOf, yOf, linePath, areaPath, bandRect, resetLines, inferredResets,
  xTicks, nearestPoint, seriesByAccount, columnsOf,
} from '../src/web/chart.js';

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

// A tidy 24-hour range so every coordinate is arithmetic a reader can check by hand.
const RANGE = { from: '2026-09-07T00:00:00Z', to: '2026-09-08T00:00:00Z', step_sec: 300 };
const at = (h, m = 0) => `2026-09-07T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00Z`;

console.log('axes');

test('time maps across the full width, ends included', () => {
  assert.equal(xOf(RANGE.from, RANGE.from, RANGE.to), 0);
  assert.equal(xOf(RANGE.to, RANGE.from, RANGE.to), BOX.w);
  assert.equal(xOf(at(12), RANGE.from, RANGE.to), BOX.w / 2);
});

test('a zero-length or backwards range yields 0, not NaN', () => {
  assert.equal(xOf(at(12), RANGE.to, RANGE.from), 0);
  assert.equal(xOf(at(12), RANGE.from, RANGE.from), 0);
  assert.equal(xOf('not a date', RANGE.from, RANGE.to), 0);
});

test('100 % is the TOP of the plot and 0 % the bottom', () => {
  assert.equal(yOf(100), BOX.top);
  assert.equal(yOf(0), BOX.bottom);
  assert.equal(yOf(50), (BOX.top + BOX.bottom) / 2);
});

test('percent is clamped, so a forecast over 100 cannot escape the box', () => {
  assert.equal(yOf(140), BOX.top);
  assert.equal(yOf(-5), BOX.bottom);
});

console.log('\nthe line');

test('samples become one run of moves and lines', () => {
  const pts = [{ at: at(0), percent: 0 }, { at: at(12), percent: 50 }, { at: '2026-09-08T00:00:00Z', percent: 100 }];
  const d = linePath(pts, RANGE);
  assert.equal(d.split('M').length - 1, 1, 'one M: the run is unbroken');
  assert.match(d, /^M0 66 L140 34\.5 L280 3$/);
});

test('a gap BREAKS the line instead of drawing across it', () => {
  const pts = [{ at: at(0), percent: 10 }, { at: at(6), percent: 20 }, { at: at(18), percent: 30 }];
  const gaps = [{ from: at(7), to: at(17), cause: 'http_429' }];
  const d = linePath(pts, RANGE, gaps);
  assert.equal(d.split('M').length - 1, 2, 'two runs: before the gap and after it');
  assert.ok(d.includes('M210'), 'the second run starts at the sample after the gap');
});

test('a gap that touches no pair of samples changes nothing', () => {
  const pts = [{ at: at(0), percent: 10 }, { at: at(6), percent: 20 }];
  const away = [{ from: at(20), to: at(22), cause: 'network' }];
  assert.equal(linePath(pts, RANGE, away), linePath(pts, RANGE));
});

test('no samples is an empty path, not a line at zero', () => {
  assert.equal(linePath([], RANGE), '');
  assert.equal(linePath(null, RANGE), '');
  assert.equal(areaPath([], RANGE), '');
});

test('the area closes each run separately, so no fill crosses a gap', () => {
  const pts = [
    { at: at(0), percent: 10 }, { at: at(6), percent: 20 },
    { at: at(18), percent: 30 }, { at: at(22), percent: 35 },
  ];
  const gaps = [{ from: at(7), to: at(17), cause: 'http_429' }];
  const a = areaPath(pts, RANGE, gaps);
  assert.equal(a.split('Z').length - 1, 2, 'two closed shapes');
  assert.equal(a.split(`L0 ${BOX.bottom}`).length - 1, 1, 'each returns to its own left edge');
});

test('a single sample fills nothing but still draws its point', () => {
  const one = [{ at: at(6), percent: 40 }];
  assert.equal(linePath(one, RANGE), 'M70 40.8');
  assert.equal(areaPath(one, RANGE), '', 'a one-sample area would be a spike out of nowhere');
});

console.log('\nbands and verticals');

test('a lock inside the range becomes its rectangle', () => {
  const r = bandRect({ from: at(6), to: at(12) }, RANGE);
  assert.deepEqual({ x: r.x, width: r.width }, { x: 70, width: 70 });
  assert.equal(r.y, BOX.top);
  assert.equal(r.height, BOX.bottom - BOX.top);
});

test('a lock STILL RUNNING reaches the right edge', () => {
  const r = bandRect({ from: at(18), to: null }, RANGE);
  assert.deepEqual({ x: r.x, width: r.width }, { x: 210, width: 70 },
    'an open lock is the case a person most needs to see');
});

test('a lock is clipped to the range, not drawn outside it', () => {
  const r = bandRect({ from: '2026-09-06T12:00:00Z', to: at(6) }, RANGE);
  assert.deepEqual({ x: r.x, width: r.width }, { x: 0, width: 70 });
});

test('a lock wholly outside the range is null, not a sliver', () => {
  assert.equal(bandRect({ from: '2026-09-01T00:00:00Z', to: '2026-09-02T00:00:00Z' }, RANGE), null);
  assert.equal(bandRect({ from: at(6), to: at(6) }, RANGE), null, 'zero length draws nothing');
});

test('resets outside the range are dropped, inside ones become x positions', () => {
  const xs = resetLines([at(6), at(18), '2026-09-09T00:00:00Z', 'nonsense'], RANGE);
  assert.deepEqual(xs, [70, 210]);
});

test('a drop of more than 30 points is read as a reset', () => {
  const pts = [
    { at: at(0), percent: 80 }, { at: at(1), percent: 82 },
    { at: at(2), percent: 4 },                                  // reset
    { at: at(3), percent: 6 }, { at: at(4), percent: 1 },       // -5: not a reset
  ];
  assert.deepEqual(inferredResets(pts), [at(2)]);
  assert.deepEqual(inferredResets(pts, 90), [], 'the threshold is the rule, not the shape');
});

console.log('\nticks and hover');

test('five ticks, the last one always now', () => {
  const t = xTicks(RANGE, '24h', () => 'x');
  assert.equal(t.length, 5);
  assert.deepEqual(t.map((k) => k.x), [0, 70, 140, 210, 280]);
  assert.equal(t[4].label, 'now');
});

test('the hover snaps to the nearest SAMPLE, never between two', () => {
  const pts = [{ at: at(0), percent: 1 }, { at: at(6), percent: 2 }, { at: at(18), percent: 3 }];
  assert.equal(nearestPoint(pts, 66, RANGE).index, 1, 'closest to the 06:00 sample');
  assert.equal(nearestPoint(pts, 200, RANGE).index, 2);
  assert.equal(nearestPoint(pts, 0, RANGE).index, 0);
  assert.equal(nearestPoint([], 10, RANGE), null);
});

console.log('\ngrouping');

test('flat series group by account_id', () => {
  const s = [
    { account_id: 'a', kind: 'session' }, { account_id: 'b', kind: 'session' },
    { account_id: 'a', kind: 'weekly_all' },
  ];
  const by = seriesByAccount(s);
  assert.equal(by.get('a').length, 2);
  assert.equal(by.get('b').length, 1);
});

test('a card always has three columns, models alphabetical', () => {
  const cols = columnsOf([
    { kind: 'weekly_scoped', model: 'Opus' },
    { kind: 'session' },
    { kind: 'weekly_scoped', model: 'Fable' },
  ]);
  assert.deepEqual(cols.map((c) => c.key), ['session', 'weekly_all', 'per_model']);
  assert.deepEqual(cols[2].series.map((s) => s.model), ['Fable', 'Opus']);
  assert.deepEqual(cols[1].series, [], 'an absent window is an empty column, not a missing one');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
