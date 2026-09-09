// One header, two paths. Written while they gave two answers; kept as the check
// that they still give one.
//
//   node probes/hunt-conventions-retry-after/measure.mjs
//
// THE DEFECT, measured 2026-09-08. `Retry-After` has two legal forms (RFC 9110
// 10.2.3): delay-seconds, or an HTTP-date. The retry delay was decided in four
// places -- format.js retryDelay, format.js refuseFor, app.js, live.js -- and only
// one of them knew about the second form. Handed the same date header:
//
//     GET path (app.js, `Number(header)` -> NaN)  ->     500 ms
//     button path (refuseFor, parses the date)    -> 300 000 ms
//
// A 600-fold difference on one input, and the short side is not a shorter wait --
// it is the server being ignored. `Number` of a date is NaN, NaN reaches retryDelay
// as "no header given", and it backs off exponentially as though nothing was said.
//
// THE DOOR. `retryAfterSeconds` is now the one place the header is read; the two
// callers keep their own policies (the button waits a minute when it cannot read
// anything, a GET backs off) but they read the SAME header. This file asserts they
// agree, so the door cannot quietly reopen.
import { retryDelay, refuseFor, retryAfterSeconds } from '../../src/web/format.js';

const now = Date.parse('2026-09-09T01:00:00Z');
const header = new Date(now + 300_000).toUTCString();   // an HTTP-date, +5 minutes

const naive = Number(header);                            // NaN -- what app.js used to do
const getWaitMs = retryDelay(1, retryAfterSeconds(header, now), () => 0.5);
const buttonWaitMs = refuseFor(429, header, now) * 1000;

console.log('header            :', header);
console.log('Number(header)    :', naive, '  <- why the naive read failed');
console.log('GET path waits    :', getWaitMs, 'ms');
console.log('button path waits :', buttonWaitMs, 'ms');

let bad = 0;

if (!Number.isNaN(naive)) {
  console.log('\nUNEXPECTED: Number() parsed an HTTP-date. The premise of this probe is');
  console.log('gone; re-read it before trusting either number.');
  bad = 1;
}

if (getWaitMs !== buttonWaitMs) {
  console.log('\nREGRESSION: the two paths disagree --', getWaitMs, 'vs', buttonWaitMs, 'ms.');
  console.log('Something reads Retry-After without going through retryAfterSeconds.');
  bad = 1;
}

if (getWaitMs !== 300_000) {
  console.log('\nREGRESSION: the server asked for 300000 ms and got', getWaitMs, 'ms.');
  console.log('Agreement alone is not enough -- both paths could agree on the wrong number.');
  bad = 1;
}

if (!bad) {
  console.log('\nOK: both paths obey the same header, 300000 ms each, which is what it says.');
}
process.exit(bad);
