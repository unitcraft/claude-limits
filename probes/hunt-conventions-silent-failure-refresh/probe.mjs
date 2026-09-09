// What each network call of the page does when it fails, and what the "poll now"
// button does.
//
// The function under test is not re-typed here: it is EXTRACTED from src/web/app.js
// by its own source text and executed as written, with `fetch` and `refuseFor`
// injected. The extracted text is printed, so nothing is taken on trust.
//
// Run:  node probe.mjs
import { readFileSync } from 'node:fs';
import { refuseFor } from '../../src/web/format.js';

const web = new URL('../../src/web/', import.meta.url);
const src = readFileSync(new URL('app.js', web), 'utf8');
const NL = String.fromCharCode(10);
const lines = src.split(NL);

// --- 1. the inventory: every network call, its own handler, and its callers ---
const fns = [];
lines.forEach((l, i) => {
  const m = /^(?:async )?function (\w+)/.exec(l);
  if (m) fns.push({ name: m[1], from: i + 1 });
});
fns.forEach((f, i) => { f.to = i + 1 < fns.length ? fns[i + 1].from - 1 : lines.length; });
const owner = (n) => fns.find((f) => n >= f.from && n <= f.to);

const others = ['app.js', 'reorder.js', 'render.js', 'settings.js', 'live.js']
  .map((f) => [f, readFileSync(new URL(f, web), 'utf8')]);

console.log('every fetch() in app.js: does its own function catch, and who calls it?');
lines.forEach((l, i) => {
  if (!/\bfetch\(/.test(l) || l.trim().startsWith('*')) return;
  const f = owner(i + 1);
  const body = lines.slice(f.from - 1, f.to).join(NL);
  const own = /\bcatch\b/.test(body) ? 'catches' : 'NO catch';
  console.log(`  app.js:${String(i + 1).padEnd(4)} inside ${f.name.padEnd(14)} ${own}`);
  for (const [name, text] of others) {
    text.split(NL).forEach((cl, ci) => {
      if (name === 'app.js' && ci + 1 >= f.from && ci + 1 <= f.to) return;
      if (!new RegExp(`\\b${f.name}\\(`).test(cl)) return;
      if (/^\s*(\*|\/\/)/.test(cl)) return;
      console.log(`        called at ${name}:${ci + 1}  ${cl.trim().slice(0, 64)}`);
    });
  }
});
console.log();

// --- 2. the one with no handler anywhere, executed as written ----------------
const m = src.match(/async function refresh\(btn\) \{[\s\S]*?\n\}/);
console.log('the source executed below, verbatim from app.js:');
console.log(m[0].split(NL).map((l) => `    ${l}`).join(NL));
console.log();

const make = new Function('fetch', 'refuseFor',
  `return (${m[0].replace('async function refresh', 'async function')});`);
const btn = { dataset: {}, disabled: false, title: 'poll now' };
const deadNetwork = () => Promise.reject(new TypeError('Failed to fetch'));
const refresh = make(deadNetwork, refuseFor);

try {
  await refresh(btn);
  console.log('the promise RESOLVED with the backend unreachable');
} catch (e) {
  console.log(`the promise REJECTED: ${e.constructor.name}: ${e.message}`);
  console.log('   the click handler is `(e) => refresh(e.currentTarget)` (app.js:600-601):');
  console.log('   nothing awaits it, so this becomes an unhandled rejection in the console.');
}
console.log(`button afterwards: spinning=${btn.dataset.spinning} disabled=${btn.disabled} title="${btn.title}"`);
console.log('nothing in the extracted body can say a word to the person: there is no');
console.log('toast, no placeholder and no title change on this path.');
