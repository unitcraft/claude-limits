// What happens the day a percent arrives as a string?
//
//   node probes/hunt-conventions-no-number-boundary/measure.mjs
//
// THE CONVENTION decides the question, api.md:512: a fractional share travels as a
// STRING of decimal digits, while integer counters travel as JSON numbers. Today
// every percent in the contract is an integer, so nothing coerces and nothing breaks.
// That is what made this finding conditional -- the hunter said so himself -- and
// also what makes it worth closing before the condition arrives.
//
// THE FAILURE IS NOT A CRASH, which is the point. Math.round("74.5") is 75. But
// `"9.5" > "74.5"` compares two strings lexicographically and is TRUE, so a forecast
// of 9.5% would be drawn as exceeding a usage of 74.5% -- the ghost bar appears on
// rows it should not, sized by a subtraction of strings. Plausible, silent, wrong.
//
// This probe feeds the renderer the string form and requires the same answers as the
// numeric form, then checks the specific comparison directly.
import { wireNumber, cellGeometry } from '../../src/web/format.js';

let bad = 0;
const check = (c, m) => { if (!c) { console.log('  FAIL:', m); bad = 1; } };

// --- the boundary itself ---------------------------------------------------
console.log('wireNumber("74.5")  =', wireNumber('74.5'));
console.log('wireNumber(74)      =', wireNumber(74));
console.log('wireNumber(null)    =', wireNumber(null));
console.log('wireNumber("")      =', wireNumber(''));
console.log('wireNumber("abc")   =', wireNumber('abc'));

check(wireNumber('74.5') === 74.5, 'a decimal string must become a number');
check(wireNumber(74) === 74, 'a number must pass through');
check(wireNumber(null) === null, 'null must stay null, not become 0');
check(wireNumber('') === null, 'an empty string must not become 0');
check(wireNumber('abc') === null, 'nonsense must not become NaN downstream');

// null and 0 are different answers: folding them makes a missing forecast look like
// a complete one, which is a wrong picture rather than a missing one.
check(wireNumber(null) !== 0, 'null must not fold into zero');

// --- the comparison that inverts -------------------------------------------
// Exactly the shape of render.js's forecast test, with the values that expose it.
const usage = '74.5';
const forecast = '9.5';
const naive = forecast > usage;                       // string comparison: TRUE
const viaBoundary = wireNumber(forecast) > wireNumber(usage);   // FALSE

console.log('');
console.log(`raw    : "${forecast}" > "${usage}"  ->`, naive, '  <- the defect');
console.log(`boundary: ${wireNumber(forecast)} > ${wireNumber(usage)}        ->`, viaBoundary);

check(naive === true, 'the premise is gone: string comparison no longer inverts here');
check(viaBoundary === false, 'the boundary did not fix the comparison');

// --- what cellGeometry does NOT prove, which is worth more than what it does ----
//
// My first version compared cellGeometry's output for numbers against strings and
// called that the control. Removing the coercion left it GREEN, twice, with two
// different value pairs. A control that will not redden proves nothing, and finding
// that out is the useful part of this probe.
//
// The reason: JavaScript rescues almost everything here. Math.round, Math.min and
// Math.max all coerce a numeric string on their own, and cellGeometry's ghost is
// guarded a SECOND time by `to > filled`, which is arithmetic on already-rounded
// integers. So that function is genuinely robust to string input, and no pair of
// values distinguishes the two versions. The check is deleted rather than kept as
// decoration.
//
// The one operation JavaScript does not rescue is the bare `>` between two strings,
// and the site that has no second guard is render.js's forecast test. It cannot be
// imported here -- render.js reaches for `document` -- so the shape is reproduced,
// and then the SOURCE is read to confirm the real file has the boundary.
{
  const usagePct = '74.5';
  const forecastPct = '9.5';

  const before = forecastPct != null && forecastPct > usagePct;          // the defect
  const after = wireNumber(forecastPct) != null
             && wireNumber(forecastPct) > (wireNumber(usagePct) ?? 0);

  console.log('');
  console.log('render.js forecast test, raw     :', before, ' <- ghost drawn on a row 65 points below');
  console.log('render.js forecast test, boundary:', after);
  check(before === true, 'the premise is gone: these strings no longer invert');
  check(after === false, 'the boundary did not fix the comparison');
}

// And the real file must actually use it, or the two blocks above only describe a
// version of render.js that exists in this probe.
{
  const src = await (await import('node:fs/promises')).readFile(
    new URL('../../src/web/render.js', import.meta.url), 'utf8');
  // The comparison line, whatever the local variables are called. What must NOT
  // appear is a raw `fc.percent_at_reset >` or `> limit.percent`: those are the wire
  // values, and comparing them is the defect. My first version of this check looked
  // for the OLD variable names and reported a fixed file as broken -- a check that
  // hard-codes today's spelling goes stale the first time anything is renamed.
  const lines = src.split('\n');
  const raw = lines.filter(
    (l) => /fc\.percent_at_reset\s*>/.test(l) || />\s*limit\.percent\b/.test(l));
  const guarded = lines.find((l) => /fcPct\s*>\s*limPct/.test(l));
  console.log('render.js compares  :', (guarded || '(no guarded comparison found)').trim());
  if (raw.length) console.log('  raw comparisons still present:', raw.map((l) => l.trim()));
  check(raw.length === 0, 'render.js still compares a raw wire value');
  check(!!guarded, 'render.js has no comparison through the coerced values');
  check(/wireNumber/.test(src), 'render.js does not use wireNumber at all');
}

console.log(bad ? '\nFAILED' : '\nOK: a percent off the wire becomes a number in one place');
process.exit(bad);
