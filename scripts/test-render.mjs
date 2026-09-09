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
const { renderList, renderCards, renderAccount, renderRow } = await import('../src/web/render.js');
const { setViewOptions } = await import('../src/web/format.js');

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

console.log('\naccessibility of a row (§10, acceptance §11 item 11)');

test('every bar is a meter and carries its value', () => {
  for (const bar of draw().all((n) => n.className === 'bar')) {
    assert.equal(bar.attrs.role, 'meter');
    assert.equal(bar.attrs['aria-valuemin'], '0');
    assert.equal(bar.attrs['aria-valuemax'], '100');
    assert.match(bar.attrs['aria-valuenow'], /^\d+$/);
  }
});

test('the strip and the ghost are hidden, so they are not read as bars of their own', () => {
  const v = draw();
  for (const n of [...v.all((x) => x.className === 'timebar'), ...v.all((x) => x.className === 'bar-ghost')]) {
    assert.equal(n.attrs['aria-hidden'], 'true');
  }
});

test('aria-valuetext carries what the hidden parts would have said', () => {
  const bar = draw().children[0].all((n) => n.className === 'bar')[0];
  const said = bar.attrs['aria-valuetext'];
  assert.match(said, /^9%; session 5h;/, 'percent and window first');
  assert.match(said, /resets /);
  assert.match(said, /% of the window elapsed/, 'the strip is aria-hidden: this is its only voice');
  assert.match(said, /forecast \d+% at reset/, 'and the ghost has no other voice either');
});

test('a locked window says it is locked, not only in red', () => {
  const bar = draw().children[1].all((n) => n.className === 'bar')[0];
  assert.match(bar.attrs['aria-valuetext'], /locked: /,
    'colour is never the only carrier of meaning (§10)');
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

test('a hundred percent WITHOUT a reason colours the block, and locked still wins', () => {
  // 01.3 section 3.3 keeps these apart: `locked` means a window carries a
  // `locked_reason` -- the endpoint is refusing -- while `at_100` means a window
  // sits at 100% with none, i.e. the allowance is simply spent. Both colour the
  // block, and only `locked` did until 2026-09-08, so the block stayed plain for
  // exactly the case a person most needs to notice.
  const spent = renderAccount({ email: 'a@x', state: 'ok', at_100: true }, []);
  assert.equal(spent.dataset.state, 'at-100');

  // "Refused" is the more specific statement; someone seeing it does not also need
  // to be told the number reached 100.
  const refused = renderAccount({ email: 'a@x', state: 'ok', at_100: true, locked: true }, []);
  assert.equal(refused.dataset.state, 'locked');

  const ordinary = renderAccount({ email: 'a@x', state: 'ok' }, []);
  assert.equal(ordinary.dataset.state, 'ok');
});

console.log('\nthe three not-ok states are not one state (01.1 sec.3.2)');

const limitsOf = (id) => snap.limits.filter((l) => l.account_id === id);

test('`unknown` KEEPS the last good rows instead of blanking them', () => {
  // A 429 or a network blip wiped the numbers off the block until 2026-09-08 --
  // the numbers a person most wants at exactly that moment, and the ones the
  // artboard shows for this very account.
  const qa = snap.accounts.find((a) => a.state === 'unknown');
  assert.ok(qa, 'the fixture needs an unknown account for this to mean anything');
  const block = renderAccount(qa, limitsOf(qa.id));
  const rows = block.all((n) => n.className === 'row');
  assert.ok(rows.length > 0, 'the last good snapshot stays on screen');
  assert.equal(rows.length, limitsOf(qa.id).length);
});

test('and marks them as a dimmed group, with the reason in the header', () => {
  const qa = snap.accounts.find((a) => a.state === 'unknown');
  const block = renderAccount(qa, limitsOf(qa.id));

  const group = block.find((n) => n.className === 'rows-dimmed');
  assert.ok(group, 'the whole group is dimmed, not each row separately');
  assert.equal(group.dataset.dimmed, 'true');

  const badge = block.find((n) => n.className === 'account-badge');
  assert.ok(badge, 'the badge says why and until when');
  assert.equal(badge.dataset.tone, 'warning');
  assert.match(badge.textContent, /429/);
  // The text comes ready from the backend; the page decides WHERE it goes.
  assert.equal(badge.textContent, qa.message);
});

test('the time strip obeys its setting, which nothing on the page used to read', () => {
  // 01.1 par.2.2 makes the strip conditional on the toggle in par.5.2. The toggle
  // existed in the settings panel and was written to the config, and no code on the
  // page ever read it back -- a control that changed nothing at all. Measured
  // 2026-09-09: a grep for `time_bar` outside settings.js found zero hits.
  const withReset = snap.limits.find((l) => l.resets_at);
  assert.ok(withReset, 'the fixture needs a limit with resets_at');

  setViewOptions({ time_bar: true });
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 1);

  setViewOptions({ time_bar: false });
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 0,
    'the toggle is off and the strip is still drawn -- the setting is being ignored');

  // Absent config must not turn the strip off: a page that has not loaded settings
  // yet should look like the default, not like someone chose to hide it.
  setViewOptions(undefined);
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 1,
    'with no config the default is ON, per the settings panel default');
});

test('a dimmed row draws no strip and no ghost: both are claims about NOW', () => {
  const withForecast = snap.limits.find((l) => l.forecast && l.resets_at);
  assert.ok(withForecast, 'the fixture needs a limit with both');

  const live = renderRow(withForecast);
  assert.equal(live.all((n) => n.className === 'timebar').length, 1);
  assert.equal(live.all((n) => n.className === 'bar-ghost').length, 1);

  const dim = renderRow(withForecast, { dimmed: true });
  assert.equal(dim.dataset.dimmed, 'true');
  assert.equal(dim.all((n) => n.className === 'timebar').length, 0,
    'elapsed share against a live clock would date a stale reading');
  assert.equal(dim.all((n) => n.className === 'bar-ghost').length, 0,
    'a forecast needs a pace, and the pace of an unreachable account is unknown');
});

test('a dimmed row SAYS it is last-known, so dimming is not colour-only meaning', () => {
  const l = snap.limits[0];
  const dim = renderRow(l, { dimmed: true });
  const bar = dim.find((n) => n.className === 'bar');
  assert.match(bar.attrs['aria-valuetext'], /^last known: /, '01.1 sec.10');
});

test('`stale` and `error` still replace the rows, because there is nothing to show', () => {
  const stale = snap.accounts.find((a) => a.state === 'stale');
  const block = renderAccount(stale, limitsOf(stale.id));
  assert.equal(block.all((n) => n.className === 'row').length, 0);
  assert.ok(block.find((n) => n.className === 'account-note'));
  assert.equal(block.all((n) => n.className === 'account-badge').length, 0,
    'a dead token is not a transient failure and gets no retry badge');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
