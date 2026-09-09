// Structure test for the statistics view (task T2.23), under node.
//
//   node scripts/test-stats.mjs
//
// The acceptance in 01.5 is "the fixture history renders like the artboard", judged
// by eye. What an eye cannot judge on a 280x84 chart: whether the line broke at the
// right gap, whether the lock band covers the hours it claims, whether a card with no
// per-model limit says so or just shows an empty box. Those are asserted here against
// fixtures/api/history-7d.json, which the generator derives from a stated shape.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Node, installDocument } from './dom-stub.mjs';

const view = new Node('section');
installDocument({ 'view-stats': view });
const { renderStats, renderTiles, summaryLine, modelColors, valuesTable } =
  await import('../src/web/stats.js');

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const hist = JSON.parse(readFileSync(new URL('../fixtures/api/history-7d.json', import.meta.url)));
const draw = (kind = '7d') => { renderStats(hist, kind); return view; };
const first = (n, cls) => n.find((x) => x.className === cls);
const all = (n, cls) => n.all((x) => x.className === cls);

console.log('the frame');

test('filters, tiles and one card per account', () => {
  const v = draw();
  assert.ok(first(v, 'stats-filters'), 'the period row');
  assert.equal(all(v, 'tile').length, 4);
  assert.equal(all(v, 'stat-card').length, 3);
});

test('the selected period is the one marked selected', () => {
  const v = draw('24h');
  const chips = all(v, 'chip').filter((c) => c.dataset.range);
  assert.deepEqual(chips.map((c) => c.attrs['aria-selected']), ['true', 'false', 'false']);
});

test('the folders control is disabled, and its title names what it waits for', () => {
  // PINS A DIVERGENCE AND ITS REASON, and the reason is not the one the title used to
  // give.
  //
  // 01.1 par.6.1 says the Accounts/Folders control "switches par.6 and par.7". The
  // chip is disabled. The old title said "not built yet" -- and folders.js is 291
  // lines, app.js routes `group === 'folder'` to renderFolders, and test-folders.mjs
  // passes eighteen tests against it. The view is built.
  //
  // What is missing is the DATA: `GET /api/history?by=folder` is specified in 01.3
  // par.3.6 and no handler serves it. Enabling the chip would draw an empty frame.
  //
  // On 2026-09-09 the stale title nearly cost the reversal: I read "not built yet",
  // checked, found the view built, and enabled the chip -- then found the real
  // blocker and put it back. THIS test is what stopped it, so it now asserts the
  // reason rather than the wording, and a title that stops naming the endpoint fails
  // here rather than misleading the next reader.
  const folder = all(draw(), 'chip').find((c) => c.dataset.group === 'folder');
  assert.equal(folder.disabled, true);
  assert.match(folder.title, /by=folder/,
    'the title must name the endpoint it waits for, not just say "not built"');
  assert.doesNotMatch(folder.title, /not built/,
    'the view IS built; saying otherwise is what caused a near-miss');
});

test('an empty history says so instead of drawing an empty frame', () => {
  renderStats({ accounts: [], series: [], range: null });
  assert.equal(view.children.length, 1);
  assert.match(view.children[0].textContent, /no history yet/);
});

console.log('\ntiles (§6.2)');

test('a locked week is red and names who and when', () => {
  const t = renderTiles(hist.tiles);
  const tile = t.children[0];
  assert.equal(first(tile, 'tile-value').dataset.tone, 'critical');
  assert.equal(first(tile, 'tile-value').textContent, '2h 40m');
  assert.match(first(tile, 'tile-note').textContent, /work@example\.org/);
});

test('a peak of 100 is red, and the count of times is shown', () => {
  const tile = renderTiles(hist.tiles).children[1];
  assert.equal(first(tile, 'tile-value').textContent, '100%');
  assert.equal(first(tile, 'tile-value').dataset.tone, 'critical');
  assert.match(first(tile, 'tile-note').textContent, /2 times/);
});

test('no history at all is an em dash, NOT a zero', () => {
  const t = renderTiles({});
  const values = all(t, 'tile-value').map((v) => v.textContent);
  assert.deepEqual(values, ['—', '—', '—', '—'],
    'zero locked hours and no data are different facts');
  assert.deepEqual(all(t, 'tile-value').map((v) => v.dataset.tone), [undefined, undefined, undefined, undefined]);
});

test('a week with zero locked seconds says zero, not no data', () => {
  const t = renderTiles({ locked: { seconds: 0, when: [] } });
  assert.equal(first(t.children[0], 'tile-value').textContent, '0m');
  assert.match(first(t.children[0], 'tile-note').textContent, /nobody was locked/);
});

console.log('\ncards (§6.3)');

test('three columns per card, always, in fixed order', () => {
  const v = draw();
  for (const card of all(v, 'stat-card')) {
    assert.deepEqual(all(card, 'stat-col').map((c) => c.dataset.column),
      ['session', 'weekly_all', 'per_model']);
  }
});

test('an account with no per-model limit SAYS so rather than showing a blank', () => {
  const qa = all(draw(), 'stat-card').find((c) => c.dataset.email === 'qa@example.org');
  const col = all(qa, 'stat-col').find((c) => c.dataset.column === 'per_model');
  assert.equal(first(col, 'col-now').textContent, 'no per-model limit on this plan');
  assert.ok(col.find((n) => n.className === 'flat'), 'and draws the dotted baseline');
});

test('the caption of a column is the LAST sample, per model where there are several', () => {
  const main = all(draw(), 'stat-card').find((c) => c.dataset.email === 'main@example.com');
  const caps = all(main, 'col-now').map((n) => n.textContent);
  assert.match(caps[0], /^now \d+%$/);
  assert.equal(caps[2], 'Fable 74%');
});

test('the summary line ranks a lock above a peak', () => {
  const work = hist.accounts.find((a) => a.email === 'work@example.org');
  const series = hist.series.filter((s) => s.account_id === work.id);
  const line = summaryLine(work, series, hist.range);
  assert.equal(line.tone, 'critical');
  assert.match(line.text, /^locked 2h 40m this week$/);
});

test('a gap is reported with its cause, above the peak', () => {
  const qa = hist.accounts.find((a) => a.email === 'qa@example.org');
  const series = hist.series.filter((s) => s.account_id === qa.id);
  const line = summaryLine(qa, series, hist.range);
  assert.equal(line.tone, 'warning');
  assert.match(line.text, /gap .* HTTP 429/);
});

test('a quiet account says peak and never locked', () => {
  const main = hist.accounts.find((a) => a.email === 'main@example.com');
  const series = hist.series.filter((s) => s.account_id === main.id);
  assert.deepEqual(summaryLine(main, series, hist.range),
    { text: `peak ${main.summary.peak_session}% · never locked`, tone: null });
});

console.log('\ncharts (§6.4)');

test('a lock is drawn as a band, an open one reaching the right edge', () => {
  const work = all(draw(), 'stat-card').find((c) => c.dataset.email === 'work@example.org');
  const bands = all(work, 'band-lock');
  assert.equal(bands.length, 2);
  const open = bands[1];
  assert.equal(Number(open.attrs.x) + Number(open.attrs.width), 280,
    'the lock that has not ended must reach the edge, not vanish for lacking a `to`');
});

test('a gap is an amber band that says why', () => {
  const qa = all(draw(), 'stat-card').find((c) => c.dataset.email === 'qa@example.org');
  const band = all(qa, 'band-gap')[0];
  assert.ok(band, 'the 429 must be visible as a band');
  assert.match(band.textContent, /HTTP 429/);
});

test('the line BREAKS at the gap instead of crossing it', () => {
  const qa = all(draw(), 'stat-card').find((c) => c.dataset.email === 'qa@example.org');
  const line = all(qa, 'line')[0];
  assert.equal((line.attrs.d.match(/M/g) || []).length, 2,
    'two runs: a straight segment across a 429 is a measurement nobody took');
});

test('the session chart of a quiet account has no bands at all', () => {
  const main = all(draw(), 'stat-card').find((c) => c.dataset.email === 'main@example.com');
  assert.equal(all(main, 'band-lock').length, 0);
  assert.equal(all(main, 'band-gap').length, 0);
});

test('every chart is labelled for a screen reader', () => {
  for (const chart of all(draw(), 'chart')) {
    assert.match(chart.attrs['aria-label'], /@/, 'the label must name the account');
    assert.equal(chart.attrs.role, 'img');
  }
});

test('resets are drawn, and the session window has many of them in a week', () => {
  // THIS TEST PINS A DIVERGENCE FROM THE SPEC, deliberately and temporarily.
  //
  // 01.1 §6.3 says the session column is "always the last 24 h regardless of the
  // period". It is not: renderStatCard passes the FULL range to renderChart and
  // changes only the tick-label kind (stats.js:311-315), so the column plots the
  // whole week with 24h-style labels -- which is why a five-hour window shows about
  // 33 resets here instead of four or five.
  //
  // Left standing because it holds a true property of the code as it is, and the
  // card that would change it (T2.23) cannot start: it needs the history endpoints
  // of T2.15 and no such handler exists in the tree. When the column really becomes
  // the last 24 h, this assertion SHOULD fail -- and that will be the fix landing,
  // not a regression.
  const main = all(draw(), 'stat-card').find((c) => c.dataset.email === 'main@example.com');
  const col = all(main, 'stat-col')[0];
  assert.ok(all(col, 'reset').length > 20, 'a five-hour window resets about 33 times a week');
});

console.log('\nthe numbers behind the chart (§10, acceptance §11 item 11)');

test('every card has a table button, closed to begin with', () => {
  for (const card of all(draw(), 'stat-card')) {
    const btn = first(card, 'table-btn');
    assert.ok(btn, 'a chart is role=img: without this the numbers are unreachable');
    assert.equal(btn.tag, 'button');
    assert.equal(btn.attrs['aria-expanded'], 'false');
    assert.equal(first(card, 'values-slot').hidden, true);
  }
});

test('the table is built only when asked for, and then stays', () => {
  const card = all(draw(), 'stat-card')[0];
  const btn = first(card, 'table-btn');
  const slot = first(card, 'values-slot');
  assert.equal(slot.children.length, 0, 'a week of samples per card is not built for nobody');
  btn.listeners.click[0]();
  assert.equal(slot.hidden, false);
  assert.equal(btn.attrs['aria-expanded'], 'true');
  assert.equal(slot.children.length, 1);
  btn.listeners.click[0]();
  assert.equal(slot.hidden, true, 'and closes again');
  assert.equal(slot.children.length, 1, 'without rebuilding');
});

test('a column per series, a row per sample moment', () => {
  const main = hist.accounts[0];
  const series = hist.series.filter((s) => s.account_id === main.id);
  const table = valuesTable(series, (x) => x.kind);
  assert.deepEqual(table.children[0].children.map((c) => c.textContent),
    ['time', 'session', 'weekly_all', 'weekly_scoped']);
  const moments = new Set(series.flatMap((s) => s.points.map((p) => p.at)));
  assert.equal(table.children.length - 1, moments.size);
});

test('a series with no sample at a moment leaves the cell EMPTY, not zero', () => {
  // qa has a five-hour 429 hole; main does not. Together they force rows where one
  // side has nothing to say.
  const mainSession = hist.series.find((s) => s.account_id === hist.accounts[0].id);
  const qaSeries = hist.series.filter((s) => s.account_id === hist.accounts[2].id);
  const table = valuesTable([mainSession, ...qaSeries], (x) => x.kind);
  const blanks = table.children.slice(1).filter((r) => r.children[2].textContent === '');
  assert.ok(blanks.length >= 4, `the hole must show as empty cells, found ${blanks.length}`);
  for (const r of blanks) {
    assert.notEqual(r.children[2].textContent, '0%', 'no sample is not a measurement of zero');
  }
});

test('model colours are fixed by name, not by position', () => {
  const a = modelColors(hist.series);
  const reversed = modelColors([...hist.series].reverse());
  assert.deepEqual([...a.entries()], [...reversed.entries()],
    'a model must not change colour because the backend reordered its series');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
