// Structure test for the list renderer, run under node with a hand-rolled DOM stub.
//
//   node scripts/test-render.mjs
//
// Why a stub rather than a browser: the acceptance of T2.20 is "the fixture renders
// like the artboard", judged by eye — but the things that break a renderer are not
// aesthetic. Rows joined to the wrong account, an account drawn empty, a state that
// silently loses its message: all of those look like a layout problem and are none.
// This checks the STRUCTURE by machine and leaves the looks to the eye.
//
// The stub implements only what app.js touches. It is not a DOM and does not pretend
// to be one; if the renderer starts using something else, this fails loudly rather
// than passing on a shim that quietly does nothing.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';


// ----------------------------------------------------------------- DOM stub --

class Node {
  constructor(tag) {
    this.tag = tag; this.className = ''; this._text = '';
    this.children = []; this.dataset = {}; this.style = {}; this.attrs = {};
    this.title = '';
  }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text || this.children.map((c) => c.textContent).join(' '); }
  append(...kids) { this.children.push(...kids); }
  prepend(...kids) { this.children.unshift(...kids); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  replaceWith(n) { const p = this.parent; if (p) p.children[p.children.indexOf(this)] = n; }
  remove() { const p = this.parent; if (p) p.children.splice(p.children.indexOf(this), 1); }
  insertBefore(n, ref) { const i = ref ? this.children.indexOf(ref) : this.children.length; this.children.splice(i, 0, n); n.parent = this; }
  replaceChildren(...kids) { this.children = kids; }
  querySelector(sel) { return this.find((n) => matches(n, sel)); }
  find(pred) {
    for (const c of this.children) { if (pred(c)) return c; const d = c.find(pred); if (d) return d; }
    return null;
  }
  all(pred, out = []) {
    for (const c of this.children) { if (pred(c)) out.push(c); c.all(pred, out); }
    return out;
  }
  get clientWidth() { return 342; }
}
const matches = (n, sel) => sel.startsWith('.') ? n.className.split(' ').includes(sel.slice(1)) : n.tag === sel;

const view = new Node('section');
globalThis.document = {
  createElement: (t) => new Node(t),
  getElementById: () => view,
  body: { dataset: {} },
};

// The REAL renderer, imported — not a copy. The first version of this file
// transcribed the three functions, which would have let the test pass while the
// shipped code drifted away from it. render.js exists precisely so this import is
// possible: it takes a document and returns nodes, with no fetch, timers or
// EventSource to drag in.
const { renderList } = await import('../src/web/render.js');

// -------------------------------------------------------------------- tests --

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const snap = JSON.parse(readFileSync(new URL('../fixtures/api/snapshot-mixed.json', import.meta.url)));
console.log('list renderer against fixtures/api/snapshot-mixed.json');

test('every account in the snapshot becomes a block, in order', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  assert.equal(v.children.length, 4);
  assert.deepEqual(v.children.map((b) => b.find((n) => n.className === 'account-email').textContent),
    ['main@example.com', 'heavy@example.com', 'ops@example.org', 'qa@example.org']);
});

test('rows are joined by account_id, not by position', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const rows = (i) => v.children[i].all((n) => n.className === 'row');
  assert.equal(rows(0).length, 3, 'main has three windows in the fixture');
  assert.equal(rows(1).length, 2, 'heavy has two');
  assert.equal(rows(2).length, 0, 'a stale account shows its reason, not rows');
});

test('row order is session, all, then models alphabetically', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const names = v.children[0].all((n) => n.className === 'row-name').map((n) => n.textContent);
  assert.deepEqual(names, ['session 5h', 'all 7d', 'Opus 7d']);
});

test('a non-ok account shows its message and NO rows', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const stale = v.children[2];
  assert.equal(stale.dataset.state, 'stale');
  assert.match(stale.find((n) => n.className === 'account-note').textContent, /token expired/);
  assert.equal(stale.all((n) => n.className === 'row').length, 0);
});

test('a locked account is marked locked even though its state is ok', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  assert.equal(v.children[1].dataset.state, 'locked');
});

test('a locked window is critical at any percent, and severity drives the row', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const first = v.children[1].all((n) => n.className === 'row')[0];
  assert.equal(first.dataset.severity, 'critical');
  assert.equal(first.find((n) => n.className === 'row-pct').textContent, '100%');
});

test('the forecast ghost appears only where the forecast is ahead', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const rows = v.children[0].all((n) => n.className === 'row');
  const ghosts = rows.map((r) => r.all((n) => n.className === 'bar-ghost').length);
  assert.deepEqual(ghosts, [1, 1, 0], 'session 9→11 and all 74→103 have one; Opus has no forecast');
});

test('bar width is the percent, clamped', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const fills = v.children[0].all((n) => n.className === 'bar-fill').map((n) => n.style.width);
  assert.deepEqual(fills, ['9%', '74%', '12%']);
});

test('directory NAMES are shown, not the full paths', () => {
  view.children = [];
  renderList(snap.accounts, snap.limits);
  const v = view;
  const dirs = v.children[0].find((n) => n.className === 'account-dirs').textContent;
  assert.equal(dirs, 'nv-lang, MGTS');
  assert.ok(!dirs.includes('D:/'), 'a path in the header would push the row off the line');
});

test('an account with no limits at all still renders its header', () => {
  view.children = [];
  renderList([{ id: 'x', email: 'empty@example.com', state: 'ok' }], []);
  const v = view;
  assert.equal(v.children.length, 1);
  assert.equal(v.children[0].find((n) => n.className === 'account-email').textContent, 'empty@example.com');
  assert.equal(v.children[0].all((n) => n.className === 'row').length, 0);
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
