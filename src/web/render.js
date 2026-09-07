// render.js — snapshot -> DOM (tasks T2.20, T2.21).
//
// Separated from app.js so scripts/test-render.mjs can IMPORT it and check the
// structure under node instead of carrying a copy. The copy was the first version
// and it was wrong to keep: two renderers drift, and the test would then pass on
// code nobody ships. Everything here takes a document and returns nodes; no fetch,
// no timers, no EventSource.
import { elapsedShare, cellGeometry, formatReset, rowLabel, sortLimits, severityOf } from './format.js';

// ------------------------------------------------------------- rendering ----

export const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/**
 * One limit window: name, bar, percent, reset caption (01.1 §2).
 *
 * WHY SOME VALUES ARE RECOMPUTED THOUGH THE BACKEND SENDS THEM. The response carries
 * `label`, `reset_label` and `elapsed_share` (01.3 §3.3), and 01.1 §2.4/§2.6 say the
 * page recomputes the countdown and the elapsed share locally. Both are right, and
 * the reason is time: a server label is correct at the poll and wrong a minute later,
 * and the poll is five minutes apart by default. So the server value is the fallback
 * — used when we cannot compute, e.g. a missing `resets_at` — and the local value
 * wins while it can be had. The differential excludes these fields for exactly this
 * reason (01.3 §5).
 */
export function renderRow(limit) {
  const sev = severityOf(limit);
  const row = el('div', 'row');
  row.dataset.severity = sev;
  row.dataset.kind = limit.kind;
  if (limit.resets_at) row.dataset.resetsAt = limit.resets_at;

  row.append(el('span', 'row-name', limit.label || rowLabel(limit)));

  const bars = el('div', 'row-bars');
  const bar = el('div', 'bar');
  const fill = el('div', 'bar-fill');
  fill.style.width = `${Math.max(0, Math.min(100, limit.percent ?? 0))}%`;
  bar.append(fill);
  const fc = limit.forecast;
  if (fc && fc.percent_at_reset != null && fc.percent_at_reset > limit.percent) {
    const ghost = el('div', 'bar-ghost');
    ghost.style.left = `${limit.percent}%`;
    ghost.style.width = `${Math.min(100, fc.percent_at_reset) - limit.percent}%`;
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
  reset.append(el('span', 'reset-when',
    limit.resets_at ? formatReset(limit.resets_at) : (limit.reset_label || '—')));
  if (fc && fc.label) {
    const f = el('span', 'reset-forecast', fc.label);
    if (fc.warning) f.dataset.warning = 'true';
    reset.append(f);
  }
  row.append(reset);
  return row;
}

/**
 * One account: header with its state, then its windows in the fixed order.
 *
 * `limits` arrives FLAT beside `accounts` and is joined by `account_id` (01.3 §3.3)
 * — not nested inside the account. The first version of this renderer assumed
 * nesting and would have drawn every account empty against a real backend; caught by
 * reading the response shape before there was a backend to be wrong against.
 */
export function renderAccount(acc, limits) {
  const block = el('section', 'account');
  block.dataset.state = acc.state || 'ok';
  if (acc.locked) block.dataset.state = 'locked';

  const head = el('header', 'account-head');
  head.append(el('span', 'account-email', acc.email || 'unknown account'));
  if (acc.org) head.append(el('span', 'account-org', acc.org));
  // `dirs` are objects {id, path, name}; the name is what a person recognises, and
  // the full path belongs in the tooltip rather than the line.
  if (acc.dirs && acc.dirs.length) {
    const d = el('span', 'account-dirs', acc.dirs.map((x) => x.name || x).join(', '));
    d.title = acc.dirs.map((x) => x.path || x).join('\n');
    head.append(d);
  }
  block.append(head);

  // A state other than ok replaces the rows with its reason. Never an empty block:
  // an account with nothing under it is indistinguishable from a broken renderer.
  if (acc.state && acc.state !== 'ok') {
    block.append(el('p', 'account-note', acc.message || acc.state));
    return block;
  }
  for (const limit of sortLimits(limits)) block.append(renderRow(limit));
  return block;
}

/**
 * Point updates, not a redraw (01.1 §9). The account block is keyed by e-mail: an
 * existing one is replaced in place, a new one is inserted at its position, a
 * vanished one is removed. Redrawing the list wholesale would drop the hover, the
 * focus and any open tooltip on every poll — five times a minute in the degraded
 * mode, which is exactly when the user is watching closely.
 */
export function renderList(accounts, allLimits) {
  const view = document.getElementById('view-list');
  const have = new Map(Array.from(view.children).map((n) => [n.dataset.email, n]));
  const seen = new Set();

  // Join once, not per account: a linear scan inside a loop over accounts is the
  // kind of thing that is invisible at four logins and silly at forty.
  const byAccount = new Map();
  for (const l of allLimits || []) {
    if (!byAccount.has(l.account_id)) byAccount.set(l.account_id, []);
    byAccount.get(l.account_id).push(l);
  }

  accounts.forEach((acc, i) => {
    const key = (acc.email || `?${i}`).toLowerCase();
    seen.add(key);
    const fresh = renderAccount(acc, byAccount.get(acc.id) || []);
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
export function layoutCells() {
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
