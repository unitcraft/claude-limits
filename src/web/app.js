// app.js — the page's behaviour: view switching and the frame (T2.19), the list
// rendering (T2.20), live updates and the retry policy (T2.21).
//
// What this file does NOT do, on purpose: it derives no figure except the elapsed
// share, which 01.1 §2.6 explicitly assigns to the page. Severity, the forecast and
// the reset captions arrive ready from the backend, so the SDL widget shows the same
// numbers. The arithmetic it does own lives in format.js and is tested under node.
//
// Separate file rather than an inline <script>: the CSP refuses inline (01.1 §0).
import {
  isRetryable, retryDelay, retryAfterSeconds, setCaptionZone, getCaptionZone, captionTime, setViewOptions, MAX_RETRIES, refuseFor, orderRequest, configPut,
  footerRight, legendText, footerCounts, intervalOf, configUiOptions, getViewOptions } from './format.js';
import { createLive, silentTooLong, SILENCE_LIMIT_MS } from './live.js';
import { el, renderList, renderCards, layoutCells } from './render.js';
import { createReorder } from './reorder.js';
import { renderStats, RANGES } from './stats.js';
import { renderFolders } from './folders.js';
import { planNotifications } from './notify.js';
import {
  renderSettings, bodyOf, isEmptyDiff, showErrors, unmatchedErrors, probeSummary,
  showConflict, clearConflict, conflictCurrent, syncFolders, collectBrowser, saveBrowser,
  savedNote, checkFailed, permissionLine, selectChoice } from './settings.js';

const VIEWS = ['list', 'cards', 'stats'];
// The transport's own numbers (10 s degraded poll, 30 s reconnect, 90 s silence)
// live in live.js next to the machine that obeys them.

const state = {
  snapshot: null,
  fetchedAt: null,      // Date, from snapshot.fetched_at
  intervalSec: null,
  lastEvent: 0,
  live: null,           // the SSE transport (live.js); owns its timers and lastEvent
  tickTimer: null,
  apiVersion: null,
  order: null,          // optimistic account order, live only until the server agrees
  reorder: null,
  history: null,        // last /api/history reply
  statsRange: '7d',
  statsGroup: 'account',
  statsLoading: false,
  panel: null,          // the open settings panel, or null
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// ------------------------------------------------------------------- views --

function showView(name) {
  if (!VIEWS.includes(name)) name = 'list';
  $$('.view').forEach((el) => { el.hidden = el.dataset.view !== name; });
  $$('.views .icon-btn').forEach((b) => {
    b.setAttribute('aria-selected', String(b.dataset.view === name));
  });
  try { localStorage.setItem('view', name); } catch { /* private mode: not fatal */ }
  // Opened for the first time: the history has not been asked for yet. Fetching it
  // at load instead would spend a large query on a view most sessions never open.
  if (name === 'stats' && !state.history) loadHistory(state.statsRange);
}

/**
 * History is fetched when the statistics view is first opened and on every period
 * change — NOT on every snapshot. A week of samples is two orders of magnitude more
 * data than a snapshot, and it does not change meaningfully between two polls five
 * minutes apart (01.1 §6.1: the period drives the request).
 */
async function loadHistory(rangeKind, group = state.statsGroup) {
  if (state.statsLoading) return;
  state.statsLoading = true;
  try {
    const res = await apiGet(
      `/api/history?range=${encodeURIComponent(rangeKind)}&by=${encodeURIComponent(group)}`);
    state.history = await res.json();
    if (group === 'folder') renderFolders(state.history, rangeKind);
    else renderStats(state.history, rangeKind);
  } catch (e) {
    const view = document.getElementById('view-stats');
    // Only when there is nothing to keep: an old chart with a failed refresh behind
    // it is more use than an error where the chart was.
    if (view && !state.history) {
      view.replaceChildren(el('p', 'placeholder', `cannot load history (${e.message})`));
    }
  } finally {
    state.statsLoading = false;
  }
}

/**
 * Open the statistics for one account (01.1 §2.5).
 *
 * "A click on a row in the list or the cards opens the statistics (§6) with that
 * account scrolled to the top, and the period `7 d` (or `24 h` for a session). A
 * click on the account's name does the same."
 *
 * None of it existed: there was no click handler on a row or on an account name at
 * all -- all six listeners were the view switcher, the brand, the panel and the
 * refresh button. The row is the most obvious thing on the page to click, and it did
 * nothing.
 *
 * The period follows the row that was clicked, not the last one chosen: a session
 * limit spans five hours, and answering a click on it with a seven-day chart shows
 * one spike in a field of nothing.
 */
function openStatsFor(accountId, kind) {
  const want = kind === 'session' ? '24h' : '7d';
  if (state.statsRange !== want) {
    state.statsRange = want;
    try { localStorage.setItem('stats_range', want); } catch { /* private mode */ }
    loadHistory(want);
  }
  showView('stats');
  // After the view is shown, so the element exists and has a box to scroll into.
  const target = document.querySelector(`[data-account="${accountId}"]`);
  if (target && typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ block: 'start' });
  }
}

function setStatsRange(rangeKind) {
  if (!RANGES.includes(rangeKind) || rangeKind === state.statsRange) return;
  state.statsRange = rangeKind;
  try { localStorage.setItem('stats_range', rangeKind); } catch { /* private mode */ }
  loadHistory(rangeKind);
}

/**
 * Accounts or folders (01.1 sec.6.1). The two are different QUERIES, not two ways of
 * drawing one reply -- `by=folder` returns an occupancy journal and series split into
 * per-account segments, which `by=account` has no equivalent of -- so switching
 * re-fetches rather than re-rendering what is held.
 */
function setStatsGroup(group) {
  if ((group !== 'account' && group !== 'folder') || group === state.statsGroup) return;
  state.statsGroup = group;
  state.history = null;
  try { localStorage.setItem('stats_group', group); } catch { /* private mode */ }
  loadHistory(state.statsRange, group);
}

function initStats() {
  try { state.statsRange = localStorage.getItem('stats_range') || '7d'; } catch { /* ignore */ }
  if (!RANGES.includes(state.statsRange)) state.statsRange = '7d';
  try { state.statsGroup = localStorage.getItem('stats_group') || 'account'; } catch { /* ignore */ }
  if (state.statsGroup !== 'folder') state.statsGroup = 'account';
  // Delegated: the chips are rebuilt with the view on every render, so a listener
  // bound to them would be lost the first time the period changed.
  document.getElementById('view-stats').addEventListener('click', (e) => {
    const chip = e.target.closest && e.target.closest('.chip');
    if (!chip) return;
    if (chip.dataset.range) setStatsRange(chip.dataset.range);
    else if (chip.dataset.group) setStatsGroup(chip.dataset.group);
  });

  // 01.1 §2.5: a click on a row, or on an account's name, opens the statistics.
  //
  // Delegated for the same reason as the chips above -- rows are rebuilt on every
  // snapshot, and a listener bound to a row would be lost on the next poll. Bound to
  // BOTH the list and the cards, because the rule names both and a card is a row in a
  // different shape.
  for (const id of ['view-list', 'view-cards']) {
    const host = document.getElementById(id);
    if (!host) continue;
    host.addEventListener('click', (e) => {
      if (!e.target.closest) return;
      // A control inside a row keeps its own click: a drag handle or a future button
      // must not also open the statistics.
      if (e.target.closest('button, a, input, select, .toggle')) return;
      const el = e.target.closest('[data-account]');
      if (!el) return;
      openStatsFor(el.dataset.account, el.dataset.kind || '');
    });
  }
}

function initViews() {
  let saved = 'list';
  try { saved = localStorage.getItem('view') || 'list'; } catch { /* ignore */ }
  showView(saved);

  $$('.views .icon-btn').forEach((btn) => {
    btn.addEventListener('click', () => showView(btn.dataset.view));
  });

  // Arrow keys move between tabs, as a tablist must (01.1 §10).
  $('.views').addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    const current = VIEWS.indexOf(VIEWS.find((v) =>
      $(`.views .icon-btn[data-view="${v}"]`).getAttribute('aria-selected') === 'true'));
    const next = (current + (e.key === 'ArrowRight' ? 1 : VIEWS.length - 1)) % VIEWS.length;
    showView(VIEWS[next]);
    $(`.views .icon-btn[data-view="${VIEWS[next]}"]`).focus();
    e.preventDefault();
  });

  $('.brand').addEventListener('click', (e) => {
    e.preventDefault();
    showView('list');
    window.scrollTo({ top: 0 });
  });
}

// -------------------------------------------------------------- liveness ----

function setLive(mode) {          // 'live' | 'polling' | 'connecting'
  const el = $('.live');
  el.dataset.state = mode;
  el.querySelector('.live-label').textContent = mode;
}

/** Two units, larger first — the same rule the backend and the widget use (01.1 §0). */
function ago(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ${m % 60}m ago` : `${Math.floor(h / 24)}d ${h % 24}h ago`;
}

function tick() {
  if (!state.fetchedAt) return;
  const age = Date.now() - state.fetchedAt.getTime();
  $('[data-field="fetched-ago"]').textContent = ago(age);
  // Older than twice the interval: the backend answers, the data does not follow.
  const stale = state.intervalSec ? age > state.intervalSec * 2000 : false;
  $('.fetched').dataset.stale = String(stale);

  if (state.live && silentTooLong(state.live, Date.now())) fetchSnapshot();
}

// -------------------------------------------------------------- transport ---

/**
 * A GET with the retry policy of 01.3 §5: up to three attempts, jitter, and
 * `Retry-After` ahead of any computed wait. Reads only — writes are retried by a
 * person pressing the button again, never by us, because a retried write can mean
 * a second action rather than a second look.
 */
/**
 * A request with no answer is a failed request. Without a limit a fetch waits for as
 * long as its socket lives: the owner's tab sat on "waiting for the first snapshot"
 * with a healthy server and never retried (2026-10-03). Aborted, it is a network
 * failure like any other and takes the retry below.
 */
const REQUEST_TIMEOUT_MS = 15_000;

async function apiGet(path) {
  let lastErr = null;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    let status = 0, res = null;
    const abort = new AbortController();
    const limit = setTimeout(() => abort.abort(), REQUEST_TIMEOUT_MS);
    try {
      res = await fetch(path, { headers: { accept: 'application/json' }, signal: abort.signal });
      status = res.status;
      if (res.ok) return res;
      lastErr = new Error(`HTTP ${status}`);
    } catch (e) {
      lastErr = e;                       // network failure or timeout: status stays 0
    } finally {
      clearTimeout(limit);
    }
    if (attempt === MAX_RETRIES || !isRetryable('GET', status)) break;
    const after = res && res.headers.get('Retry-After');
    await sleep(retryDelay(attempt, retryAfterSeconds(after)));
  }
  throw lastErr || new Error('request failed');
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchSnapshot() {
  try {
    applySnapshot(await (await apiGet('/api/snapshot')).json());
  } catch (e) {
    // Keep the last good reading and say it is aging: a page that blanks on one
    // failed poll is less useful than one showing a number with its age.
    $('[data-field="placeholder"]').textContent =
      state.snapshot ? '' : `cannot reach the backend (${e.message})`;
  }
}

/**
 * The binary serves both the API and this page, so a restarted backend can be a
 * NEWER one whose responses this script does not understand. `api_version` is read
 * once at load and compared on every `notice`; a change asks for a reload instead of
 * rendering a shape it was not written for (01.3 §5).
 */
async function checkApiVersion() {
  try {
    const health = await (await apiGet('/api/health')).json();
    if (state.apiVersion == null) { state.apiVersion = health.api_version; return; }
    if (health.api_version !== state.apiVersion) askReload();
  } catch { /* health is not worth a visible error: the snapshot path already reports */ }
}

function askReload() {
  if ($('.reload-note')) return;
  const note = el('p', 'reload-note', 'the backend was updated — reload the page');
  note.setAttribute('role', 'status');
  $('main').prepend(note);
}

/**
 * A short message that says something failed and then gets out of the way (01.1
 * §4.1 names exactly one: `could not save order`).
 *
 * `role="status"` and not `alert`: a screen reader should finish the sentence it is
 * on rather than be interrupted by a message about a card that has already moved
 * back on its own.
 */
function toast(text) {
  const t = el('div', 'toast', text);
  t.setAttribute('role', 'status');
  document.body.append(t);
  setTimeout(() => t.remove(), 4000);
}

/**
 * Persist the account order (01.3 §3.8): read the current `etag`, then a partial
 * `PUT` carrying nothing but `ui.accounts_order`.
 *
 * The `etag` is re-read immediately before the write rather than remembered from the
 * last poll. The config file is editable by hand and by another tab, and an `If-Match`
 * from five minutes ago would collect a `412` on a file that changed for reasons
 * having nothing to do with this order — turning a valid drag into a failure the
 * person cannot explain. A race still exists in the milliseconds between the GET and
 * the PUT, and that is precisely what `412` is for.
 *
 * NOT retried, on purpose. `isRetryable` refuses non-safe methods (01.3 §5): a
 * repeated write can mean a second action rather than a second look, and after a
 * successful PUT the repeat would get a `412` anyway (§3.8, idempotency by version).
 */
async function saveOrder(emails) {
  // Keys only: an account without one is drawn under its position (`?2`), and a
  // position saved into the order names nothing after a reload.
  emails = emails.filter((k) => k && !k.startsWith('?'));
  const current = await apiGet('/api/config');
  const etag = current.headers.get('ETag');
  const res = await fetch('/api/config', orderRequest(etag, emails));
  if (!res.ok) {
    // The config moved under us: show what the server actually has rather than
    // leaving the page on an order nobody stored.
    if (res.status === 412 || res.status === 428) { state.order = null; fetchSnapshot(); }
    throw new Error(`config PUT ${res.status}`);
  }
  state.order = emails;
}

function applySnapshot(snap) {
  state.snapshot = snap;
  if (state.live) state.live.lastEvent = Date.now();
  state.fetchedAt = snap.fetched_at ? new Date(snap.fetched_at) : new Date();
  state.intervalSec = intervalOf(snap) ?? state.intervalSec;

  $('[data-field="fetched-at"]').textContent = captionTime(state.fetchedAt);

  const accounts = snap.accounts || [];
  state.tz = snap.tz || state.tz;
  // The one place the backend's zone reaches the captions. Assigning state.tz and
  // stopping there is what the page did until 2026-09-09, and every reset time was
  // drawn in the viewer's zone instead of the backend's.
  setCaptionZone(state.tz);
  $('[data-field="counts"]').textContent = footerCounts(accounts);

  // The legend describes what this snapshot actually draws (01.1 sec.1.2).
  const limits = snap.limits || [];
  // What is drawn, not what is configured: render.js draws the strip whenever a
  // limit carries `resets_at` (it computes the share itself, 01.1 sec.2.6) and the
  // ghost whenever a forecast came with it. Reading the same conditions here keeps
  // the legend honest -- a legend built from the config would explain a mark that
  // this particular snapshot does not show.
  const legend = legendText({
    timeBar: getViewOptions().time_bar && limits.some((l) => l.resets_at),
    forecast: limits.some((l) => l.forecast),
  });
  $('[data-field="legend"]').textContent = legend;
  $('[data-field="legend-sep"]').hidden = !legend;
  if (state.intervalSec) {
    $('[data-field="interval"]').textContent =
      footerRight(state.intervalSec, snap.next_poll_at);
  }
  $('[data-field="placeholder"]').textContent = accounts.length ? '' : 'no logins found';

  renderList(accounts, snap.limits, state.order);
  // The cards view is rendered even while hidden: switching views must not wait for
  // the next poll, which is five minutes away by default.
  renderCards(accounts, snap.limits, state.order);
  tick();
  notifyThresholds(snap);
  document.dispatchEvent(new CustomEvent('snapshot', { detail: snap }));
}

/**
 * Task #9: show the notifications the snapshot owes. The rules live in notify.js; this
 * only reads and writes localStorage (`notify`, `notified`) and raises the browser's
 * Notification. Every step may fail quietly -- a missing permission or a private-mode
 * store must never break drawing the page.
 */
function notifyThresholds(snap) {
  let enabled = false;
  let told = {};
  try {
    enabled = localStorage.getItem('notify') === 'true';
    told = JSON.parse(localStorage.getItem('notified') || '{}') || {};
  } catch { /* unreadable: start from nothing */ }
  const granted = typeof Notification !== 'undefined' && Notification.permission === 'granted';
  const names = {};
  for (const a of snap.accounts || []) names[a.id] = a.email || a.display_name || a.id;
  const plan = planNotifications(snap.limits, told, { enabled: enabled && granted, names });
  try { localStorage.setItem('notified', JSON.stringify(plan.told)); } catch { /* private mode */ }
  for (const n of plan.fire) {
    try { new Notification(n.title, { body: n.body, tag: n.key }); } catch { /* ignore */ }
  }
}

async function askNotifyPermission(btn) {
  if (typeof Notification === 'undefined') return;
  try { await Notification.requestPermission(); } catch { /* ignore */ }
  const note = btn.parentElement && btn.parentElement.querySelector('.notify-state');
  if (note) note.textContent = permissionLine();
}

window.addEventListener('resize', layoutCells);


function connect() {
  state.live = createLive({
    openStream: (url) => new EventSource(url),
    now: () => Date.now(),
    timers: {
      set: (fn, ms) => setTimeout(fn, ms),
      clear: (id) => clearTimeout(id),
      setEvery: (fn, ms) => setInterval(fn, ms),
      clearEvery: (id) => clearInterval(id),
    },
    setLive,
    poll: fetchSnapshot,
    onEvent: handleEvent,
  });
  state.live.start();
}

/**
 * What each frame MEANS is the page's business; live.js only guarantees it arrived
 * and hands the payload over unparsed.
 */
function handleEvent(name, data) {
  if (name === 'snapshot') {
    try { applySnapshot(JSON.parse(data)); } catch { /* malformed frame: keep the old one */ }
    return;
  }
  // A restarted backend announces itself; the version check decides whether this
  // script can still read what the new one sends (01.3 sec.5).
  if (name === 'notice') {
    try {
      if (JSON.parse(data).level === 'reload') { askReload(); return; }
    } catch { /* an unreadable notice is still a sign of life, nothing more */ }
    checkApiVersion();
    return;
  }
  // Settings changed in another tab: the config is the backend's, not this tab's.
  // The optimistic order goes with it -- keeping it would let this tab override an
  // order somebody else has just saved, and keep overriding it on every poll.
  if (name === 'config') {
    state.order = null;
    // An open panel is now on a stale etag with stale folder rows, and the folder
    // somebody removed must not sit there looking real. Refresh THAT -- closing the
    // panel would discard whatever is half-typed in it, and unlike a 412 the person
    // has not even asked to save yet.
    if (state.panel) refreshOpenPanel();
    fetchSnapshot();
  }
  // 'ping' says only that the connection is alive, which live.js has already recorded;
  // 'bye' ends the stream, and live.js has already turned to polling.
}

// --------------------------------------------------------------- settings ---

/**
 * Open the panel on a FRESH `GET /api/config` every time (01.1 sec.5). The etag it
 * carries is the one the save sends back as `If-Match`, so a panel built from a
 * remembered reply would collect a 412 for a file that changed while it sat closed.
 */
/**
 * A `config` event arrived while the panel is open: re-read the file and rebuild the
 * folder list from it, keeping the rest of the panel and its edits. If the list
 * actually changed under somebody, say so -- a row vanishing on its own is alarming
 * in a way an explained one is not.
 */
async function refreshOpenPanel() {
  const panel = state.panel;
  if (!panel) return;
  let reply;
  try {
    reply = await (await apiGet('/api/config')).json();
  } catch { return; }        // the panel keeps what it has; the next event tries again
  if (state.panel !== panel) return;               // closed or replaced while we asked
  if (syncFolders(panel, reply)) showConflict(panel, reply);
}

/**
 * The person accepted the offer a 412 made. Rebuild from the `current` the error
 * carried rather than issuing another GET: that is the version the server refused us
 * over, and a fresh GET can already have moved past it.
 */
function reloadSettings() {
  const old = state.panel;
  if (!old) return;
  const current = conflictCurrent(old);
  if (!current) { closeSettings(); openSettings(); return; }
  const panel = renderSettings(current);
  panel.addEventListener('click', onPanelClick);
  old.replaceWith(panel);
  state.panel = panel;
}

async function openSettings() {
  if (state.panel) { closeSettings(); return; }
  let reply;
  try {
    reply = await (await apiGet('/api/config')).json();
  } catch (e) {
    toast(`cannot read the settings (${e.message})`);
    return;
  }
  const panel = renderSettings(reply);
  panel.addEventListener('click', onPanelClick);
  document.body.append(panel);
  state.panel = panel;
  const firstInput = panel.querySelector('.input');
  if (firstInput && firstInput.focus) firstInput.focus();
}

function closeSettings() {
  if (!state.panel) return;
  state.panel.remove();
  state.panel = null;
}

function onPanelClick(e) {
  const target = e.target && e.target.closest ? e.target.closest('button') : e.target;
  if (!target || !target.dataset) return;
  const action = target.dataset.action;

  const option = target.closest && target.closest('.choice-option');
  if (option) {
    selectChoice(option);
    return;
  }

  // A toggle and a day button carry their state in ARIA, which is also what the
  // collector reads: one place, so a control cannot look on and read off.
  if (target.className === 'toggle' && !target.disabled) {
    target.setAttribute('aria-checked', String(target.getAttribute('aria-checked') !== 'true'));
    return;
  }
  if (target.className === 'day') {
    target.setAttribute('aria-pressed', String(target.getAttribute('aria-pressed') !== 'true'));
    return;
  }
  if (action === 'cancel') { closeSettings(); return; }
  if (action === 'drop-folder') {
    const row = target.parentElement;
    if (row) row.remove();
    return;
  }
  if (action === 'reload-settings') { reloadSettings(); return; }
  if (action === 'probe') { probeFolder(); return; }
  if (action === 'notify-permission') { askNotifyPermission(target); return; }
  if (action === 'save') { saveSettings(); }
}

/**
 * `POST /api/folders/probe` (01.3 sec.3.9): say what is in a path BEFORE it is added.
 * The path goes in the BODY, never in the URL -- a path in a query string ends up in
 * every log and proxy on the way (01.3 sec.0).
 */
async function probeFolder() {
  const panel = state.panel;
  if (!panel) return;
  const input = Array.from(panel.querySelectorAll('.input'))
    .find((n) => n.dataset.path === 'folders.new');
  const note = panel.querySelector('.probe-note');
  const path = input && input.value ? input.value.trim() : '';
  if (!path) { if (note) note.textContent = 'type a path first'; return; }
  const say = (text, tone) => {
    if (!note) return;
    note.textContent = text;
    if (tone) note.dataset.tone = tone; else delete note.dataset.tone;
  };
  say('checking...', null);
  try {
    const res = await fetch('/api/folders/probe', {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ path }),
    });
    let found = null;
    try { found = await res.json(); } catch { /* a refusal need not be JSON */ }
    // A FAILED CHECK IS AN ERROR, in red, and says what the server said -- not the
    // JSON parser's complaint about a plain-text 500, which is what a person saw on
    // the first stand (2026-10-02).
    if (!res.ok || !found) {
      say(checkFailed(res.status, found), 'critical');
      return;
    }
    const line = probeSummary(found);
    say(line.text, line.tone);
  } catch (err) {
    say(`could not check: ${err.message}`, 'critical');
  }
}

/**
 * One partial PUT with `If-Match` (01.3 sec.3.8), and the three answers that matter:
 * 200 closes the panel, 422 paints the fields the server names, 412 says the file
 * moved and offers to re-read it rather than overwriting what someone else saved.
 */
async function saveSettings() {
  const panel = state.panel;
  if (!panel) return;

  // THE BROWSER HALF FIRST, and unconditionally. These settings never travel to the
  // backend, so they must not depend on whether the config diff turns out to be
  // empty -- which is exactly how they were being lost: toggling only `countdown`
  // produced an empty body, the early return below closed the panel, and nothing
  // ever wrote localStorage. The switch moved and nothing happened.
  const browserPrefs = collectBrowser(panel);
  saveBrowser(browserPrefs);
  if (browserPrefs.view) showView(browserPrefs.view);
  if (browserPrefs.bar_style) {
    document.body.dataset.barStyle = browserPrefs.bar_style === 'blocks' ? 'cells' : '';
    layoutCells();
  }

  const body = bodyOf(panel);
  if (isEmptyDiff(body)) { closeSettings(); return; }
  clearConflict(panel);        // a bar from the previous attempt is a stale statement

  let res;
  try {
    res = await fetch('/api/config', configPut(panel.dataset.etag, body));
  } catch (e) {
    toast(`could not save (${e.message})`);
    return;
  }

  if (res.ok) {
    let reply = null;
    try { reply = await res.json(); } catch { /* a 200 with no body is still a save */ }
    closeSettings();
    if (body.ui) {
      setViewOptions(body.ui);
      if (state.snapshot) applySnapshot(state.snapshot);
    }
    const note = savedNote(reply);
    if (note) toast(note);
    fetchSnapshot();
    return;
  }
  let problem = {};
  try { problem = await res.json(); } catch { /* an error with no body is still an error */ }

  if (res.status === 422 || res.status === 400) {
    const errors = problem.errors || [];
    showErrors(panel, errors);
    const left = unmatchedErrors(panel, errors);
    // Never a silent failure: an error the panel cannot place still has to be read,
    // or a refused save looks exactly like a successful one.
    if (!errors.length || left.length) {
      toast(left.length ? left.map((x) => `${x.field}: ${x.message}`).join('; ')
        : (problem.detail || `save refused (${res.status})`));
    }
    return;
  }
  // 01.3 sec.3.8: the body carries `current`, and the panel OFFERS to re-read. It
  // does not re-read by force -- that would discard everything typed since the panel
  // opened, at the one moment somebody is most likely to have typed a lot.
  if (res.status === 412 || res.status === 428) {
    showConflict(panel, problem.current || null);
    return;
  }
  // `title` before the bare status: a 500 `config_readonly` carries no detail (the path
  // stays in the log), and "Settings file is read-only" is the sentence a person needs.
  toast(problem.detail || problem.title || `save refused (${res.status})`);
}

// ---------------------------------------------------------------- refresh ---

async function refresh(btn) {
  btn.dataset.spinning = 'true';
  try {
    const r = await fetch('/api/snapshot/refresh', { method: 'POST' });
    // The floor is not advice: the endpoint answers 429 to eager polling, which is
    // why the backend refuses too (plan 01 sec.0). Say until when, and mean it.
    // How long is refuseFor's decision -- it is tested, and this is not.
    const wait = refuseFor(r.status, r.headers.get('Retry-After'));
    if (wait > 0) {
      const until = new Date(Date.now() + wait * 1000);
      btn.disabled = true;
      // The backend's zone, like every other caption on this page: the person
      // reading it and the machine being waited on are not always in the same one.
      const zone = getCaptionZone();
      const opts = { hour: '2-digit', minute: '2-digit', hour12: false };
      btn.title = `server asks to wait until ${
        until.toLocaleTimeString('en', zone ? { ...opts, timeZone: zone } : opts)}`;
      setTimeout(() => { btn.disabled = false; btn.title = 'poll now'; }, wait * 1000);
    }
    // 202: the snapshot arrives over SSE; nothing to do here.
  } catch (e) {
    // WITHOUT THIS, A REJECTED FETCH SAID NOTHING. `try/finally` with no `catch`
    // stopped the spinner and left the person looking at an unchanged page: the
    // request never left, and the page behaved exactly as though it had succeeded
    // and there was simply no news. Four of the five handlers here already had a
    // catch, which is what made the fifth look finished.
    //
    // api.md:26 -- "no silent outcomes".
    toast(`could not reach the backend (${e.message})`);
  } finally {
    btn.dataset.spinning = 'false';
  }
}

// ------------------------------------------------------------------- start --

/**
 * A hidden tab stops its timers and catches up on return (01.1 §9). Without this a
 * page left open in a background tab keeps a per-second timer running all day for
 * nobody, and on a laptop that is measurable.
 */
function initVisibility() {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      clearInterval(state.tickTimer);
      state.tickTimer = null;
    } else if (!state.tickTimer) {
      state.tickTimer = setInterval(tick, 1000);
      tick();                    // catch up at once rather than a second later
      if (!state.live || Date.now() - state.live.lastEvent > SILENCE_LIMIT_MS) fetchSnapshot();
    }
  });
}

function main() {
  initStats();          // before initViews: opening on `stats` must find the period
  initViews();
  initVisibility();
  state.reorder = createReorder({
    container: document.getElementById('view-cards'),
    commit: saveOrder,
    toast,
  });
  state.reorder.attach();
  $('[data-action="refresh"]').addEventListener('click', (e) =>
    refresh(e.currentTarget));
  $('[data-action="settings"]').addEventListener('click', openSettings);
  // Esc closes the panel wherever the focus is: a popover that can only be dismissed
  // by finding its Cancel button is a trap for keyboard use (01.1 sec.10).
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.panel) closeSettings();
  });
  checkApiVersion();
  // The snapshot contract intentionally does not contain the full config. Fetch the
  // live UI flags over the real config endpoint instead of relying on a synthetic
  // `snapshot.config` property that production never sends.
  apiGet('/api/config').then((r) => r.json()).then((r) => {
    setViewOptions(configUiOptions(r));
    let style = 'rounded';
    try { style = localStorage.getItem('bar_style') || style; } catch { /* ignore */ }
    document.body.dataset.barStyle = style === 'blocks' ? 'cells' : '';
    if (state.snapshot) applySnapshot(state.snapshot);
  }).catch(() => {});
  fetchSnapshot();
  connect();
  state.tickTimer = setInterval(tick, 1000);
}

document.addEventListener('DOMContentLoaded', main);
