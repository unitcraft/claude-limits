// app.js — the page frame's behaviour (task T2.19): view switching, the live
// indicator, the freshness clock, and the refresh button.
//
// What this file does NOT do, on purpose: it never derives a number. Severity, the
// share of the window elapsed, the forecast and the reset captions all arrive ready
// from the backend, so that the SDL widget shows the same figures (01.1 §0). Row and
// account rendering arrive with T2.20; the containers stay empty here.
//
// Separate file rather than an inline <script>: the CSP refuses inline (01.1 §0).
'use strict';

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

async function fetchSnapshot() {
  try {
    const r = await fetch('/api/snapshot', { headers: { accept: 'application/json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    applySnapshot(await r.json());
  } catch (e) {
    // Keep the last good reading and say it is aging: a page that blanks on one
    // failed poll is less useful than one showing a number with its age.
    $('[data-field="placeholder"]').textContent =
      state.snapshot ? '' : `cannot reach the backend (${e.message})`;
  }
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

  tick();
  // Rendering of rows and account blocks lands in T2.20; the frame stops here.
  document.dispatchEvent(new CustomEvent('snapshot', { detail: snap }));
}

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

function main() {
  initViews();
  setLive('connecting');
  $('[data-action="refresh"]').addEventListener('click', (e) =>
    refresh(e.currentTarget));
  fetchSnapshot();
  connect();
  setInterval(tick, 1000);
}

document.addEventListener('DOMContentLoaded', main);
