// stats.js — the statistics view, by account (task T2.23).
//
// Reads a `/api/history` reply and builds the filter row, the four tiles and one card
// per account with its three charts. All the coordinate arithmetic lives in chart.js
// and is tested separately; this file is the shape of the DOM around it.
//
// Everything here follows subplan 01.1 §6. SVG is built element by element rather
// than by setting innerHTML: the CSP forbids nothing here, but a chart assembled
// from a string is a chart nobody can test without parsing HTML back out of it.
import {
  BOX, yOf, linePath, areaPath, bandRect, resetLines, inferredResets,
  xTicks, nearestPoint, seriesByAccount, columnsOf,
} from './chart.js';
import { formatDuration } from './format.js';
import { el } from './render.js';

const NS = 'http://www.w3.org/2000/svg';

/** An SVG element with attributes — the same shape as `el`, for the other namespace. */
export function svg(tag, attrs = {}) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, String(v));
  return n;
}

export const RANGES = ['24h', '7d', '30d'];

/** Model colours are fixed BY NAME in order of appearance (01.1 §8), not by rank. */
export function modelColors(series) {
  const names = [];
  for (const s of series || []) {
    if (s.kind === 'weekly_scoped' && s.model && !names.includes(s.model)) names.push(s.model);
  }
  const out = new Map();
  names.sort().forEach((name, i) => out.set(name, `var(--series-${(i % 3) + 1})`));
  return out;
}

// ---------------------------------------------------------------- tiles -----

/**
 * The four tiles of §6.2. Each takes its number from `tiles` and says who and when
 * underneath; a tile with nothing to show says `—` and `no history yet` rather than
 * `0`, because zero locked hours and no data at all are different facts.
 */
export function renderTiles(tiles) {
  const box = el('div', 'tiles');
  const t = tiles || {};

  const tile = (label, value, note, tone) => {
    const n = el('div', 'tile');
    n.append(el('div', 'tile-label', label));
    const v = el('div', 'tile-value', value);
    if (tone) v.dataset.tone = tone;
    n.append(v);
    n.append(el('div', 'tile-note', note));
    return n;
  };

  const locked = t.locked;
  box.append(tile('Locked this week',
    locked && locked.seconds ? formatDuration(locked.seconds * 1000) : (locked ? '0m' : '—'),
    locked && locked.seconds
      ? `${locked.email} · ${(locked.when || []).join(', ')}`
      : (locked ? 'nobody was locked' : 'no history yet'),
    locked && locked.seconds ? 'critical' : null));

  const peak = t.peak_session;
  box.append(tile('Peak session',
    peak ? `${peak.percent}%` : '—',
    peak ? `${peak.email}${peak.times > 1 ? ` · ${peak.times} times` : ''}` : 'no history yet',
    peak && peak.percent >= 100 ? 'critical' : null));

  const avg = t.avg_session;
  box.append(tile('Avg session window',
    avg ? `${avg.percent}%` : '—',
    avg ? `across ${avg.accounts} account${avg.accounts === 1 ? '' : 's'}` : 'no history yet'));

  const pace = t.pace;
  box.append(tile('Pace · working hours',
    pace ? `${pace.rate_per_hour}/h` : '—',
    pace ? (pace.label || `${pace.email} · ${pace.model || 'all models'}`) : 'no history yet',
    pace && pace.label ? 'warning' : null));

  return box;
}

// ---------------------------------------------------------------- charts ----

/**
 * One chart. The order of the layers is the order they must be painted in: bands
 * first so the line is never hidden behind a lock, the line last so a reset vertical
 * cannot cut through it.
 */
export function renderChart(seriesList, range, opts = {}) {
  const colors = opts.colors || new Map();
  const node = svg('svg', {
    viewBox: `0 0 ${BOX.w} ${BOX.h}`,
    class: 'chart',
    preserveAspectRatio: 'none',
    role: 'img',
    'aria-label': opts.label || 'usage over time',
  });

  for (const pct of [0, 50, 100]) {
    node.append(svg('line', {
      class: 'grid', x1: 0, x2: BOX.w, y1: yOf(pct), y2: yOf(pct),
    }));
  }

  const first = seriesList[0];
  if (first) {
    for (const lock of first.locks || []) {
      const r = bandRect(lock, range);
      if (r) node.append(svg('rect', { class: 'band-lock', ...r }));
    }
    for (const gap of first.gaps || []) {
      const r = bandRect(gap, range);
      if (r) {
        const rect = svg('rect', { class: 'band-gap', ...r });
        // A <title> child is the SVG tooltip: the band says WHY it is there, or an
        // amber stripe is just an unexplained hole in the week.
        const why = svg('title', {});
        why.textContent = `no samples: ${cause(gap)}`;
        rect.append(why);
        node.append(rect);
      }
    }
  }

  // A single series is filled; several are lines only, or the fills would hide each
  // other and the reader could not tell which model is which (§6.4).
  const single = seriesList.length === 1;
  for (const s of seriesList) {
    const gaps = s.gaps || [];
    if (single) {
      const area = areaPath(s.points, range, gaps);
      if (area) node.append(svg('path', { class: 'area', d: area }));
    }
    const d = linePath(s.points, range, gaps);
    if (d) {
      node.append(svg('path', {
        class: 'line', d, style: colors.get(s.model) ? `--line: ${colors.get(s.model)}` : null,
      }));
    }
    // The backend's resets, plus the ones only the samples know about: a window
    // observed across a restart has no `resets_at` anyone recorded (§6.4).
    const marks = resetLines([...(s.resets || []), ...inferredResets(s.points)], range);
    for (const x of marks) {
      node.append(svg('line', { class: 'reset', x1: x, x2: x, y1: BOX.top, y2: BOX.bottom }));
    }
  }

  for (const tick of xTicks(range, opts.rangeKind || '7d')) {
    const label = svg('text', {
      class: 'tick', x: Math.min(BOX.w - 2, Math.max(2, tick.x)), y: BOX.labelY,
      'text-anchor': tick.x === 0 ? 'start' : tick.x >= BOX.w ? 'end' : 'middle',
    });
    label.textContent = tick.label;
    node.append(label);
  }

  // The hover cursor and its dot, parked outside the box until a pointer arrives.
  node.append(svg('line', { class: 'cursor', x1: -10, x2: -10, y1: BOX.top, y2: BOX.bottom }));
  node.append(svg('circle', { class: 'cursor-dot', cx: -10, cy: -10, r: 3.5 }));
  // The samples the hover snaps to, kept on the node itself. The alternative is a
  // lookup table keyed by element, which is the same thing with more moving parts.
  node.__points = (first && first.points) || [];
  return node;
}

/** The right-hand caption of a column: `now 9%`, or the reason there is no line. */
function columnCaption(column) {
  if (!column.series.length) {
    return column.key === 'per_model' ? 'no per-model limit on this plan' : 'no data';
  }
  const parts = [];
  for (const s of column.series) {
    const last = s.points && s.points.length ? s.points[s.points.length - 1] : null;
    if (!last) continue;
    parts.push(column.key === 'per_model' ? `${s.model} ${last.percent}%` : `now ${last.percent}%`);
  }
  return parts.join(' · ') || 'no data';
}

/**
 * The summary line under the account's e-mail (§6.3). Ordered by what a person needs
 * first: a lock outranks a peak, and having no data at all outranks both — a card
 * saying `peak 39%` about a week that stopped being measured on Tuesday is a lie of
 * omission.
 */
export function summaryLine(account, seriesOfAccount, range) {
  const s = account.summary || {};
  const session = (seriesOfAccount || []).find((x) => x.kind === 'session');
  const gaps = (session && session.gaps) || [];
  const openGap = gaps.find((g) => !g.to);
  if (openGap) return { text: `gap since ${shortMoment(openGap.from)} · ${cause(openGap)}`, tone: 'warning' };
  if (!session || !session.points || !session.points.length) {
    return { text: 'no data in this period', tone: 'warning' };
  }
  if (s.locked_sec) {
    return { text: `locked ${formatDuration(s.locked_sec * 1000)} this week`, tone: 'critical' };
  }
  if (gaps.length) {
    const last = gaps[gaps.length - 1];
    return { text: `peak ${s.peak_session}% · gap ${shortMoment(last.from)} · ${cause(last)}`, tone: 'warning' };
  }
  return { text: `peak ${s.peak_session ?? '—'}% · never locked`, tone: null };
}

const cause = (g) => (g.cause === 'http_429' ? 'HTTP 429' : (g.cause || 'no reason given'));

function shortMoment(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

// ----------------------------------------------------------------- card -----

export function renderStatCard(account, seriesOfAccount, range, rangeKind) {
  const card = el('section', 'stat-card');
  card.dataset.email = (account.email || '').toLowerCase();

  const head = el('div', 'stat-head');
  head.append(el('div', 'account-email', account.email || 'unknown account'));
  if (account.org) head.append(el('div', 'account-org', account.org));
  const sum = summaryLine(account, seriesOfAccount, range);
  const line = el('div', 'stat-summary', sum.text);
  if (sum.tone) line.dataset.tone = sum.tone;
  if (sum.tone === 'critical') card.dataset.state = 'locked';
  head.append(line);
  card.append(head);

  const colors = modelColors(seriesOfAccount);
  const cols = el('div', 'stat-cols');
  for (const column of columnsOf(seriesOfAccount)) {
    const c = el('div', 'stat-col');
    c.dataset.column = column.key;
    c.append(el('div', 'col-title', column.title));
    const chart = renderChart(column.series, range, {
      colors,
      rangeKind: column.key === 'session' ? '24h' : rangeKind,
      label: `${column.title}, ${account.email}`,
    });
    if (!column.series.length) chart.append(svg('line', {
      class: 'flat', x1: 0, x2: BOX.w, y1: yOf(0), y2: yOf(0),
    }));
    c.append(chart);
    c.append(el('div', 'col-now', columnCaption(column)));
    cols.append(c);
  }
  card.append(cols);
  card.append(el('div', 'hover-readout'));
  attachHover(card, range);
  return card;
}

/**
 * The whole view. Rebuilt wholesale rather than patched point by point, unlike the
 * list: history arrives on a range change or an explicit refresh, not five times a
 * minute, and there is no hover state on a chart worth preserving across a reload of
 * the data underneath it.
 */
export function renderStats(history, rangeKind = '7d') {
  const view = document.getElementById('view-stats');
  if (!view) return;
  view.replaceChildren();

  const accounts = (history && history.accounts) || [];
  const range = (history && history.range) || null;
  if (!range || !accounts.length) {
    view.append(el('p', 'placeholder', 'no history yet'));
    return;
  }

  view.append(renderFilters(rangeKind, history));
  view.append(renderTiles(history.tiles));

  const by = seriesByAccount(history.series);
  const cards = el('div', 'stat-cards');
  for (const account of accounts) {
    cards.append(renderStatCard(account, by.get(account.id) || [], range, rangeKind));
  }
  view.append(cards);
}

function renderFilters(rangeKind, history) {
  const bar = el('div', 'stats-filters');

  const ranges = el('div', 'range-tabs');
  ranges.setAttribute('role', 'tablist');
  ranges.setAttribute('aria-label', 'period');
  for (const r of RANGES) {
    const b = el('button', 'chip', r === '24h' ? '24 h' : r === '7d' ? '7 d' : '30 d');
    b.setAttribute('type', 'button');
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(r === rangeKind));
    b.dataset.range = r;
    ranges.append(b);
  }
  bar.append(ranges);

  const groups = el('div', 'group-tabs');
  groups.setAttribute('role', 'tablist');
  groups.setAttribute('aria-label', 'grouping');
  for (const g of ['account', 'folder']) {
    const b = el('button', 'chip', g === 'account' ? 'Accounts' : 'Folders');
    b.setAttribute('type', 'button');
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(g === 'account'));
    b.dataset.group = g;
    // The folders view is task T2.24; the control exists so the row matches the
    // artboard, and says why it does nothing yet instead of failing silently.
    if (g === 'folder') { b.disabled = true; b.title = 'folders view: not built yet'; }
    groups.append(b);
  }
  bar.append(groups);

  const legend = el('div', 'legend');
  const colors = modelColors(history.series);
  for (const [name, color] of colors) {
    const item = el('span', 'legend-item', name);
    item.style.setProperty('--swatch', color);
    legend.append(item);
  }
  bar.append(legend);
  return bar;
}

/**
 * The shared hover of §6.4: one vertical, moving in ALL THREE columns of a card at
 * once, because the three charts share a time axis and reading them apart is the
 * thing the layout exists to prevent.
 */
export function attachHover(card, range) {
  const charts = Array.from(card.querySelectorAll('.chart'));
  const move = (ev) => {
    const source = ev.currentTarget;
    const rect = source.getBoundingClientRect();
    if (!rect.width) return;
    const x = ((ev.clientX - rect.left) / rect.width) * BOX.w;
    for (const chart of charts) {
      const cursor = chart.querySelector('.cursor');
      const dot = chart.querySelector('.cursor-dot');
      if (cursor) { cursor.setAttribute('x1', x); cursor.setAttribute('x2', x); }
      const pts = chart.__points || [];
      const near = nearestPoint(pts, x, range);
      if (dot && near) {
        dot.setAttribute('cx', near.x);
        dot.setAttribute('cy', yOf(near.point.percent));
      }
      if (chart === source && near) {
        const readout = card.querySelector('.hover-readout');
        if (readout) {
          readout.textContent =
            `${new Date(near.point.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} · ${near.point.percent}%`;
        }
      }
    }
  };
  const leave = () => {
    for (const chart of charts) {
      const cursor = chart.querySelector('.cursor');
      const dot = chart.querySelector('.cursor-dot');
      if (cursor) { cursor.setAttribute('x1', -10); cursor.setAttribute('x2', -10); }
      if (dot) { dot.setAttribute('cx', -10); dot.setAttribute('cy', -10); }
    }
  };
  for (const chart of charts) {
    chart.addEventListener('pointermove', move);
    chart.addEventListener('pointerleave', leave);
  }
}
