// Structure test for the folders statistics view (task T2.24), under node.
//
//   node scripts/test-folders.mjs
//
// The acceptance in 01.5 is: "a change of e-mail in the fixture BREAKS the line and
// changes its colour; the occupancy strip has a grey `expired` tail; the note is
// shown". All three are statements about structure, and all three are the kind of
// thing that looks plausible when wrong — a line that runs straight through a
// handover simply looks like an account that used more.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Node, installDocument } from './dom-stub.mjs';

const view = new Node('section');
installDocument({ 'view-stats': view });
const { occupancySegments, accountColors } = await import('../src/web/chart.js');
const { renderFolders, occupancyOf, columnsOfFolder, nowLine, renderFolderTiles, dailyPeaks, secondModelOf} =
  await import('../src/web/folders.js');

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const hist = JSON.parse(readFileSync(new URL('../fixtures/api/history-folders.json', import.meta.url)));
const draw = () => { renderFolders(hist, '30d'); return view; };
const all = (n, cls) => n.all((x) => x.className === cls);
const first = (n, cls) => n.find((x) => x.className === cls);
const cardOf = (name) => all(draw(), 'folder-card').find((c) => c.dataset.folder === name);

console.log('the occupancy journal (§7.3, §7.4)');

test('segments cover the WHOLE range, holes included', () => {
  const segs = occupancySegments(occupancyOf(hist, hist.folders[2].id), hist.range);
  assert.equal(segs[0].x, 0);
  const last = segs[segs.length - 1];
  assert.equal(Math.round(last.x + last.width), 280, 'the strip must reach the right edge');
});

test('a folder whose login expired ends in a grey `no login` stretch', () => {
  const segs = occupancySegments(occupancyOf(hist, hist.folders[2].id), hist.range);
  const tail = segs[segs.length - 1];
  assert.equal(tail.email, null, 'an absent login is a segment, not an absence of one');
  assert.ok(tail.width > 100, 'two weeks of a month is about half the strip');
});

test('three logins in a row leave no hole between them', () => {
  const segs = occupancySegments(occupancyOf(hist, hist.folders[0].id), hist.range);
  assert.deepEqual(segs.map((s) => s.email),
    ['main@example.com', 'work@example.org', 'qa@example.org']);
  for (let i = 1; i < segs.length; i++) {
    assert.equal(Math.round(segs[i].x), Math.round(segs[i - 1].x + segs[i - 1].width));
  }
});

test('an empty journal is one grey stretch, not nothing', () => {
  const segs = occupancySegments([], hist.range);
  assert.equal(segs.length, 1);
  assert.equal(segs[0].email, null);
  assert.equal(segs[0].width, 280);
});

test('account colours are fixed by e-mail at first appearance', () => {
  const c = accountColors(hist.occupancy);
  assert.equal(c.get('main@example.com'), 'var(--series-1)');
  assert.equal(c.get('work@example.org'), 'var(--series-2)');
  assert.equal(c.get('qa@example.org'), 'var(--series-3)');
  assert.deepEqual([...accountColors([...hist.occupancy]).entries()], [...c.entries()]);
});

console.log('\nthe card (§7.3)');

test('one card per folder, with the strip above the columns', () => {
  const v = draw();
  assert.equal(all(v, 'folder-card').length, 3);
  const dev = cardOf('dev');
  assert.ok(first(dev, 'occupancy'), 'the strip');
  assert.equal(all(dev, 'occ-block').length, 3);
  assert.equal(all(dev, 'stat-col').length, 3);
});

test('a switch of account BREAKS the line and recolours it', () => {
  const dev = cardOf('dev');
  const col = all(dev, 'stat-col').find((c) => c.dataset.column === 'session');
  const lines = all(col, 'line');
  assert.equal(lines.length, 3, 'three segments, three separate lines - never one');
  const colors = lines.map((l) => l.attrs.style);
  assert.equal(new Set(colors).size, 3, 'a jump after a handover is another account, not usage');
});

test('a folder held by one account all month draws ONE line', () => {
  const col = all(cardOf('nv-lang'), 'stat-col').find((c) => c.dataset.column === 'session');
  assert.equal(all(col, 'line').length, 1);
});

test('the occupancy strip is the backdrop of every chart', () => {
  const dev = cardOf('dev');
  const backs = all(dev, 'backdrop');
  assert.equal(backs.length, 9, 'three stretches under each of three columns');
  assert.equal(all(cardOf('ops'), 'backdrop-empty').length, 3, 'and the grey one too');
});

test('a wide stretch is labelled inside, a narrow one only by tooltip', () => {
  const blocks = all(cardOf('dev'), 'occ-block');
  assert.equal(blocks[0].textContent, 'main@');
  for (const b of blocks) assert.match(b.title, / → /, 'every block says who and when');
});

test('the now line names the current login, or says since when there is none', () => {
  const segsOps = occupancySegments(occupancyOf(hist, hist.folders[2].id), hist.range);
  const ops = nowLine(hist.folders[2], segsOps);
  assert.equal(ops.tone, 'warning');
  assert.match(ops.text, /^no login since .* token expired$/);

  const segsDev = occupancySegments(occupancyOf(hist, hist.folders[0].id), hist.range);
  const dev = nowLine(hist.folders[0], segsDev);
  assert.equal(dev.tone, null);
  assert.match(dev.text, /^now: qa@example\.org · since /);
});

test('two models of DIFFERENT accounts are both solid', () => {
  const cols = columnsOfFolder(hist.series.filter((s) => s.login_dir_id === hist.folders[0].id));
  const perModel = cols[2].series;
  assert.equal(perModel.length, 2);
  assert.deepEqual(perModel.map((s) => s.dashed), [false, false],
    'each is the first model of its own account; the colour already tells them apart');
});

test('the SECOND model of one account is dashed', () => {
  // Stated directly rather than through the fixture: the fixture happens to have no
  // account holding two models in one folder, so a test reading it would be
  // describing the fixture and not the rule (01.1 §7.3).
  const cols = columnsOfFolder([
    { kind: 'weekly_scoped', account_id: 'a', email: 'a@x', model: 'Fable', from: '2026-09-01T00:00:00Z' },
    { kind: 'weekly_scoped', account_id: 'a', email: 'a@x', model: 'Opus', from: '2026-09-02T00:00:00Z' },
    { kind: 'weekly_scoped', account_id: 'b', email: 'b@x', model: 'Fable', from: '2026-09-03T00:00:00Z' },
  ]);
  assert.deepEqual(cols[2].series.map((s) => [s.email, s.model, s.dashed]), [
    ['a@x', 'Fable', false],
    ['a@x', 'Opus', true],
    ['b@x', 'Fable', false],
  ]);
});

console.log('\nthe frame (§7.1, §7.2, §7.4)');

test('the limitation is printed on the page, not only in the plan', () => {
  const note = first(draw(), 'view-note');
  assert.ok(note, 'the note must be visible');
  assert.match(note.textContent, /counts per login/);
});

test('the legend names ACCOUNTS, the grey, and the dash it draws', () => {
  // 01.1 par.7.1 lists account swatches, the grey `no login`, AND a dashed entry for
  // the second model. The dash was drawn on the chart -- columnsOfFolder marks the
  // second model of an account `dashed` -- and explained nowhere, so a broken line
  // appeared with no key. The obvious reading of a dash is "estimated" or "no data",
  // and it is neither.
  const items = all(draw(), 'legend-item');
  const labels = items.map((i) => i.textContent);
  assert.deepEqual(labels.slice(0, 4),
    ['main@example.com', 'work@example.org', 'qa@example.org', 'no login']);

  // The dashed one is named from the DATA, not hard-coded to the spec's example
  // ("Opus"): the second model differs per account and plan, and a legend naming a
  // model nobody uses is worse than one naming none.
  const dashed = items.filter((i) => i.dataset.dashed === 'true');
  const second = secondModelOf(hist);
  if (second) {
    assert.equal(dashed.length, 1, 'one dashed entry when a second model is drawn');
    assert.equal(dashed[0].textContent, second, 'it names the model actually dashed');
  } else {
    assert.equal(dashed.length, 0, 'no second model, no dash to explain');
  }
});

test('the grouping row marks Folders as the selected one', () => {
  const chips = all(draw(), 'chip').filter((c) => c.dataset.group);
  assert.deepEqual(chips.map((c) => c.attrs['aria-selected']), ['false', 'true']);
});

test('the tiles answer the folder questions, not the account ones', () => {
  const t = renderFolderTiles(hist.tiles);
  const labels = all(t, 'tile-label').map((n) => n.textContent);
  assert.deepEqual(labels, ['Login switches · 30 d', 'Locked while in a folder',
    'Folder with most logins', 'Days without a login']);
  assert.equal(all(t, 'tile-value')[0].textContent, '2');
  assert.match(all(t, 'tile-note')[0].textContent, /dev: main → work → qa/);
  assert.equal(all(t, 'tile-value')[3].dataset.tone, 'warning');
});

test('an empty history says so instead of an empty frame', () => {
  renderFolders({ folders: [], range: null });
  assert.equal(view.children.length, 1);
  assert.match(view.children[0].textContent, /no folder history yet/);
});


// ------------------------------------------- daily peaks at 30 d (par.7.3) --

test('at 30 d the session column is one point per day, the day maximum, at noon', () => {
  // The column has been captioned "session · daily peaks" from the start and the raw
  // points went straight through. 01.1 par.7.3 asks for the maximum per calendar day
  // at noon, "otherwise 24 h x 30 blur into noise" -- at 30 d that is thirty readable
  // points against about eight thousand overlapping ones.
  //
  // A caption describing work nobody did is worse than none: it tells the reader the
  // noise IS the peaks.
  const pts = [
    { at: '2026-09-01T03:00:00Z', percent: 10 },
    { at: '2026-09-01T18:00:00Z', percent: 62 },   // the day's max
    { at: '2026-09-01T21:00:00Z', percent: 40 },
    { at: '2026-09-02T09:00:00Z', percent: 33 },
    { at: '2026-09-02T23:50:00Z', percent: 71 },   // late peak, still 2 September
  ];
  const out = dailyPeaks({ kind: 'session', points: pts });

  assert.equal(out.points.length, 2, 'two calendar days, two points');
  assert.deepEqual(out.points.map((p) => p.percent), [62, 71], 'the maximum of each');
  assert.deepEqual(out.points.map((p) => p.at),
    ['2026-09-01T12:00:00Z', '2026-09-02T12:00:00Z'],
    'at noon: the point stands for the whole day, so a 23:50 peak must not drift into the next one');

  // Everything else about the series survives.
  assert.equal(out.kind, 'session');

  // Empty in, empty out -- not a crash and not a phantom point.
  assert.deepEqual(dailyPeaks({ points: [] }).points, []);
  assert.deepEqual(dailyPeaks({}).points, []);

  // An unparsable stamp is skipped rather than placed at the epoch.
  assert.equal(dailyPeaks({ points: [{ at: 'nonsense', percent: 9 }] }).points.length, 0);
});

test('below 30 d the session column keeps its raw samples, and says so', () => {
  // Only the long period aggregates. At shorter ones the samples ARE the point, and
  // the title must not promise peaks it is not showing -- the defect this replaces,
  // in the other direction.
  const series = [{ kind: 'session', points: [{ at: '2026-09-01T03:00:00Z', percent: 10 },
                                              { at: '2026-09-01T18:00:00Z', percent: 62 }] }];
  const long = columnsOfFolder(series, '30d')[0];
  const short = columnsOfFolder(series, '7d')[0];

  assert.match(long.title, /daily peaks/);
  assert.equal(long.series[0].points.length, 1, 'one day, one peak');

  assert.doesNotMatch(short.title, /daily peaks/,
    'at 7 d the column shows raw samples and must not claim peaks');
  assert.equal(short.series[0].points.length, 2, 'both samples survive');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
