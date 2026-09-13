// settings.js — the settings panel (task T2.25), subplan 01.1 §5.
//
// The panel is a popover built from `GET /api/config` and saved with ONE partial
// `PUT /api/config` carrying `If-Match` (01.3 §3.8). Two things here are worth more
// than the markup and are pure functions with tests:
//
//   diffConfig  — the body is PARTIAL: only branches that actually changed. Sending
//                 the whole tree back would rewrite fields the person never touched,
//                 and would make every save a conflict with anyone editing the file.
//
//   BROWSER_ONLY — layout, bar style and the countdown live in localStorage and are
//                 not config keys at all (§5.1). Putting one in the body earns a
//                 `422 extra_forbidden`, and the panel would blame the wrong field.
import { el } from './render.js';

/**
 * Settings that belong to this browser, never to the config file (01.1 §5.1).
 *
 * DOCUMENTATION NOW, NOT A FILTER. `collect` used to drop a value whose path ENDED in
 * one of these names, which decided a control's destination by guessing. Two things
 * were wrong with that at once: `ui.countdown` and `ui.hide_stale` are neighbours in
 * one section and belong to different places, and the name `view` here would have
 * swallowed the first config key ever spelled `widget.view`.
 *
 * A control now declares its store (`data-store="browser"`), and this list stays as
 * the written record of which settings those are -- checked against the panel by
 * scripts/test-settings.mjs, so the two cannot drift apart in silence.
 */
export const BROWSER_ONLY = ['view', 'bar_style', 'countdown', 'stats_range', 'stats_group'];

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/**
 * The minimal partial tree turning `base` into `edited` (01.3 §3.8: "the body is a
 * partial `config` tree; lists are replaced whole").
 *
 * Lists are compared as a whole and sent whole, because that is how the server merges
 * them — sending a "changed" element alone would delete the rest.
 */
export function diffConfig(base, edited) {
  const out = {};
  for (const key of Object.keys(edited || {})) {
    const a = base ? base[key] : undefined;
    const b = edited[key];
    if (isObject(a) && isObject(b)) {
      const inner = diffConfig(a, b);
      if (Object.keys(inner).length) out[key] = inner;
    } else if (JSON.stringify(a) !== JSON.stringify(b)) {
      out[key] = b;
    }
  }
  return out;
}

/** Does this partial contain anything at all? An empty PUT is a wasted 412. */
export const isEmptyDiff = (d) => !d || !Object.keys(d).length;

/**
 * A folder as `PUT /api/config` wants it (01.3 §3.8): an existing one by `id`, a new
 * one by `path`. Sending the whole read-back object would carry `kind`, `login_dirs`
 * and `problem` — all computed by the server, none of them settings, and every one of
 * them a `422 extra_forbidden`.
 */
export const folderRef = (f) => (f.id ? { id: f.id } : { path: f.path });

/** The line under a folder's path (§5.4), from what the server found there. */
export function folderNote(folder, accountsFound = []) {
  if (folder.problem) return { text: folder.problem, tone: 'warning' };
  const dirs = folder.login_dirs || [];
  if (folder.kind === 'parent') {
    return dirs.length
      ? { text: `parent folder · ${dirs.length} logins found: ${dirs.map((d) => d.name).join(', ')}`, tone: null }
      : { text: 'parent folder · no logins inside', tone: 'warning' };
  }
  const dirIds = new Set(dirs.map((d) => d.id));
  const account = accountsFound.find((a) => (a.dirs || []).some((d) => dirIds.has(d.id)));
  if (!account) return { text: 'no .credentials.json here', tone: 'warning' };
  // The same login in two folders is ONE account, and saying so here prevents the
  // reasonable-but-wrong conclusion that adding the folder adds a login (§5.4).
  const others = (account.dirs || []).filter((d) => !dirIds.has(d.id));
  const also = others.length ? ` (same login as ${others.map((d) => d.name).join(', ')})` : '';
  return { text: `single login · ${account.email}${also}`, tone: null };
}

/**
 * The "what is there" line for a probed path (§5.4), built from the reply of
 * `POST /api/folders/probe` (01.3 §3.9).
 *
 * Written against the documented fields — `kind`, `login_dirs[]`, `problem`,
 * `already_listed` — after the first version read a `summary` field that the endpoint
 * does not have and would have shown an empty line for every path. The same mistake
 * as the nested `limits` in the list renderer, caught the same way: by reading the
 * contract instead of assuming it.
 */
export function probeSummary(reply) {
  if (!reply) return { text: 'no answer from the server', tone: 'warning' };
  if (reply.problem) return { text: reply.problem, tone: 'warning' };
  if (reply.kind === 'missing') return { text: 'no such folder', tone: 'warning' };
  const dirs = reply.login_dirs || [];
  if (reply.kind === 'empty' || !dirs.length) {
    return { text: 'no .credentials.json here', tone: 'warning' };
  }
  const already = reply.already_listed ? ' · already in the list' : '';
  if (reply.kind === 'parent') {
    return {
      text: `parent folder · ${dirs.length} logins found: ${dirs.map((d) => d.name).join(', ')}${already}`,
      tone: reply.already_listed ? 'warning' : null,
    };
  }
  const one = dirs[0];
  const same = (one.same_login_as || []).map((d) => d.name);
  const also = same.length ? ` (same login as ${same.join(', ')})` : '';
  const stale = one.token_state && one.token_state !== 'ok' ? ` · token ${one.token_state}` : '';
  return {
    text: `single login · ${one.email || 'unknown'}${also}${stale}${already}`,
    tone: reply.already_listed || stale ? 'warning' : null,
  };
}

// ------------------------------------------------------------------ fields --

function field(label, input, hint) {
  const row = el('label', 'field');
  row.append(el('span', 'field-label', label));
  row.append(input);
  if (hint) row.append(el('span', 'field-hint', hint));
  row.append(el('span', 'field-error'));
  return row;
}

function number(path, value, attrs = {}) {
  const n = el('input', 'input');
  n.setAttribute('type', 'number');
  n.dataset.path = path;
  n.value = value;
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

/**
 * A switch. `store` says WHERE its value belongs -- 'config' (the default) or
 * 'browser'.
 *
 * THE CONTROL DECLARES IT; NOTHING GUESSES. `collect` used to decide by matching the
 * LAST SEGMENT of the path against a list of names, which is wrong in both
 * directions: `ui.countdown` and `ui.hide_stale` sit side by side in one section and
 * belong to different places (01.1 lines 300-301 -- one is localStorage.countdown,
 * the other is `[ui] hide_stale` in the config file), while the name `view` in that
 * list would have swallowed the first config key ever called `widget.view`.
 *
 * A leaf name is not an address. This attribute is.
 */
function toggle(path, on, store = 'config') {
  const t = el('button', 'toggle');
  t.setAttribute('type', 'button');
  t.setAttribute('role', 'switch');
  t.setAttribute('aria-checked', String(!!on));
  t.dataset.path = path;
  if (store !== 'config') t.dataset.store = store;
  return t;
}

function text(path, value, placeholder) {
  const n = el('input', 'input');
  n.setAttribute('type', 'text');
  if (placeholder) n.setAttribute('placeholder', placeholder);
  n.dataset.path = path;
  n.value = value == null ? '' : value;
  return n;
}

/**
 * A choice of two, as a pair of buttons -- 01.1 §5.1 draws `List / Cards` and
 * `Rounded / Blocks` this way.
 *
 * WHY IT EXISTS ONLY NOW. The design has shown both since the mock was drawn and the
 * page built neither; `BROWSER_ONLY` already named `view` and `bar_style`, so half
 * the plumbing was waiting for them. The artboard guard could not see the gap because
 * it searched the whole source for the label's letters, and found `Bar style` inside
 * the identifier `bar.style.width`. Tightened 2026-09-09, it named all four missing
 * labels at once.
 *
 * `role="radiogroup"` rather than a `<select>`: two options are quicker to hit than a
 * dropdown, and 01.1 §10 wants arrow keys to move between them.
 */
function choice(path, value, options, store = 'config') {
  const group = el('div', 'choice');
  group.setAttribute('role', 'radiogroup');
  group.dataset.path = path;
  if (store !== 'config') group.dataset.store = store;
  for (const [val, label] of options) {
    const b = el('button', 'choice-option', label);
    b.setAttribute('type', 'button');
    b.setAttribute('role', 'radio');
    b.setAttribute('aria-checked', String(val === value));
    b.dataset.value = val;
    group.append(b);
  }
  return group;
}

/** The stored value of a browser-side preference, or its default. */
function browserPref(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;                                    // private mode: not fatal
  }
}

const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

// ------------------------------------------------------------------- panel --

/**
 * Build the panel. It holds the reply it was built from, so `collect` can produce a
 * whole tree and `diffConfig` the partial — a panel that only remembered its own
 * inputs could not tell "unchanged" from "absent".
 */
export function renderSettings(reply) {
  const cfg = (reply && reply.config) || {};
  const panel = el('div', 'settings');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'settings');
  panel.dataset.etag = reply && reply.etag ? reply.etag : '';
  panel.__base = cfg;
  panel.__accounts = (reply && reply.accounts_found) || [];

  const head = el('header', 'settings-head', 'Settings');
  panel.append(head);

  // 5.1 View — browser-only, and labelled as such so nobody looks for it in the file.
  const view = section(panel, 'View', 'kept in this browser, not in the config file');
  // 01.1 §5.1 lines 298-299: both live in localStorage, neither in the config file.
  view.append(field('Layout',
    choice('ui.view', browserPref('view', 'list'),
           [['list', 'List'], ['cards', 'Cards']], 'browser')));
  view.append(field('Bar style',
    choice('ui.bar_style', browserPref('bar_style', 'rounded'),
           [['rounded', 'Rounded'], ['blocks', 'Blocks']], 'browser')));
  view.append(field('Reset time',
    toggle('ui.countdown', browserCountdown(), 'browser'), '\u00b7 show countdown'));
  view.append(field('Hide logins with an expired token',
    toggle('ui.hide_stale', cfg.ui && cfg.ui.hide_stale)));

  // 5.2
  const bars = section(panel, 'Time elapsed bar');
  bars.append(field('Show the elapsed-time strip',
    toggle('ui.time_bar', cfg.ui && cfg.ui.time_bar), '\u00b7 thin line under each bar'));

  // 5.3
  const fc = cfg.forecast || {};
  const forecast = section(panel, 'Forecast',
    'a straight line from the current working-hours rate to the reset');
  forecast.append(field('Show forecast at reset',
    toggle('forecast.enabled', fc.enabled), '\u00b7 hatched part of the bar'));
  const days = el('div', 'days');
  days.dataset.path = 'forecast.work_days';
  for (const d of DAYS) {
    const b = el('button', 'day', d[0].toUpperCase() + d.slice(1, 2));
    b.setAttribute('type', 'button');
    b.setAttribute('aria-pressed', String((fc.work_days || []).includes(d)));
    b.dataset.day = d;
    days.append(b);
  }
  forecast.append(field('Working days', days));
  forecast.append(field('Working hours from', text('forecast.work_from', fc.work_from, '09:00')));
  forecast.append(field('to', text('forecast.work_to', fc.work_to, '19:00')));
  forecast.append(field('Usage outside working hours',
    number('forecast.off_hours_rate', fc.off_hours_rate ?? 0, { min: 0, max: 100 }),
    'of the working rate'));

  // 5.4
  const folders = section(panel, 'Login folders', 'where accounts are discovered');
  const list = el('div', 'folder-list');
  list.dataset.path = 'folders';
  for (const f of cfg.folders || []) list.append(folderRow(f, panel.__accounts));
  folders.append(list);
  const add = el('div', 'folder-add');
  add.append(text('folders.new', '', 'path to a login folder or a parent of several'));
  const probe = el('button', 'btn', 'Check');
  probe.setAttribute('type', 'button');
  probe.dataset.action = 'probe';
  add.append(probe);
  add.append(el('div', 'probe-note'));
  folders.append(add);

  // 5.5
  const poll = section(panel, 'Polling');
  poll.append(field('Interval, seconds',
    number('poll.interval_sec', (cfg.poll && cfg.poll.interval_sec) ?? 300, { min: 60 }),
    'minimum is 60 s (the server rate-limits eager polling)'));

  // 5.6
  const th = cfg.thresholds || {};
  const thresholds = section(panel, 'Thresholds');
  thresholds.append(field('Warning, %', number('thresholds.warning', th.warning ?? 70, { min: 1, max: 100 })));
  thresholds.append(field('Critical, %', number('thresholds.critical', th.critical ?? 90, { min: 1, max: 100 })));

  // 5.7 — the LAN toggle is inert until phase F6 and says so rather than failing.
  const srv = cfg.server || {};
  const server = section(panel, 'Server');
  server.append(el('p', 'settings-note',
    `Listening on ${srv.bind || '127.0.0.1'}:${srv.port ?? 7391}`));
  const lan = toggle('server.allow_lan', srv.allow_lan);
  lan.disabled = true;
  lan.title = 'LAN access arrives in a later version';
  server.append(field('Allow access from the local network', lan,
    'needs a token and a certificate — LAN access arrives in a later version'));

  // 5.8 — the widget toggles are inert in the first release and say so, exactly the
  // way the LAN toggle above does. Owner's decision 2026-09-13 (plan 01, decision
  // 13): no tray and no SDL in the MVP. A switch that saves a value and changes
  // nothing is worse than an absent one -- the config would then claim the widget is
  // on while no widget exists, and the person would have no way to see why.
  const w = cfg.widget || {};
  const widget = section(panel, 'Desktop widget');
  const wEnabled = toggle('widget.enabled', w.enabled);
  const wTop = toggle('widget.always_on_top', w.always_on_top);
  for (const t of [wEnabled, wTop]) {
    t.disabled = true;
    t.title = 'the desktop widget arrives after the first release';
  }
  widget.append(field('Show the widget', wEnabled,
    'the page in the browser does the same job — the widget arrives after the first release'));
  widget.append(field('Always on top', wTop));

  const footer = el('footer', 'settings-foot');
  const cancel = el('button', 'btn', 'Cancel');
  cancel.setAttribute('type', 'button');
  cancel.dataset.action = 'cancel';
  const save = el('button', 'btn btn-primary', 'Save');
  save.setAttribute('type', 'button');
  save.dataset.action = 'save';
  footer.append(cancel, save);
  panel.append(footer);
  return panel;
}

function section(panel, title, note) {
  const s = el('section', 'settings-section');
  s.append(el('h3', 'section-title', title));
  if (note) s.append(el('p', 'settings-note', note));
  panel.append(s);
  return s;
}

function folderRow(folder, accountsFound) {
  const row = el('div', 'folder-row');
  row.dataset.id = folder.id || '';
  row.dataset.path = folder.path || '';
  const p = el('div', 'folder-path', folder.path || '(hidden over LAN)');
  p.title = folder.path || '';
  row.append(p);
  const note = folderNote(folder, accountsFound);
  const n = el('div', 'folder-note', note.text);
  if (note.tone) n.dataset.tone = note.tone;
  row.append(n);
  const drop = el('button', 'icon-btn folder-drop', '\u00d7');
  drop.setAttribute('type', 'button');
  drop.setAttribute('aria-label', `remove ${folder.path || 'folder'}`);
  drop.dataset.action = 'drop-folder';
  row.append(drop);
  return row;
}

// ---------------------------------------------------------------- collect ---

/** Read the panel back into a config tree of the same shape it was built from. */
/** The current value of the countdown preference, or its default. */
export function browserCountdown() {
  try {
    const v = localStorage.getItem('countdown');
    return v === null ? true : v === 'true';
  } catch {
    return true;                                        // private mode: not fatal
  }
}

/**
 * The settings that belong to THIS BROWSER, keyed by their localStorage name.
 *
 * This function is the half that did not exist. `BROWSER_ONLY` named five settings
 * and `collect` dropped anything matching, which meant the countdown toggle produced
 * an empty PUT body, Save closed the panel, and nobody wrote localStorage.countdown.
 * The switch moved and nothing happened -- a silent outcome, which api.md:26 forbids.
 */
export function collectBrowser(panel) {
  const out = {};
  for (const t of panel.querySelectorAll('.toggle')) {
    if (t.dataset.store !== 'browser' || !t.dataset.path) continue;
    const leaf = t.dataset.path.split('.').pop();
    out[leaf] = t.getAttribute('aria-checked') === 'true';
  }
  for (const input of panel.querySelectorAll('.input')) {
    if (input.dataset.store !== 'browser' || !input.dataset.path) continue;
    out[input.dataset.path.split('.').pop()] = input.value;
  }
  for (const g of panel.querySelectorAll('.choice')) {
    if (g.dataset.store !== 'browser' || !g.dataset.path) continue;
    for (const b of g.querySelectorAll('.choice-option')) {
      if (b.getAttribute('aria-checked') === 'true') {
        out[g.dataset.path.split('.').pop()] = b.dataset.value;
      }
    }
  }
  return out;
}

/** Write them where they live. Returns the names actually stored. */
export function saveBrowser(settings) {
  const done = [];
  for (const [k, v] of Object.entries(settings)) {
    try {
      localStorage.setItem(k, String(v));
      done.push(k);
    } catch { /* private mode: the setting is lost, the save is not */ }
  }
  return done;
}

export function collect(panel) {
  const out = {};
  // A setting that belongs to this browser never reaches the config tree (sec.5.1).
  // Until 2026-09-08 BROWSER_ONLY was a list nothing consulted -- the header called
  // it a protection and the panel simply had no such control yet, so the test that
  // asserts the outcome passed with nothing to protect against.
  const put = (path, value) => {
    const parts = path.split('.');
    let node = out;
    for (const key of parts.slice(0, -1)) node = (node[key] ||= {});
    node[parts[parts.length - 1]] = value;
  };

  for (const input of panel.querySelectorAll('.input')) {
    const path = input.dataset.path;
    if (!path || path === 'folders.new') continue;      // the add box is not a setting
    if (input.dataset.store === 'browser') continue;    // collected by collectBrowser
    const raw = input.value;
    put(path, input.getAttribute('type') === 'number' ? Number(raw) : raw);
  }
  for (const g of panel.querySelectorAll('.choice')) {
    if (g.dataset.store === 'browser' || !g.dataset.path) continue;
    for (const b of g.querySelectorAll('.choice-option')) {
      if (b.getAttribute('aria-checked') === 'true') put(g.dataset.path, b.dataset.value);
    }
  }
  for (const t of panel.querySelectorAll('.toggle')) {
    if (t.dataset.store === 'browser') continue;        // collected by collectBrowser
    if (t.dataset.path) put(t.dataset.path, t.getAttribute('aria-checked') === 'true');
  }
  const days = panel.querySelector('.days');
  if (days) {
    put('forecast.work_days', Array.from(days.querySelectorAll('.day'))
      .filter((n) => n.getAttribute('aria-pressed') === 'true')
      .map((n) => n.dataset.day));
  }
  const rows = Array.from(panel.querySelectorAll('.folder-row'));
  out.folders = rows.map((r) => folderRef({ id: r.dataset.id || null, path: r.dataset.path }));
  return out;
}

/**
 * The body of the `PUT`: what changed, and nothing else.
 *
 * `folders` is special-cased because the panel holds REFERENCES (`{id}` / `{path}`)
 * while the reply holds full objects with computed fields. Comparing those two shapes
 * directly would mark the list changed on every open.
 */
export function bodyOf(panel) {
  const base = panel.__base || {};
  const edited = collect(panel);
  const baseRefs = (base.folders || []).map(folderRef);
  const foldersChanged = JSON.stringify(baseRefs) !== JSON.stringify(edited.folders);
  const withoutFolders = { ...edited };
  delete withoutFolders.folders;

  const body = diffConfig(base, withoutFolders);
  if (foldersChanged) body.folders = edited.folders;
  return body;
}

// ----------------------------------------------------------------- errors ---

/**
 * Paint `errors[]` from a `422` onto the fields they name (01.3 §3.8: dotted notation
 * in `errors[].field`, one entry per field, all of them in one response).
 *
 * The TEXT is the server's, verbatim. The page has no second opinion about why a
 * value is wrong, and inventing one here is how two different messages for one rule
 * come to exist.
 */
/**
 * A `config` event says the settings file changed elsewhere. Rebuild the folder list
 * from the new config -- a folder somebody deleted must not sit there looking real --
 * and take the new etag with it, or the next Save collects a 412 over a change this
 * page has already been told about.
 *
 * ONLY the folder list. The event is about the whole file, but the acceptance is
 * about that list, and rebuilding the panel would throw away whatever is half-typed
 * in it. Returns true when the list actually changed, so the caller can decide
 * whether the person needs telling.
 */
export function syncFolders(panel, reply) {
  const cfg = (reply && reply.config) || {};
  const list = panel.querySelector('.folder-list');
  if (!list) return false;

  // Array.from: `children` is an HTMLCollection in a browser and has no .map.
  const ids = (n) => Array.from(n.children, (r) => (r.dataset && (r.dataset.id || r.dataset.path)) || '').join('|');
  const before = ids(list);

  panel.dataset.etag = reply && reply.etag ? reply.etag : panel.dataset.etag;
  panel.__base = cfg;
  if (reply && reply.accounts_found) panel.__accounts = reply.accounts_found;

  list.replaceChildren();
  for (const f of cfg.folders || []) list.append(folderRow(f, panel.__accounts));
  return ids(list) !== before;
}

/**
 * The bar a 412 raises (01.3 sec.3.8): the file changed under this panel.
 *
 * It does NOT close the panel. "The panel offers to re-read" is the spec's wording,
 * and the difference is somebody's typing: re-reading by force discards every edit
 * they made, silently, at the one moment they are most likely to have made several.
 *
 * `current` is the fresh config the 412 carried with it. Keeping it on the bar means
 * the re-read costs no second request -- and, more to the point, re-reads the version
 * the server actually refused us over, not whatever a later GET happens to return.
 */
export function showConflict(panel, current) {
  clearConflict(panel);
  const bar = el('div', 'settings-conflict');
  bar.setAttribute('role', 'alert');
  bar.dataset.etag = (current && current.etag) || '';
  bar.__current = current || null;

  const said = current
    ? 'the settings file changed elsewhere; your edits are still here'
    : 'the settings file changed elsewhere, and the server did not send the new one';
  bar.append(el('span', 'settings-conflict-text', said));

  const btn = el('button', 'settings-conflict-reload',
    current ? 'discard my edits and reload' : 'reopen the panel');
  btn.setAttribute('type', 'button');
  btn.dataset.action = 'reload-settings';
  bar.append(btn);

  panel.dataset.conflict = 'true';
  const head = panel.querySelector('.settings-head');
  if (head && head.after) head.after(bar); else panel.append(bar);
  return bar;
}

/** A fresh save starts from a clean slate: an old conflict bar is a stale statement. */
export function clearConflict(panel) {
  delete panel.dataset.conflict;
  const old = panel.querySelector('.settings-conflict');
  if (old && old.remove) old.remove();
}

/** The config a conflict bar is holding, or null when the 412 carried none. */
export function conflictCurrent(panel) {
  const bar = panel.querySelector('.settings-conflict');
  return bar ? bar.__current : null;
}

export function showErrors(panel, errors) {
  for (const slot of panel.querySelectorAll('.field-error')) slot.textContent = '';
  // Every control that can be named by an error, not only the text inputs: a toggle
  // left marked invalid from the previous save is a red field with no message.
  for (const n of panel.querySelectorAll('[data-path]')) delete n.dataset.invalid;

  let painted = 0;
  for (const err of errors || []) {
    const target = Array.from(panel.querySelectorAll('[data-path]'))
      .find((n) => n.dataset.path === err.field);
    if (!target) continue;
    target.dataset.invalid = 'true';
    const row = target.parentElement;
    const slot = row && row.querySelector ? row.querySelector('.field-error') : null;
    if (slot) slot.textContent = err.message || 'invalid value';
    painted += 1;
  }
  return painted;
}

/** Unmatched errors still have to be shown: a silent 422 looks like a save. */
export function unmatchedErrors(panel, errors) {
  const paths = new Set(Array.from(panel.querySelectorAll('[data-path]')).map((n) => n.dataset.path));
  return (errors || []).filter((e) => !paths.has(e.field));
}
