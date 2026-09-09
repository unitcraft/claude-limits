// render.js — snapshot -> DOM (tasks T2.20, T2.21).
//
// Separated from app.js so scripts/test-render.mjs can IMPORT it and check the
// structure under node instead of carrying a copy. The copy was the first version
// and it was wrong to keep: two renderers drift, and the test would then pass on
// code nobody ships. Everything here takes a document and returns nodes; no fetch,
// no timers, no EventSource.
import {
  elapsedShare, cellGeometry, formatReset, rowLabel, sortLimits, severityOf, applyOrder, wireNumber, getViewOptions } from './format.js';

// ------------------------------------------------------------- rendering ----

export const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/**
 * Everything the bar means, in one sentence (01.1 §10, the example given there:
 * `74%, Fable, 7 days, resets Tue 13:00` plus `61% of the window elapsed; forecast
 * 103% at reset`).
 *
 * It is ASSEMBLED rather than taken from a field because the three things it must
 * carry live in three places — the percent on the bar, the elapsed share in a strip
 * marked `aria-hidden`, the forecast in a ghost marked the same. Both of those are
 * hidden precisely so they are not read as separate meaningless bars, which leaves
 * this string as the only place their meaning survives.
 */
export function valueText(limit, elapsedPercent = null) {
  const parts = [`${Math.round(wireNumber(limit.percent) ?? 0)}%`, limit.label || rowLabel(limit)];
  if (limit.locked_reason) parts.push(`locked: ${limit.locked_reason}`);
  if (limit.resets_at) parts.push(`resets ${formatReset(limit.resets_at)}`);
  else if (limit.reset_label) parts.push(`resets ${limit.reset_label}`);
  if (elapsedPercent != null) parts.push(`${elapsedPercent}% of the window elapsed`);
  const fc = limit.forecast;
  if (fc && fc.percent_at_reset != null) {
    parts.push(`forecast ${Math.round(wireNumber(fc.percent_at_reset) ?? 0)}% at reset`);
  }
  return parts.join('; ');
}

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
export function renderRow(limit, { dimmed = false } = {}) {
  const sev = severityOf(limit);
  const row = el('div', 'row');
  row.dataset.severity = sev;
  if (dimmed) row.dataset.dimmed = 'true';
  row.dataset.kind = limit.kind;
  if (limit.resets_at) row.dataset.resetsAt = limit.resets_at;

  row.append(el('span', 'row-name', limit.label || rowLabel(limit)));

  const bars = el('div', 'row-bars');
  const bar = el('div', 'bar');
  // A bar is a meter, and it has to SAY so (01.1 §10). Without this a screen reader
  // reads an empty div: the percent sits in a sibling and the strip and the ghost
  // carry no text at all, so their meaning has to be folded into `aria-valuetext` —
  // which is why that string is assembled rather than taken from one field.
  bar.setAttribute('role', 'meter');
  bar.setAttribute('aria-valuemin', '0');
  bar.setAttribute('aria-valuemax', '100');
  bar.setAttribute('aria-valuenow', String(Math.round(wireNumber(limit.percent) ?? 0)));
  const fill = el('div', 'bar-fill');
  fill.style.width = `${Math.max(0, Math.min(100, wireNumber(limit.percent) ?? 0))}%`;
  bar.append(fill);
  // No ghost on a dimmed row: a forecast is a claim about where the pace lands, and
  // we do not know the pace of an account we cannot reach (01.1 sec.3.2).
  const fc = dimmed ? null : limit.forecast;
  // Through wireNumber: a fractional percent arrives as a STRING (api.md:512), and
  // `">"` on two strings compares them lexicographically -- "9.5" > "74.5" is true.
  const fcPct = wireNumber(fc && fc.percent_at_reset);
  const limPct = wireNumber(limit.percent) ?? 0;
  if (fc && fcPct != null && fcPct > limPct) {
    const ghost = el('div', 'bar-ghost');
    ghost.style.left = `${limit.percent}%`;
    ghost.style.width = `${Math.min(100, fcPct) - limPct}%`;
    ghost.setAttribute('aria-hidden', 'true');
    bar.append(ghost);
  }
  bars.append(bar);

  // The time strip is computed here, not sent: only resets_at and kind are needed
  // (01.1 §2.6). Reading: fill left of the strip's end means a pace below the window.
  let elapsed = null;
  if (limit.resets_at && !dimmed && getViewOptions().time_bar) {
    const strip = el('div', 'timebar');
    const share = elapsedShare(limit.kind, limit.resets_at);
    elapsed = Math.round(share * 100);
    const done = el('div', 'timebar-fill');
    done.style.width = `${(share * 100).toFixed(1)}%`;
    strip.append(done);
    strip.title = `time elapsed ${elapsed}%`;
    strip.setAttribute('aria-hidden', 'true');   // its meaning goes into valuetext
    bars.append(strip);
  }
  bar.setAttribute('aria-valuetext',
    dimmed ? `last known: ${valueText(limit, null)}` : valueText(limit, elapsed));
  row.append(bars);

  const pct = el('span', 'row-pct',
    limit.percent == null ? '—' : `${Math.round(wireNumber(limit.percent) ?? 0)}%`);
  row.append(pct);

  const reset = el('div', 'row-reset');
  reset.append(el('span', 'reset-when',
    limit.resets_at ? formatReset(limit.resets_at)
                    : (limit.reset_label || '—')));
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
  // Two different facts, both of which colour the block (01.3 §3.3): `locked` means
  // a window carries a `locked_reason` -- the endpoint is refusing -- while `at_100`
  // means a window sits at 100% with no reason given, i.e. the allowance is simply
  // spent. `at_100` was missing here and the block stayed uncoloured for exactly the
  // case a person most needs to see; the acceptance line of T2.20 names it.
  //
  // `locked` wins when both are true: "refused" is the more specific statement, and
  // a person who sees it does not also need to be told the number reached 100.
  if (acc.at_100) block.dataset.state = 'at-100';
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

  // 01.1 sec.3.2 splits the not-ok states, and the split is the point.
  //
  // `unknown` -- a 429 or a network blip -- KEEPS the rows: they are the last good
  // snapshot, and they are what a person most wants to see at exactly that moment.
  // They are dimmed as a group, and the badge in the header says why and until when.
  // Until 2026-09-08 every not-ok state was treated alike and the numbers vanished
  // on a single rate-limited poll.
  if (acc.state === 'unknown') {
    const badge = el('span', 'account-badge', acc.message || 'no answer');
    badge.dataset.tone = 'warning';
    head.append(badge);
    const dim = el('div', 'rows-dimmed');
    dim.dataset.dimmed = 'true';
    // The strip and the ghost are statements about NOW, and this reading is not now:
    // drawing them would date stale numbers with a live clock.
    for (const limit of sortLimits(limits)) dim.append(renderRow(limit, { dimmed: true }));
    block.append(dim);
    return block;
  }

  // `stale` and `error` have nothing to show -- the token is dead, or the answer was
  // rejected -- so the reason takes the place of the rows. Never an empty block: an
  // account with nothing under it is indistinguishable from a broken renderer.
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
export function renderList(accounts, allLimits, order = null) {
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

  // One order for every view (01.1 §4.1): a card dragged in the cards view moves in
  // the list too, or the two views disagree about which account is first.
  applyOrder(accounts, order).forEach((acc, i) => {
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

// ------------------------------------------------------ cards view (§4) -----

/**
 * One card: the same account block as the list, in a rounded panel with a drag
 * handle on the left (01.1 §4).
 *
 * The handle is a real `<button>`, not the artboard's bare `<div>` with a grab
 * cursor. 01.1 §10 requires every interactive element to be a real control with a
 * visible focus ring, and the same section gives the handle a keyboard protocol
 * (Space takes, arrows move, Space drops, Esc cancels) — which a div cannot receive
 * at all. Its six dots are drawn in CSS rather than as an inline SVG so this
 * function needs no `createElementNS`, and so the dots recolour with the card state
 * by inheriting `currentColor`.
 */
export function renderCard(acc, limits) {
  const card = el('article', 'card');
  const handle = el('button', 'card-handle');
  handle.setAttribute('type', 'button');
  handle.setAttribute('aria-label', `reorder ${acc.email || 'account'}`);
  handle.title = 'drag to reorder, or Space then arrows';
  card.append(handle);

  const body = renderAccount(acc, limits);
  card.append(body);
  card.dataset.state = body.dataset.state;
  return card;
}

/**
 * The cards view, updated point by point exactly as the list is, and for the same
 * reason: a wholesale redraw during a drag would tear the card out from under the
 * pointer.
 *
 * `order` is the page's optimistic order (01.1 §4.2) — the e-mails as they should
 * appear right now, which between a drop and the server's answer is NOT the order
 * the snapshot arrived in.
 */
export function renderCards(accounts, allLimits, order = null) {
  const view = document.getElementById('view-cards');
  if (!view) return;
  const have = new Map(Array.from(view.children)
    .filter((n) => n.className === 'card')
    .map((n) => [n.dataset.email, n]));
  const seen = new Set();

  const byAccount = new Map();
  for (const l of allLimits || []) {
    if (!byAccount.has(l.account_id)) byAccount.set(l.account_id, []);
    byAccount.get(l.account_id).push(l);
  }

  applyOrder(accounts, order).forEach((acc, i) => {
    const key = (acc.email || `?${i}`).toLowerCase();
    seen.add(key);
    const fresh = renderCard(acc, byAccount.get(acc.id) || []);
    fresh.dataset.email = key;
    const old = have.get(key);
    if (old) old.replaceWith(fresh);
    else view.insertBefore(fresh, view.children[i] || null);
  });

  for (const [key, node] of have) if (!seen.has(key)) node.remove();
}

/**
 * The "cells" bar style needs pixel widths, so it is applied after layout and again
 * on resize (01.1 §2.2). Whole cells only — the geometry is in format.js and tested.
 */
export function layoutCells() {
  if (document.body.dataset.barStyle !== 'cells') return;
  // `document.querySelectorAll`, not the `$$` helper: that one lives in app.js, and
  // when these functions moved here the call came with them and would have thrown a
  // ReferenceError the first time anyone chose the cells style. It threw in nothing
  // until then only because the default style is bars.
  for (const bar of Array.from(document.querySelectorAll('.bar'))) {
    const fill = bar.querySelector('.bar-fill');
    const pct = parseFloat(fill.style.width) || 0;
    const g = cellGeometry(bar.parentElement.clientWidth, pct);
    bar.style.width = `${g.barWidth}px`;
    fill.style.width = `${g.fillWidth}px`;
    bar.title = `${Math.round(pct)}% · ${g.filledCells} of ${g.cells} cells`;
  }
}
