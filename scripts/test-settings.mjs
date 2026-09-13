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
  showConflict, clearConflict, conflictCurrent, syncFolders,
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

test('the widget toggles are present, inert, and say when they arrive', () => {
  // Owner's decision 2026-09-13 (plan 01, decision 13): no tray and no SDL in the
  // first release. A switch that saves a value and changes nothing is worse than an
  // absent one -- the config would claim the widget is on while no widget exists.
  //
  // Both toggles, not one: they are independent controls and disabling only the
  // first would leave "Always on top" live for a window that cannot open.
  const panel = build();
  for (const key of ['widget.enabled', 'widget.always_on_top']) {
    const t = at(panel, key);
    assert.equal(t.disabled, true, `${key} must be inert until the widget ships`);
    assert.match(t.title, /after the first release/);
  }
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

console.log('\na 412 OFFERS to re-read (01.3 sec.3.8, acceptance line 3)');

const conflictReply = {
  etag: '"newer-etag"',
  config: { poll: { interval_sec: 900 }, ui: { time_bar: false } },
  accounts_found: [],
};

test('the panel STAYS, and so does everything typed into it', () => {
  // This is the whole point of the word "offers". Until 2026-09-08 a 412 closed the
  // panel and reopened it, so ten minutes of settings vanished behind a toast at the
  // one moment somebody is most likely to have typed a lot.
  const panel = build();
  const field = at(panel, 'poll.interval_sec');
  field.value = '123';

  showConflict(panel, conflictReply);

  assert.equal(panel.dataset.conflict, 'true');
  assert.equal(at(panel, 'poll.interval_sec').value, '123', 'the edit must survive the refusal');
});

test('the bar says what happened and offers the way out', () => {
  const panel = build();
  const bar = showConflict(panel, conflictReply);
  assert.equal(bar.attrs.role, 'alert', 'a conflict nobody is told about is a lost save');
  const btn = bar.find((n) => n.dataset && n.dataset.action === 'reload-settings');
  assert.ok(btn, 'the offer needs something to accept it with');
  assert.equal(btn.tag, 'button');
  assert.equal(btn.attrs.type, 'button', 'without type= a button inside a form submits it');
  assert.match(btn.textContent, /discard/, 'the button must say what it costs');
});

test('the bar carries the config the 412 sent, so accepting costs no second request', () => {
  // And, more to the point, re-reads the version the server actually refused us over
  // rather than whatever a later GET happens to return.
  const panel = build();
  showConflict(panel, conflictReply);
  assert.equal(conflictCurrent(panel), conflictReply);
  assert.equal(panel.querySelector('.settings-conflict').dataset.etag, '"newer-etag"');
});

test('a 412 with no `current` still tells the person, and asks for less', () => {
  const panel = build();
  const bar = showConflict(panel, null);
  assert.equal(conflictCurrent(panel), null);
  assert.match(bar.textContent, /did not send/);
  assert.match(bar.find((n) => n.dataset && n.dataset.action === 'reload-settings').textContent,
    /reopen/, 'nothing to discard against, so it offers a plain reopen');
});

test('a second attempt clears the first bar rather than stacking them', () => {
  const panel = build();
  showConflict(panel, conflictReply);
  showConflict(panel, conflictReply);
  assert.equal(panel.all((n) => n.className === 'settings-conflict').length, 1);
  clearConflict(panel);
  assert.equal(panel.all((n) => n.className === 'settings-conflict').length, 0);
  assert.equal(panel.dataset.conflict, undefined, 'a stale flag would tint a clean panel');
});

test('the bar sits right under the header, where it is read before the fields', () => {
  const panel = build();
  showConflict(panel, conflictReply);
  assert.equal(panel.children[0].className, 'settings-head');
  assert.equal(panel.children[1].className, 'settings-conflict');
});

console.log('\na `config` event while the panel is open (acceptance line 5)');

const rowPaths = (panel) =>
  panel.all((n) => n.className === 'folder-row').map((r) => r.dataset.path);

const withFolders = (folders, etag = '"e2"') => ({
  etag,
  config: { ...reply.config, folders },
  accounts_found: reply.accounts_found || [],
});

test('a folder removed elsewhere disappears from the list', () => {
  const panel = build();
  const before = rowPaths(panel);
  assert.ok(before.length >= 2, 'the fixture needs at least two folders for this to mean anything');

  const changed = syncFolders(panel, withFolders(reply.config.folders.slice(1)));
  assert.equal(changed, true);
  assert.deepEqual(rowPaths(panel), before.slice(1));
});

test('and a folder added elsewhere appears', () => {
  const panel = build();
  const grown = [...reply.config.folders, { id: 'f-new', path: 'D:/added/elsewhere' }];
  assert.equal(syncFolders(panel, withFolders(grown)), true);
  assert.ok(rowPaths(panel).includes('D:/added/elsewhere'));
});

test('the panel takes the new etag, or the next Save fights a change it knows about', () => {
  const panel = build();
  syncFolders(panel, withFolders(reply.config.folders, '"newer"'));
  assert.equal(panel.dataset.etag, '"newer"');
});

test('an event that changed nothing in the list reports no change', () => {
  // The caller raises the conflict bar on `true`; saying so for an unchanged list
  // would put an alarming notice on the panel every time any setting anywhere moved.
  const panel = build();
  assert.equal(syncFolders(panel, withFolders(reply.config.folders)), false);
});

test('EDITS ELSEWHERE IN THE PANEL SURVIVE the refresh', () => {
  // This is the whole reason the event does not close the panel. Somebody typing an
  // interval must not lose it because another tab touched an unrelated folder.
  const panel = build();
  at(panel, 'poll.interval_sec').value = '456';
  syncFolders(panel, withFolders(reply.config.folders.slice(1)));
  assert.equal(at(panel, 'poll.interval_sec').value, '456');
});

test('a panel with no folder list at all is left alone rather than crashing', () => {
  const bare = new Node('div');
  assert.equal(syncFolders(bare, withFolders([])), false);
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
