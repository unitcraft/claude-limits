// Tests for the threshold notifications (task #9), under node.
//
//   node scripts/test-notify.mjs
import assert from 'node:assert/strict';
import { planNotifications, THRESHOLDS } from '../src/web/notify.js';

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const NOW = Date.parse('2026-10-08T12:00:00Z');
const R1 = '2026-10-08T17:00:00Z';
const R2 = '2026-10-08T22:00:00Z';
const lim = (percent, extra = {}) => ({
  account_id: 'a1', kind: 'session', model: null, label: 'Session 5h', percent,
  resets_at: R1, reset_label: 'in 5h', locked: false, ...extra,
});
const run = (limits, told = {}, o = {}) =>
  planNotifications(limits, told, { enabled: true, now: NOW, names: { a1: 'main@example.com' }, ...o });

test('the thresholds are 70 and 90', () => assert.deepEqual(THRESHOLDS, [70, 90]));

test('below 70 says nothing', () => assert.equal(run([lim(69)]).fire.length, 0));

test('crossing 70 fires once, naming the account', () => {
  const r = run([lim(70)]);
  assert.equal(r.fire.length, 1);
  assert.equal(r.fire[0].threshold, 70);
  assert.match(r.fire[0].title, /main@example\.com/);
});

test('then crossing 90 fires again', () => {
  const a = run([lim(75)]);
  const b = run([lim(91)], a.told);
  assert.equal(b.fire.length, 1);
  assert.equal(b.fire[0].threshold, 90);
});

test('one jump over both thresholds gives ONE notification, the higher', () => {
  const r = run([lim(95)]);
  assert.equal(r.fire.length, 1);
  assert.equal(r.fire[0].threshold, 90);
});

test('...and the skipped 70 does not fire on the next snapshot', () => {
  const a = run([lim(95)]);
  assert.equal(run([lim(96)], a.told).fire.length, 0);
});

test('a repeat of the same snapshot (page reload) does not duplicate', () => {
  const a = run([lim(80)]);
  const reloaded = JSON.parse(JSON.stringify(a.told));
  assert.equal(run([lim(80)], reloaded).fire.length, 0);
});

test('after the window resets, the thresholds arm again', () => {
  const a = run([lim(92)]);
  const later = run([lim(10, { resets_at: R2 })], a.told);
  assert.equal(later.fire.length, 0);
  const again = run([lim(75, { resets_at: R2 })], later.told);
  assert.equal(again.fire.length, 1);
});

test('two windows and two accounts are told separately', () => {
  const r = run([lim(80), lim(80, { kind: 'weekly_all' }), lim(80, { account_id: 'a2' })]);
  assert.equal(r.fire.length, 3);
});

test('switched off: silent, and nothing recorded', () => {
  const r = run([lim(95)], {}, { enabled: false });
  assert.equal(r.fire.length, 0);
  assert.deepEqual(r.told, {});
  assert.equal(run([lim(95)], r.told).fire.length, 1, 'switching on later reports what is still true');
});

test('a locked window is not announced', () => {
  assert.equal(run([lim(100, { locked: true })]).fire.length, 0);
});

test('a window without resets_at or with a junk percent is skipped', () => {
  assert.equal(run([lim(90, { resets_at: null }), lim('x')]).fire.length, 0);
});

test('a fractional percent arriving as a string still counts', () => {
  assert.equal(run([lim('90.5')]).fire.length, 1);
});

test('windows reset more than a day ago are forgotten', () => {
  const old = { 'a1|session||2026-10-01T00:00:00Z|70': Date.parse('2026-10-01T00:00:00Z') };
  assert.deepEqual(run([], old).told, {});
});

console.log(`\n${passed} passed`);
