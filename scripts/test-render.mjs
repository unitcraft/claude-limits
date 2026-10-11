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
const { renderList, renderCards, renderAccount, renderRow, layoutCells, extraUsageLine } = await import('../src/web/render.js');
const { setViewOptions, configUiOptions } = await import('../src/web/format.js');

// -------------------------------------------------------------------- tests --

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const snap = JSON.parse(readFileSync(new URL('../fixtures/api/snapshot-mixed.json', import.meta.url)));
const configReply = JSON.parse(readFileSync(new URL('../fixtures/api/config.json', import.meta.url)));
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

test('weekly 1% with null forecast preserves facts without a ghost hatch or forecast date', () => {
  setViewOptions({ time_bar: true });
  const limit = { ...snap.limits[1], kind: 'weekly_all', percent: 1, severity: 'normal', forecast: null };
  const row = renderRow(limit);
  assert.equal(row.dataset.severity, 'normal');
  assert.equal(row.find(n => n.className === 'row-pct').textContent, '1%');
  assert.equal(row.find(n => n.className === 'row-pct').title, 'forecast later');
  assert.equal(row.dataset.resetsAt, limit.resets_at);
  assert.equal(row.all(n => n.className === 'bar-ghost').length, 0);
  assert.equal(row.all(n => n.className === 'timebar-hatch').length, 0);
  assert.equal(row.all(n => n.className.includes('reset-forecast')).length, 0);
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

test('a shared pool shows a footnote naming the first account, not the same bars again', () => {
  // 01.3 sec.3.3 (amendment 2026-09-21): the later of two logins reporting the
  // identical quota gets `same_quota_as`; its bars would repeat the first block's.
  const rows = [{ account_id: 'b', kind: 'session', label: 'session', percent: 9, severity: 'normal' }];
  const owner = { id: 'a', email: 'first@x', state: 'ok' };
  const pooled = renderAccount({ id: 'b', email: 'second@x', state: 'ok', same_quota_as: 'a' }, rows, owner);
  const notes = pooled.all((n) => n.className === 'account-note').map((n) => n.textContent);
  assert.deepEqual(notes, ['same quota reported for first@x -- shared pool suspected']);
  assert.equal(pooled.all((n) => n.className === 'row').length, 0);
  // The control: without `same_quota_as` the same rows are drawn.
  const own = renderAccount({ id: 'b', email: 'second@x', state: 'ok' }, rows);
  assert.equal(own.all((n) => n.className === 'account-note').length, 0);
  assert.ok(own.all((n) => n.className === 'row').length > 0);
});

test('Kimi Extra Usage is the reference line under the rows, and no line when the wallet is off', () => {
  // The reference's own lines for the same wallets (kimi_extra_usage_line, 2026-10-02).
  assert.equal(extraUsageLine({ balance: '1.23', currency: 'USD', monthly_cap: '5.00' }),
    'extra usage balance: 1.23 USD (monthly cap 5.00 USD)');
  assert.equal(extraUsageLine({ balance: '0.01', currency: 'CNY', monthly_cap: null }),
    'extra usage balance: 0.01 CNY');
  const rows = [{ account_id: 'k', kind: 'monthly', label: 'month', percent: 67, severity: 'normal' }];
  const on = renderAccount({ id: 'k', provider: 'kimi', display_name: 'kimi-env', state: 'ok',
    extra_usage: { balance: '1.23', currency: 'USD', monthly_cap: null } }, rows);
  assert.deepEqual(on.all((n) => n.className === 'account-extra').map((n) => n.textContent),
    ['extra usage balance: 1.23 USD']);
  // The control: the field absent, no line.
  const off = renderAccount({ id: 'k', provider: 'kimi', display_name: 'kimi-env', state: 'ok' }, rows);
  assert.equal(off.all((n) => n.className === 'account-extra').length, 0);
});

test('a new order moves the blocks that are already drawn', () => {
  // The owner's stand: a card dragged from third to second was saved, the snapshot came
  // back in the new order, and the list still showed the old one -- a block replaced in
  // place kept its old position.
  const accs = [{ id: 'a', email: 'a@x', state: 'ok' }, { id: 'k', provider: 'kimi', display_name: 'K', state: 'ok' },
    { id: 'm', email: 'm@x', state: 'ok' }];
  list.replaceChildren();
  renderList(accs, [], null);
  assert.deepEqual(list.children.map((n) => n.dataset.email), ['a@x', 'kimi:k', 'm@x']);
  renderList([accs[0], accs[2], accs[1]], [], null);
  assert.deepEqual(list.children.map((n) => n.dataset.email), ['a@x', 'm@x', 'kimi:k']);
});

test('the person name stands before the organisation, and either may be missing', () => {
  const org = (acc) => renderAccount(acc, []).all((n) => n.className === 'account-org').map((n) => n.textContent);
  assert.deepEqual(org({ email: 'a@x', state: 'ok', display_name: 'Nova', org: 'Org' }), ['Nova, Org']);
  assert.deepEqual(org({ email: 'a@x', state: 'ok', display_name: null, org: 'Org' }), ['Org']);
  assert.deepEqual(org({ email: 'a@x', state: 'ok', display_name: 'Nova' }), ['Nova']);
  assert.deepEqual(org({ email: 'a@x', state: 'ok' }), []);
});

test('a Kimi Code account is headed by its name and says which service it is', () => {
  const block = renderAccount({ provider: 'kimi', email: null, display_name: 'kimi-code-env-0e4f', state: 'ok' }, []);
  assert.equal(block.all((n) => n.className === 'account-email')[0].textContent, 'kimi-code-env-0e4f');
  assert.equal(block.all((n) => n.className === 'account-org')[0].textContent, 'Kimi Code');
});

test('a Codex account is headed by its address and says which service it is', () => {
  const block = renderAccount({ provider: 'codex', email: null, display_name: 'me@example.com', state: 'ok' }, []);
  assert.equal(block.all((n) => n.className === 'account-email')[0].textContent, 'me@example.com');
  assert.equal(block.all((n) => n.className === 'account-org')[0].textContent, 'Codex');
});

test('a live account shows its note, and one without a note shows none', () => {
  const noted = renderAccount({ email: 'a@x', state: 'ok', message: 'MGTS: token expired on disk' }, []);
  const notes = noted.all((n) => n.className === 'account-note');
  assert.equal(notes.length, 1);
  assert.equal(notes[0].textContent, 'MGTS: token expired on disk');
  const plain = renderAccount({ email: 'a@x', state: 'ok', message: '' }, []);
  assert.equal(plain.all((n) => n.className === 'account-note').length, 0);
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

  setViewOptions(configUiOptions(configReply));
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 1);

  setViewOptions(configUiOptions({ ...configReply, config: { ...configReply.config,
    ui: { ...configReply.config.ui, time_bar: false } } }));
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 0,
    'the toggle is off and the strip is still drawn -- the setting is being ignored');

  // Absent config must not turn the strip off: a page that has not loaded settings
  // yet should look like the default, not like someone chose to hide it.
  setViewOptions(undefined);
  assert.equal(renderRow(withReset).all((n) => n.className === 'timebar').length, 1,
    'with no config the default is ON, per the settings panel default');
});

test('a row and an account name both say which account they are (01.1 par.2.5)', () => {
  // "A click on a row in the list or the cards opens the statistics with that account
  // scrolled to the top." There was no click handler on a row or on an account name
  // at all -- all six listeners were the view switcher, the brand, the panel and the
  // refresh button. The row is the most obvious thing on the page to click and it did
  // nothing.
  //
  // The handler is delegated and finds the nearest [data-account], so what this test
  // pins is the structure the handler depends on. A row that stops carrying its id is
  // a click that silently does nothing again.
  const withAccount = snap.limits.find((l) => l.account_id);
  assert.ok(withAccount, 'the fixture needs a limit with an account_id');
  assert.equal(renderRow(withAccount).dataset.account, withAccount.account_id);

  const acc = snap.accounts[0];
  const block = renderAccount(acc, snap.limits.filter((l) => l.account_id === acc.id));
  const name = block.all((n) => n.className === 'account-email')[0];
  assert.ok(name, 'the account block must show a name');
  assert.equal(name.dataset.account, acc.id,
    'the name is the second place 01.1 par.2.5 names, and the handler needs its id');
});

test('the strip hatches to where the forecast runs out (01.1 par.2.2)', () => {
  // `runs_out_at` was in every snapshot and read by NOTHING -- a grep across the page
  // found zero uses. So the strip showed how much of the window had gone and never
  // that it was going to end early, which is the one thing the hatching is for.
  //
  // A window that resets in an hour, of which 90% has gone, and a forecast that runs
  // out ten minutes from now: the hatch must start at the elapsed point and stop
  // before the end.
  const now = Date.now();
  const win = 5 * 3600;                                // a session window, 01.1 2.6
  const lim = {
    kind: 'session', account_id: 'a-1', percent: 80, window_sec: win,
    resets_at: new Date(now + 360_000).toISOString(),   // 6 minutes left
    seconds_left: 360,
    forecast: { runs_out_at: new Date(now + 120_000).toISOString(),
                percent_at_reset: 103, label: 'ends soon', warning: true },
  };
  setViewOptions({ time_bar: true });
  const hatch = renderRow(lim).all((n) => n.className === 'timebar-hatch');
  assert.equal(hatch.length, 1, 'the forecast says it runs out inside the window');
  assert.ok(parseFloat(hatch[0].style.width) > 0, 'a hatch of zero width shows nothing');

  // No forecast: no hatching. Without this the test would pass for a strip that always
  // hatches. (One that does not run out IS hatched since 2026-10-06 -- to the end of
  // the window; the colour test below holds that.)
  const none = { ...lim, forecast: undefined };
  assert.equal(renderRow(none).all((n) => n.className === 'timebar-hatch').length, 0);

  // A run-out already BEHIND the elapsed point is a stale reading, not a warning:
  // hatching backwards would read as the opposite of what it means.
  const past = { ...lim, forecast: { ...lim.forecast,
                 runs_out_at: new Date(now - 600_000).toISOString() } };
  assert.equal(renderRow(past).all((n) => n.className === 'timebar-hatch').length, 0);
});

test('layoutCells re-lays the GHOST too, not only the fill (01.1 par.2.2)', () => {
  // THE CALL SITE, not the function. cellGeometry's own tests pass whether or not
  // layoutCells hands it a forecast -- I removed the argument and every one of them
  // stayed green, which is how the defect survived in the first place. This test
  // drives layoutCells and looks at what happened to the ghost element.
  const withForecast = snap.limits.find((l) => l.forecast && l.forecast.percent_at_reset);
  assert.ok(withForecast, 'the fixture needs a limit with a forecast');

  const row = renderRow(withForecast);
  const before = row.all((n) => n.className === 'bar-ghost')[0];
  assert.ok(before, 'the row must draw a ghost before we relayout it');
  const smooth = before.style.width;
  assert.match(smooth, /%$/, 'the smooth style sizes the ghost in per cent');

  // Mount it where layoutCells will find it, and switch to the cells style.
  document.body.append(row);
  document.body.dataset.barStyle = 'cells';
  try {
    layoutCells();
    const after = row.all((n) => n.className === 'bar-ghost')[0];
    assert.match(after.style.width, /px$/,
      'in the cells style the ghost must be sized in pixels, snapped to the grid');
    assert.notEqual(after.style.width, smooth,
      'the ghost kept its smooth-bar geometry and would run across the cell gaps');
  } finally {
    document.body.dataset.barStyle = '';
  }
});

test('the ghost is coloured by the PROJECTION, not by the row (01.1 sec.2.2, 2026-09-22)', () => {
  // 40 % now is a calm row; heading for 120 % it is a red ghost. The owner saw no
  // forecast colours at all on the first stand: the ghost took the row's colour.
  const base = snap.limits.find((l) => l.forecast && l.resets_at);
  const row = renderRow({ ...base, percent: 40, severity: 'normal',
    forecast: { ...base.forecast, percent_at_reset: 120, severity: 'critical' } });
  const ghost = row.all((n) => n.className === 'bar-ghost')[0];
  assert.equal(ghost.dataset.severity, 'critical');
  const calm = renderRow({ ...base, percent: 40, severity: 'normal',
    forecast: { ...base.forecast, percent_at_reset: 60, severity: 'normal' } });
  assert.equal(calm.all((n) => n.className === 'bar-ghost')[0].dataset.severity, 'normal');
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

test('the forecast time is green from 95% of the window, yellow from 80%, red earlier', () => {
  // Owner, 2026-10-06: the line that says WHEN the limit ends is coloured by that
  // moment's place in the window, not by the percent at reset. Edges included: 95
  // is still green, 80 still yellow.
  const now = Date.now();
  const win = 5 * 3600 * 1000;                         // session window, 01.1 2.6
  const reset = now + 3600_000;
  const start = reset - win;
  const at = (share) => new Date(start + win * share / 100).toISOString();
  const row = (share, label = '→ 120% at reset, ends ~01:08 (3h 15min)') => renderRow({
    kind: 'session', account_id: 'a-1', percent: 70, window_sec: 5 * 3600,
    resets_at: new Date(reset).toISOString(), seconds_left: 3600,
    forecast: { runs_out_at: share == null ? null : at(share), percent_at_reset: 120,
                label, severity: 'critical' },
  });
  const tone = (r) => r.find((n) => String(n.className).startsWith('reset-forecast')).dataset.timeTone;
  assert.equal(tone(row(99)), 'ok');
  assert.equal(tone(row(95)), 'ok', '95% is the green edge');
  assert.equal(tone(row(94.9)), 'warning');
  assert.equal(tone(row(80)), 'warning', '80% is the yellow edge');
  assert.equal(tone(row(79.9)), 'critical');
  assert.equal(tone(row(30)), 'critical');
  // No moment to colour: no run-out, or a line without "ends" -- severity alone.
  assert.equal(tone(row(null)), undefined);
  assert.equal(tone(row(99, '→ 52% at reset')), undefined);
});

test('the strip hatches to where the limit lasts, coloured green from 95%, yellow from 80%', () => {
  // Owner, 2026-10-06: the forecast is the strip's OWN hatching, not a bar of its own;
  // it ends where the pace lasts to and wears that point's colour -- and a forecast
  // that does not run out is hatched too, to the end of the window, green.
  const now = Date.now();
  const win = 5 * 3600 * 1000;
  const reset = now + 4.5 * 3600_000;                  // 10% of the window has gone
  const start = reset - win;
  const lim = (forecast) => ({
    kind: 'session', account_id: 'a-1', percent: 70, window_sec: 5 * 3600,
    resets_at: new Date(reset).toISOString(), seconds_left: 4.5 * 3600, forecast });
  const runsOut = (share) => lim({ runs_out_at: new Date(start + win * share / 100).toISOString(),
                                   percent_at_reset: 120, label: '→ 120% at reset' });
  const hatches = (r) => r.all((n) => n.className === 'timebar-hatch');
  const hatch = (l, opts) => hatches(renderRow(l, opts))[0];
  const end = (h) => parseFloat(h.style.left) + parseFloat(h.style.width);
  setViewOptions({ time_bar: true });

  for (const [share, tone] of [[99, 'ok'], [95, 'ok'], [94.9, 'warning'], [80, 'warning'],
                               [79.9, 'critical'], [30, 'critical']]) {
    const h = hatch(runsOut(share));
    assert.ok(h, `a hatch to ${share}%`);
    assert.equal(h.dataset.tone, tone, `${share}% of the window`);
    assert.ok(Math.abs(end(h) - share) < 0.2, `the hatch ends at ${share}%, not ${end(h)}`);
  }
  // A forecast that does not run out: hatched to the end of the window, green.
  const whole = hatch(lim({ runs_out_at: null, percent_at_reset: 40, label: '→ 40% at reset' }));
  assert.ok(whole, 'a forecast that lasts is shown too');
  assert.equal(whole.dataset.tone, 'ok');
  assert.ok(Math.abs(end(whole) - 100) < 0.2);
  // No separate forecast bar: the strip is the one place for it.
  assert.equal(renderRow(runsOut(50)).all((n) => n.className === 'fcbar').length, 0);
  // A dimmed row (no pace known) draws no strip, so no hatch.
  assert.equal(hatches(renderRow(runsOut(50), { dimmed: true })).length, 0);
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
