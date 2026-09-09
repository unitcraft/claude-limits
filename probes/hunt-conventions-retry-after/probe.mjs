// One header, two answers, in one file.
//
// The page has two callers that must answer the same question -- "the server said
// Retry-After, how long do we wait?" -- and they answer it differently. Both live in
// src/web/format.js; a third place, app.js:203, converts the header to a number
// before either of them sees it.
//
// Run:  node probe.mjs
import { retryDelay, refuseFor, REFUSAL_MAX_SEC } from '../../src/web/format.js';

const NOW = Date.parse('2026-09-08T12:00:00Z');
const rand = () => 0.5;                       // jitter pinned, so the numbers are stable

// app.js:203 is the conversion the retry path actually performs:
//     const after = res && res.headers.get('Retry-After');
//     await sleep(retryDelay(attempt, after ? Number(after) : null));
const asRetryPathSeesIt = (header) => retryDelay(1, header ? Number(header) : null, rand);

const cases = [
  ['120', 'delay-seconds, the ordinary form'],
  ['Tue, 08 Sep 2026 12:05:00 GMT', 'HTTP-date, the other form RFC 9110 10.2.3 allows'],
  ['86400', 'an absurd but legal value'],
];

console.log('header'.padEnd(34), 'GET retry path'.padEnd(18), 'refresh button');
console.log('-'.repeat(34), '-'.repeat(18), '-'.repeat(16));
let disagreements = 0;
for (const [header, note] of cases) {
  const a = asRetryPathSeesIt(header) / 1000;
  const b = refuseFor(429, header, NOW);
  if (a !== b) disagreements += 1;
  console.log(`${header.padEnd(34)} ${String(a + ' s').padEnd(18)} ${b} s     <- ${note}`);
}

console.log();
console.log(`disagreements: ${disagreements} of ${cases.length}`);
console.log('the retry path has no ceiling at all; the button caps at', REFUSAL_MAX_SEC, 's');
console.log();
console.log('convention api.md section 17: "`Retry-After` perekryvaet raschet bezuslovno"');
console.log('  -- on the HTTP-date form the GET path does not honour it at all:');
console.log('     Number("Tue, 08 Sep 2026 12:05:00 GMT") is NaN, the `>= 0` test fails,');
console.log('     and the wait falls back to the computed 0.5 s against a server that');
console.log('     has just asked for five minutes.');
