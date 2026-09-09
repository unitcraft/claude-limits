// One page, one moment, several answers: who decides the zone, the locale and the clock.
//
// The snapshot carries `tz` (the application's setting) and a ready `reset_label` for
// every limit. The page assigns `tz` to its state and never reads it again, and every
// place that prints a moment picks its own locale and its own 12/24-hour convention.
//
// Run:  node probe.mjs      (cmd.sh runs it twice, in two zones)
import { readFileSync } from 'node:fs';
import { formatResetMoment, formatReset, footerRight } from '../../src/web/format.js';

const snap = JSON.parse(readFileSync(new URL('../../fixtures/api/snapshot-mixed.json', import.meta.url)));
const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;

console.log(`this run's zone : ${zone}`);
console.log(`snapshot says   : tz = ${snap.tz}  <- assigned at app.js:295, read by nothing`);
console.log();

// --- 1. the option sets, as the six sites spell them -------------------------
// Every one of these is a separate decision about locale and clock, and they are
// not the same decision. Reproduced here with an explicit `en-US` because that is
// what a browser in the United States passes when the code passes `[]`.
const t = new Date('2026-09-07T17:50:00Z');
const sites = [
  ['app.js:292   fetched-at', { hour: '2-digit', minute: '2-digit' }, []],
  ['app.js:561   refresh tip', { hour: '2-digit', minute: '2-digit' }, []],
  ['format.js:83 reset column', { hour: '2-digit', minute: '2-digit', hour12: false }, []],
  ['format.js:214 footer next', { hour: '2-digit', minute: '2-digit' }, []],
  ['stats.js:429 chart cursor', { hour: '2-digit', minute: '2-digit', hour12: false }, []],
  ['chart.js:159 axis tick', { hour: '2-digit', minute: '2-digit', hour12: false }, []],
];
console.log('the same instant, printed by the option sets the page actually uses,');
console.log('under a browser whose locale is en-US:');
const shown = new Set();
for (const [where, opts] of sites) {
  const s = t.toLocaleTimeString('en-US', opts);
  shown.add(s);
  console.log(`  ${where.padEnd(28)} ${s}`);
}
console.log(`  -> ${shown.size} different strings for one instant on one page`);
console.log();

// --- 2. the server's label against the page's own rendering ------------------
console.log('the server sends `reset_label`; render.js:115 prefers its own rendering');
console.log('whenever `resets_at` is present. Same field, two answers:');
let differ = 0;
for (const l of snap.limits.filter((x) => x.resets_at && x.reset_label).slice(0, 4)) {
  const mine = formatReset(l.resets_at, Date.parse(snap.fetched_at));
  if (mine !== l.reset_label) differ += 1;
  console.log(`  ${l.kind.padEnd(14)} ${l.resets_at}`);
  console.log(`     server: ${l.reset_label.padEnd(22)} page: ${mine}` +
              `${mine === l.reset_label ? '' : '   <- differ'}`);
}
console.log();
console.log(`labels that differ from the server's in this zone: ${differ} of 4`);
console.log('01.3 section 9, deviation D2 justifies the *_label fields with:');
console.log('  "two interfaces (the page and the widget) ... must show ONE string".');
console.log();

// --- 3. two disagreements that survive ANY zone, because they are not about zones -
const wk = snap.limits.find((l) => l.kind === 'weekly_all');
const dur = (s) => (s.match(/\(([^)]*)\)/) || [])[1];
const roundingCase = snap.limits.find((l) => l.resets_at && l.reset_label
  && dur(l.reset_label) !== dur(formatReset(l.resets_at, Date.parse(snap.fetched_at))));
console.log('two disagreements survive ANY zone, because they are not about zones:');
console.log(`  weekday : ${wk.resets_at} is a ${new Date(wk.resets_at).toUTCString().slice(0, 3)},`);
console.log(`            the server's label for it says "${wk.reset_label}"`);
if (roundingCase) {
  const mins = (Date.parse(roundingCase.resets_at) - Date.parse(snap.fetched_at)) / 60000;
  console.log(`  rounding: ${mins.toFixed(2)} minutes from fetched_at ${snap.fetched_at};`);
  console.log(`            server "${dur(roundingCase.reset_label)}", `
    + `page "${dur(formatReset(roundingCase.resets_at, Date.parse(snap.fetched_at)))}"`);
} else {
  console.log('  rounding: no case in this fixture');
}

// --- 4. the locale is decided per site too ------------------------------------
// Six sites pass `[]` (follow the browser), six pass 'en' (force English), and
// stats.js:212 passes nothing at all (browser locale AND browser date style).
const p = new Date('2026-09-07T17:50:00Z');
console.log();
console.log(`the same instant on one statistics card, in this run's locale`
  + ` (${Intl.DateTimeFormat().resolvedOptions().locale}):`);
console.log(`  chart.js:161 axis tick   (locale 'en')  ${p.toLocaleDateString('en', { weekday: 'short' })}`);
console.log(`  stats.js:286 gap caption (locale 'en')  ${p.toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}`);
console.log(`  stats.js:212 values table (no locale)   ${p.toLocaleString()}`);
