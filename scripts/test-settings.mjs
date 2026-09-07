// Tests for the settings panel (task T2.25), under node.
//
//   node scripts/test-settings.mjs
//
// The acceptance in 01.5 is about a sequence again: Save sends a PARTIAL PUT with
// If-Match, a 422 highlights the fields the server names with the server's own texts,
// a 412 offers to re-read. The trap underneath all three is what goes INTO the body:
// a browser-only setting or a server-computed field earns a 422 extra_forbidden, and
// the panel would then paint an error on a field nobody touched.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Node, installDocument } from './dom-stub.mjs';

installDocument({});
const {
  renderSettings, collect, bodyOf, diffConfig, isEmptyDiff, folderRef,
  folderNote, showErrors, unmatchedErrors, probeSummary, BROWSER_ONLY,
} = await import('../src/web/settings.js');

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

const reply = JSON.parse(readFileSync(new URL('../fixtures/api/config.json', import.meta.url)));
const build = () => renderSettings(reply);
const at = (panel, path) => panel.all((n) => n.dataset && n.dataset.path === path)[0];

console.log('the partial body (01.3 §3.8)');

test('an untouched panel produces an EMPTY body', () => {
  const body = bodyOf(build());
  assert.ok(isEmptyDiff(body), `nothing changed, so nothing is sent; got ${JSON.stringify(body)}`);
});

test('one changed number is the whole body', () => {
  const panel = build();
  at(panel, 'poll.interval_sec').value = 120;
  assert.deepEqual(bodyOf(panel), { poll: { interval_sec: 120 } });
});

test('a changed toggle is sent as a boolean, not a string', () => {
  const panel = build();
  at(panel, 'ui.time_bar').setAttribute('aria-checked', 'false');
  assert.deepEqual(bodyOf(panel), { ui: { time_bar: false } });
});

test('the working days are sent as a whole list, as the server merges them', () => {
  const panel = build();
  const days = at(panel, 'forecast.work_days');
  days.children.find((d) => d.dataset.day === 'sat').setAttribute('aria-pressed', 'true');
  assert.deepEqual(bodyOf(panel),
    { forecast: { work_days: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat'] } });
});

test('NO browser-only setting can reach the body', () => {
  const panel = build();
  at(panel, 'poll.interval_sec').value = 120;
  const flat = JSON.stringify(bodyOf(panel));
  for (const key of BROWSER_ONLY) {
    assert.ok(!flat.includes(`"${key}"`), `${key} is a localStorage setting, not a config key`);
  }
});

test('folders are sent as references, never as the objects read back', () => {
  const panel = build();
  panel.all((n) => n.className === 'folder-row')[2].remove();
  const body = bodyOf(panel);
  assert.equal(body.folders.length, 2);
  for (const f of body.folders) {
    assert.deepEqual(Object.keys(f), ['id'],
      'kind, login_dirs and problem are computed by the server: sending them is a 422');
  }
});

test('an untouched folder list is not sent at all', () => {
  const panel = build();
  at(panel, 'thresholds.warning').value = 75;
  assert.deepEqual(bodyOf(panel), { thresholds: { warning: 75 } });
});

test('diffConfig descends, and reports nothing for equal trees', () => {
  assert.deepEqual(diffConfig({ a: { b: 1, c: 2 } }, { a: { b: 1, c: 3 } }), { a: { c: 3 } });
  assert.deepEqual(diffConfig({ a: { b: 1 } }, { a: { b: 1 } }), {});
  assert.deepEqual(diffConfig({}, { a: 1 }), { a: 1 });
  assert.deepEqual(diffConfig({ list: [1, 2] }, { list: [1, 3] }), { list: [1, 3] },
    'a list changes as a whole or not at all');
});

test('a new folder goes by path, an existing one by id', () => {
  assert.deepEqual(folderRef({ id: 'x', path: '/p' }), { id: 'x' });
  assert.deepEqual(folderRef({ id: null, path: '/p' }), { path: '/p' });
});

console.log('\nwhat the folder rows say (§5.4)');

test('a parent folder lists the logins found inside it', () => {
  const note = folderNote(reply.config.folders[0], reply.accounts_found);
  assert.equal(note.text, 'parent folder · 3 logins found: nv-lang, dev, qa');
  assert.equal(note.tone, null);
});

test('a folder sharing a login with another says so', () => {
  const note = folderNote(reply.config.folders[1], reply.accounts_found);
  assert.equal(note.text, 'single login · work@example.org (same login as dev)',
    'adding this folder does NOT add an account, and the line has to say it');
});

test('a folder with no credentials is amber and says why', () => {
  const note = folderNote(reply.config.folders[2], reply.accounts_found);
  assert.equal(note.text, 'no .credentials.json here');
  assert.equal(note.tone, 'warning');
});

console.log('\nthe probe line (§5.4, 01.3 §3.9)');

test('a parent path lists what is inside it', () => {
  const line = probeSummary({
    kind: 'parent', already_listed: false, problem: null,
    login_dirs: [{ name: 'nv-lang' }, { name: 'dev' }],
  });
  assert.equal(line.text, 'parent folder · 2 logins found: nv-lang, dev');
  assert.equal(line.tone, null);
});

test('a single login names the account and any folder sharing it', () => {
  const line = probeSummary({
    kind: 'single', already_listed: false, problem: null,
    login_dirs: [{ name: '.claude', email: 'work@example.org', token_state: 'ok', same_login_as: [{ name: 'dev' }] }],
  });
  assert.equal(line.text, 'single login · work@example.org (same login as dev)');
});

test('an expired token and an already-listed path are both amber', () => {
  const stale = probeSummary({
    kind: 'single', login_dirs: [{ email: 'a@x', token_state: 'expired' }],
  });
  assert.match(stale.text, /token expired/);
  assert.equal(stale.tone, 'warning');
  const dup = probeSummary({ kind: 'parent', already_listed: true, login_dirs: [{ name: 'dev' }] });
  assert.match(dup.text, /already in the list/);
  assert.equal(dup.tone, 'warning');
});

test('the endpoint has NO summary field, and the line is built without one', () => {
  // The first version of probeSummary read `reply.summary`, which 01.3 §3.9 does not
  // define: every probe would have shown an empty line. Same trap as the nested
  // `limits` in the list renderer.
  const line = probeSummary({ kind: 'empty', login_dirs: [], problem: null });
  assert.equal(line.text, 'no .credentials.json here');
  assert.equal(probeSummary({ kind: 'missing' }).text, 'no such folder');
  assert.equal(probeSummary(null).tone, 'warning');
});

console.log('\nerrors from the server (§3.8, §5)');

test('a 422 paints the fields it names, with the SERVER text', () => {
  const panel = build();
  const painted = showErrors(panel, [
    { field: 'poll.interval_sec', message: 'minimum is 60 s (the server rate-limits eager polling)' },
    { field: 'thresholds.critical', message: 'critical must be above warning' },
  ]);
  assert.equal(painted, 2);
  const input = at(panel, 'poll.interval_sec');
  assert.equal(input.dataset.invalid, 'true');
  assert.equal(input.parent.querySelector('.field-error').textContent,
    'minimum is 60 s (the server rate-limits eager polling)');
});

test('a second save clears the marks of the first', () => {
  const panel = build();
  showErrors(panel, [{ field: 'poll.interval_sec', message: 'too small' }]);
  showErrors(panel, [{ field: 'thresholds.warning', message: 'out of range' }]);
  assert.equal(at(panel, 'poll.interval_sec').dataset.invalid, undefined);
  assert.equal(at(panel, 'poll.interval_sec').parent.querySelector('.field-error').textContent, '');
  assert.equal(at(panel, 'thresholds.warning').dataset.invalid, 'true');
});

test('a toggle named by an error is cleared too, not left red and mute', () => {
  const panel = build();
  showErrors(panel, [{ field: 'forecast.enabled', message: 'nope' }]);
  assert.equal(at(panel, 'forecast.enabled').dataset.invalid, 'true');
  showErrors(panel, []);
  assert.equal(at(panel, 'forecast.enabled').dataset.invalid, undefined);
});

test('an error naming a field the panel does not show is reported, not swallowed', () => {
  const panel = build();
  const errs = [{ field: 'storage.threads', message: 'must be 1..8' }];
  assert.equal(showErrors(panel, errs), 0);
  assert.deepEqual(unmatchedErrors(panel, errs), errs,
    'a 422 that paints nothing looks exactly like a successful save');
});

console.log('\nthe panel itself (§5)');

test('the LAN toggle is present, inert, and says when it arrives', () => {
  const lan = at(build(), 'server.allow_lan');
  assert.equal(lan.disabled, true);
  assert.match(lan.title, /later version/);
});

test('every folder row can be removed and names what it removes', () => {
  const rows = build().all((n) => n.className === 'folder-row');
  assert.equal(rows.length, 3);
  for (const r of rows) {
    const drop = r.find((n) => n.className === 'icon-btn folder-drop');
    assert.match(drop.attrs['aria-label'], /^remove /);
  }
});

test('the panel carries the etag it was built from', () => {
  assert.equal(build().dataset.etag, reply.etag,
    'without it the save cannot send If-Match and gets a 428');
});

test('the interval field repeats the minimum under itself', () => {
  const hint = at(build(), 'poll.interval_sec').parent.find((n) => n.className === 'field-hint');
  assert.match(hint.textContent, /minimum is 60 s/);
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
