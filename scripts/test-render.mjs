// Structure test for the renderers, run under node with a hand-rolled DOM stub.
//
//   node scripts/test-render.mjs
//
// Why a stub rather than a browser: the acceptance of T2.20 and T2.22 is "the fixture
// renders like the artboard", judged by eye — but the things that break a renderer are
// not aesthetic. Rows joined to the wrong account, an account drawn empty, a state
// that silently loses its message: all of those look like a layout problem and are
// none. This checks the STRUCTURE by machine and leaves the looks to the eye.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Node, installDocument } from './dom-stub.mjs';

const list = new Node('section');
const cards = new Node('section');
installDocument({ 'view-list': list, 'view-cards': cards });

// The REAL renderer, imported — not a copy. The first version of this file
// transcribed the three functions, which would have let the test pass while the
// shipped code drifted away from it. render.js exists precisely so this import is
// possible: it takes a document and returns nodes, with no fetch, timers or
// EventSource to drag in. Dynamic, because the stub must be installed first.
const { renderList, renderCards } = await import('../src/web/render.js');

// -------------------------------------------------------------------- tests --

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const snap = JSON.parse(readFileSync(new URL('../fixtures/api/snapshot-mixed.json', import.meta.url)));
const draw = (order = null) => {
  list.replaceChildren();
  renderList(snap.accounts, snap.limits, order);
  return list;
};
const drawCards = (order = null) => {
  cards.replaceChildren();
  renderCards(snap.accounts, snap.limits, order);
  return cards;
};

console.log('list renderer against fixtures/api/snapshot-mixed.json');

test('every account in the snapshot becomes a block, in order', () => {
  const v = draw();
  assert.equal(v.children.length, 4);
  assert.deepEqual(v.children.map((b) => b.find((n) => n.className === 'account-email').textContent),
    ['main@example.com', 'heavy@example.com', 'ops@example.org', 'qa@example.org']);
});

test('rows are joined by account_id, not by position', () => {
  const v = draw();
  const rows = (i) => v.children[i].all((n) => n.className === 'row');
  assert.equal(rows(0).length, 3, 'main has three windows in the fixture');
  assert.equal(rows(1).length, 2, 'heavy has two');
  assert.equal(rows(2).length, 0, 'a stale account shows its reason, not rows');
});

test('row order is session, all, then models alphabetically', () => {
  const v = draw();
  const names = v.children[0].all((n) => n.className === 'row-name').map((n) => n.textContent);
  assert.deepEqual(names, ['session 5h', 'all 7d', 'Opus 7d']);
});

test('a non-ok account shows its message and NO rows', () => {
  const v = draw();
  const stale = v.children[2];
  assert.equal(stale.dataset.state, 'stale');
  assert.match(stale.find((n) => n.className === 'account-note').textContent, /token expired/);
  assert.equal(stale.all((n) => n.className === 'row').length, 0);
});

test('a locked account is marked locked even though its state is ok', () => {
  assert.equal(draw().children[1].dataset.state, 'locked');
});

test('a locked window is critical at any percent, and severity drives the row', () => {
  const first = draw().children[1].all((n) => n.className === 'row')[0];
  assert.equal(first.dataset.severity, 'critical');
  assert.equal(first.find((n) => n.className === 'row-pct').textContent, '100%');
});

test('the forecast ghost appears only where the forecast is ahead', () => {
  const rows = draw().children[0].all((n) => n.className === 'row');
  const ghosts = rows.map((r) => r.all((n) => n.className === 'bar-ghost').length);
  assert.deepEqual(ghosts, [1, 1, 0], 'session 9->11 and all 74->103 have one; Opus has no forecast');
});

test('bar width is the percent, clamped', () => {
  const fills = draw().children[0].all((n) => n.className === 'bar-fill').map((n) => n.style.width);
  assert.deepEqual(fills, ['9%', '74%', '12%']);
});

test('directory NAMES are shown, not the full paths', () => {
  const dirs = draw().children[0].find((n) => n.className === 'account-dirs').textContent;
  assert.equal(dirs, 'nv-lang, MGTS');
  assert.ok(!dirs.includes('D:/'), 'a path in the header would push the row off the line');
});

test('an account with no limits at all still renders its header', () => {
  list.replaceChildren();
  renderList([{ id: 'x', email: 'empty@example.com', state: 'ok' }], []);
  assert.equal(list.children.length, 1);
  assert.equal(list.children[0].find((n) => n.className === 'account-email').textContent, 'empty@example.com');
  assert.equal(list.children[0].all((n) => n.className === 'row').length, 0);
});

console.log('\ncards renderer (T2.22)');

test('one card per account, each with a real button as its handle', () => {
  const v = drawCards();
  assert.equal(v.children.length, 4);
  for (const card of v.children) {
    const handle = card.children[0];
    assert.equal(handle.className, 'card-handle');
    assert.equal(handle.tag, 'button', 'a div cannot take Space, arrows or a focus ring (01.1 §10)');
    assert.equal(handle.attrs.type, 'button', 'without type= a button inside a form submits it');
    assert.match(handle.attrs['aria-label'], /reorder /);
  }
});

test('a card carries the same rows as the list block does', () => {
  const inCards = drawCards().children[0].all((n) => n.className === 'row').length;
  const inList = draw().children[0].all((n) => n.className === 'row').length;
  assert.equal(inCards, inList);
  assert.equal(inCards, 3);
});

test('the card mirrors the account state, so the panel can be tinted', () => {
  const v = drawCards();
  assert.deepEqual(v.children.map((c) => c.dataset.state), ['ok', 'locked', 'stale', 'unknown']);
});

test('accounts_order puts named accounts first, the rest in discovery order', () => {
  const v = drawCards(['qa@example.org', 'heavy@example.com']);
  assert.deepEqual(v.children.map((c) => c.dataset.email),
    ['qa@example.org', 'heavy@example.com', 'main@example.com', 'ops@example.org']);
});

test('the SAME order applies to the list view', () => {
  const v = draw(['qa@example.org', 'heavy@example.com']);
  assert.deepEqual(v.children.map((b) => b.dataset.email),
    ['qa@example.org', 'heavy@example.com', 'main@example.com', 'ops@example.org']);
});

test('an order naming an account that is gone does not lose the others', () => {
  const v = drawCards(['nobody@example.net', 'qa@example.org']);
  assert.deepEqual(v.children.map((c) => c.dataset.email),
    ['qa@example.org', 'main@example.com', 'heavy@example.com', 'ops@example.org']);
});

test('a second render updates in place: same nodes, no duplicates', () => {
  cards.replaceChildren();
  renderCards(snap.accounts, snap.limits, null);
  renderCards(snap.accounts, snap.limits, null);
  assert.equal(cards.children.length, 4, 'a redraw that appends would show eight');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
