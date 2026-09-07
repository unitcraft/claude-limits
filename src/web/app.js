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
  elapsedShare, cellGeometry, formatReset, rowLabel, sortLimits, severityOf,
  isRetryable, retryDelay, MAX_RETRIES,
} from './format.js';

const VIEWS = ['list', 'cards', 'stats'];
const POLL_WHEN_DEGRADED_MS = 10_000;   // no SSE: ask for a snapshot this often
const SSE_RETRY_MS = 30_000;            // and try to reconnect this often
const SILENCE_LIMIT_MS = 90_000;        // SSE open but silent: ask anyway (01.1 §1.1)

const state = {
  snapshot: null,
  fetchedAt: null,      // Date, from snapshot.fetched_at
  intervalSec: null,
  lastEvent: 0,
  es: null,
  pollTimer: null,
  tickTimer: null,
  apiVersion: null,
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

  if (state.es && state.es.readyState === EventSource.OPEN
      && Date.now() - state.lastEvent > SILENCE_LIMIT_MS) {
    fetchSnapshot();
  }
}

// -------------------------------------------------------------- transport ---

/**
 * A GET with the retry policy of 01.3 §5: up to three attempts, jitter, and
 * `Retry-After` ahead of any computed wait. Reads only — writes are retried by a
 * person pressing the button again, never by us, because a retried write can mean
 * a second action rather than a second look.
 */
async function apiGet(path) {
  let lastErr = null;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    let status = 0, res = null;
    try {
      res = await fetch(path, { headers: { accept: 'application/json' } });
      status = res.status;
      if (res.ok) return res;
      lastErr = new Error(`HTTP ${status}`);
    } catch (e) {
      lastErr = e;                       // network failure: status stays 0
    }
    if (attempt === MAX_RETRIES || !isRetryable('GET', status)) break;
    const after = res && res.headers.get('Retry-After');
    await sleep(retryDelay(attempt, after ? Number(after) : null));
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

function applySnapshot(snap) {
  state.snapshot = snap;
  state.lastEvent = Date.now();
  state.fetchedAt = snap.fetched_at ? new Date(snap.fetched_at) : new Date();
  state.intervalSec = snap.interval_sec ?? state.intervalSec;

  $('[data-field="fetched-at"]').textContent =
    state.fetchedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const accounts = snap.accounts || [];
  const dirs = accounts.reduce((n, a) => n + (a.dirs ? a.dirs.length : 0), 0);
  $('[data-field="counts"]').textContent =
    `${accounts.length} login${accounts.length === 1 ? '' : 's'} in ${dirs} director${dirs === 1 ? 'y' : 'ies'}`;
  if (state.intervalSec) {
    $('[data-field="interval"]').textContent = `polling every ${state.intervalSec} s`;
  }
  $('[data-field="placeholder"]').textContent = accounts.length ? '' : 'no logins found';

  renderList(accounts);
  tick();
  document.dispatchEvent(new CustomEvent('snapshot', { detail: snap }));
}

// ------------------------------------------------------------- rendering ----

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/** One limit window: name, bar, percent, reset caption (01.1 §2). */
function renderRow(limit) {
  const sev = severityOf(limit);
  const row = el('div', 'row');
  row.dataset.severity = sev;

  row.append(el('span', 'row-name', rowLabel(limit)));

  const bars = el('div', 'row-bars');
  const bar = el('div', 'bar');
  const fill = el('div', 'bar-fill');
  fill.style.width = `${Math.max(0, Math.min(100, limit.percent ?? 0))}%`;
  bar.append(fill);
  if (limit.forecast_percent_at_reset != null && limit.forecast_percent_at_reset > limit.percent) {
    const ghost = el('div', 'bar-ghost');
    ghost.style.left = `${limit.percent}%`;
    ghost.style.width = `${Math.min(100, limit.forecast_percent_at_reset) - limit.percent}%`;
    bar.append(ghost);
  }
  bars.append(bar);

  // The time strip is computed here, not sent: only resets_at and kind are needed
  // (01.1 §2.6). Reading: fill left of the strip's end means a pace below the window.
  if (limit.resets_at) {
    const strip = el('div', 'timebar');
    const share = elapsedShare(limit.kind, limit.resets_at);
    const done = el('div', 'timebar-fill');
    done.style.width = `${(share * 100).toFixed(1)}%`;
    strip.append(done);
    strip.title = `time elapsed ${Math.round(share * 100)}%`;
    bars.append(strip);
  }
  row.append(bars);

  const pct = el('span', 'row-pct', limit.percent == null ? '—' : `${Math.round(limit.percent)}%`);
  row.append(pct);

  const reset = el('div', 'row-reset');
  reset.append(el('span', 'reset-when', formatReset(limit.resets_at)));
  if (limit.forecast_label) reset.append(el('span', 'reset-forecast', limit.forecast_label));
  row.append(reset);
  return row;
}

/** One account: header with its state, then its windows in the fixed order. */
function renderAccount(acc) {
  const block = el('section', 'account');
  block.dataset.state = acc.state || 'ok';

  const head = el('header', 'account-head');
  head.append(el('span', 'account-email', acc.email || 'unknown account'));
  if (acc.org) head.append(el('span', 'account-org', acc.org));
  if (acc.dirs && acc.dirs.length) head.append(el('span', 'account-dirs', acc.dirs.join(', ')));
  block.append(head);

  // A state other than ok replaces the rows with its reason. Never an empty block:
  // an account with nothing under it is indistinguishable from a broken renderer.
  if (acc.state && acc.state !== 'ok') {
    block.append(el('p', 'account-note', acc.message || acc.state));
    return block;
  }
  for (const limit of sortLimits(acc.limits || [])) block.append(renderRow(limit));
  return block;
}

/**
 * Point updates, not a redraw (01.1 §9). The account block is keyed by e-mail: an
 * existing one is replaced in place, a new one is inserted at its position, a
 * vanished one is removed. Redrawing the list wholesale would drop the hover, the
 * focus and any open tooltip on every poll — five times a minute in the degraded
 * mode, which is exactly when the user is watching closely.
 */
function renderList(accounts) {
  const view = document.getElementById('view-list');
  const have = new Map(Array.from(view.children).map((n) => [n.dataset.email, n]));
  const seen = new Set();

  accounts.forEach((acc, i) => {
    const key = (acc.email || `?${i}`).toLowerCase();
    seen.add(key);
    const fresh = renderAccount(acc);
    fresh.dataset.email = key;
    const old = have.get(key);
    if (old) old.replaceWith(fresh);
    else view.insertBefore(fresh, view.children[i] || null);
  });

  for (const [key, node] of have) if (!seen.has(key)) node.remove();
  layoutCells();
}

/**
 * The "cells" bar style needs pixel widths, so it is applied after layout and again
 * on resize (01.1 §2.2). Whole cells only — the geometry is in format.js and tested.
 */
function layoutCells() {
  if (document.body.dataset.barStyle !== 'cells') return;
  for (const bar of $$('.bar')) {
    const fill = bar.querySelector('.bar-fill');
    const pct = parseFloat(fill.style.width) || 0;
    const g = cellGeometry(bar.parentElement.clientWidth, pct);
    bar.style.width = `${g.barWidth}px`;
    fill.style.width = `${g.fillWidth}px`;
    bar.title = `${Math.round(pct)}% · ${g.filledCells} of ${g.cells} cells`;
  }
}
window.addEventListener('resize', layoutCells);

function connect() {
  try {
    state.es = new EventSource('/api/events');
  } catch {
    setLive('polling');
    return;
  }
  state.es.addEventListener('open', () => {
    setLive('live');
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  });
  state.es.addEventListener('snapshot', (e) => {
    state.lastEvent = Date.now();
    try { applySnapshot(JSON.parse(e.data)); } catch { /* malformed frame: keep the old one */ }
  });
  state.es.addEventListener('ping', () => { state.lastEvent = Date.now(); });
  // A restarted backend announces itself; the version check decides whether this
  // script can still read what the new one sends (01.3 §5).
  state.es.addEventListener('notice', (e) => {
    state.lastEvent = Date.now();
    try {
      if (JSON.parse(e.data).level === 'reload') { askReload(); return; }
    } catch { /* an unreadable notice is still a sign of life, nothing more */ }
    checkApiVersion();
  });
  // Settings changed in another tab: the config is the backend's, not this tab's.
  state.es.addEventListener('config', () => {
    state.lastEvent = Date.now();
    fetchSnapshot();
  });
  state.es.addEventListener('error', () => {
    setLive('polling');
    if (!state.pollTimer) state.pollTimer = setInterval(fetchSnapshot, POLL_WHEN_DEGRADED_MS);
    setTimeout(() => {
      if (!state.es || state.es.readyState === EventSource.CLOSED) connect();
    }, SSE_RETRY_MS);
  });
}

// ---------------------------------------------------------------- refresh ---

async function refresh(btn) {
  btn.dataset.spinning = 'true';
  try {
    const r = await fetch('/api/snapshot/refresh', { method: 'POST' });
    if (r.status === 429) {
      // The floor is not advice: the endpoint answers 429 to eager polling, which
      // is why the backend refuses too (plan 01 §0). Say until when, and mean it.
      const wait = Number(r.headers.get('Retry-After') || 60);
      const until = new Date(Date.now() + wait * 1000);
      btn.disabled = true;
      btn.title = `server asks to wait until ${until.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      setTimeout(() => { btn.disabled = false; btn.title = 'poll now'; }, wait * 1000);
    }
    // 202: the snapshot arrives over SSE; nothing to do here.
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
      if (Date.now() - state.lastEvent > SILENCE_LIMIT_MS) fetchSnapshot();
    }
  });
}

function main() {
  initViews();
  initVisibility();
  setLive('connecting');
  $('[data-action="refresh"]').addEventListener('click', (e) =>
    refresh(e.currentTarget));
  checkApiVersion();
  fetchSnapshot();
  connect();
  state.tickTimer = setInterval(tick, 1000);
}

document.addEventListener('DOMContentLoaded', main);
