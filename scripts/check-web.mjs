// One entry point for everything that judges the page.
//
//   node scripts/check-web.mjs
//
// Why it exists: until 2026-09-08 the eight suites and the page guard were run by a
// person typing nine commands, and nothing anywhere ran them on its own -- there is
// no CI in this repository yet. An acceptance that depends on somebody remembering
// is not an acceptance; it is a habit, and habits are exactly what stops holding
// when the work gets interesting.
//
// TWO PROPERTIES IT HAS TO HAVE, both learned the hard way today:
//
//   * It discovers suites, never lists them. A runner with a hand-written list
//     silently measures less every time a suite is added -- it stays green while
//     covering fewer files, which is worse than not running at all.
//   * It judges by EXIT CODE, not by reading the summary line. test-render.mjs spent
//     a day printing a green summary before its last test had run; a runner that
//     trusts the printed word inherits every such bug instead of catching it.
import { spawnSync } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.dirname(here);

const suites = readdirSync(here)
  .filter((f) => f.startsWith('test-') && f.endsWith('.mjs'))
  .sort();

if (!suites.length) {
  // Not "nothing to do": the runner is in the wrong place, or the naming changed.
  console.log('FAILED: no test-*.mjs suites found in scripts/ -- a runner that finds');
  console.log('        nothing must not report success.');
  process.exit(1);
}

let failed = 0;
let total = 0;

const line = (verdict, name, note) =>
  console.log(`  ${verdict.padEnd(6)} ${name.padEnd(24)} ${note}`);

for (const suite of suites) {
  const r = spawnSync(process.execPath, [path.join(here, suite)], {
    cwd: repo, encoding: 'utf8',
  });
  const out = (r.stdout || '').trim();
  const last = out ? out.split('\n').pop() : '';
  const count = /^(\d+) passed/.exec(last);
  if (count) total += Number(count[1]);

  if (r.status === 0 && count && Number(count[1]) > 0) {
    line('ok', suite, last);
  } else if (r.status === 0) {
    // A suite that exits 0 having run NOTHING. The guard above protects the file
    // count; this protects the test count, and until 2026-09-08 nothing did -- a
    // suite drawing its cases from an emptied directory printed `0 passed` and the
    // whole run said clean. An empty measurement in the clothes of success, in the
    // one file every other check is run by.
    failed += 1;
    line('FAIL', suite, count
      ? `${last} -- ran no tests at all`
      : `${last || '(no output)'} -- no parsable summary, so emptiness cannot be ruled out`);
  } else {
    failed += 1;
    line('FAIL', suite, last || `exit ${r.status}`);
    // The failures themselves, not just the tally: a runner that hides them makes
    // the reader run the suite again by hand to learn anything.
    for (const l of out.split('\n').filter((x) => x.includes('FAIL'))) {
      console.log(`         ${l.trim()}`);
    }
    if (r.stderr && r.stderr.trim()) console.log(`         ${r.stderr.trim().split('\n')[0]}`);
  }
}

// The python checkers, judged the same way as the suites: by EXIT CODE, never by
// the verdict they print. Listed rather than globbed on purpose -- scripts/ also
// holds `claude_limits.py`, `diff_with_probe.py` and three `make-*.py` generators,
// which are not checks and would fail as ones. The cost of the list is that a new
// checker has to be added here; that is a real step and it is not hidden.
const CHECKERS = [
  ['check-page.py', [], 'PAGE GUARD'],
  ['check-fixtures.py', [], 'SECRET SCAN'],
  ['check-config-fixture.py', [], 'INVENTED'],
  ['check-dir-fixtures.py', [], 'RESULT'],
  ['check-plan-trees.py', [], 'PLAN TREES'],
  ['lint-openapi.py', ['fixtures/openapi/sample.json'], 'OPENAPI LINT'],
  ['check-test-domains.py', [], 'TEST DOMAINS'],
  ['check-fixture-ids.py', [], 'FIXTURE IDS'],
  ['check-scale-suffixes.py', [], 'SCALE SUFFIXES'],
  ['check-duplicate-limits.py', [], 'DUPLICATE LIMITS'],
  ['check-config-shape.py', [], 'CONFIG SHAPE'],
  ['check-artboard-labels.py', [], 'ARTBOARD LABELS'],
  ['check-citations.py', [], 'CITATIONS'],
];

for (const [name, args, verdictPrefix] of CHECKERS) {
  const r = spawnSync('python', [path.join(here, name), ...args], { cwd: repo, encoding: 'utf8' });
  const out = (r.stdout || '').trim();
  const said = verdictPrefix && out
    ? (out.split('\n').find((l) => l.startsWith(verdictPrefix)) || '')
    : (out ? out.split('\n').pop() : '');
  if (r.status === 0) {
    line('ok', name, said || 'clean');
  } else {
    failed += 1;
    line('FAIL', name, said || `exit ${r.status}`);
    for (const l of out.split('\n').slice(-10)) console.log(`         ${l}`);
    if (r.stderr && r.stderr.trim()) console.log(`         ${r.stderr.trim().split('\n')[0]}`);
  }
}

// Implied by the per-suite rule, and stated anyway: it is the one sentence that
// cannot be argued with when somebody asks what the green meant.
if (total === 0) {
  failed += 1;
  line('FAIL', '(the run)', 'zero tests executed in total -- nothing was measured');
}

console.log(`\n${suites.length} suites (${total} tests) + ${CHECKERS.length} checkers`);
console.log(failed ? `WEB CHECK: FAILED (${failed})` : 'WEB CHECK: clean');
process.exit(failed ? 1 : 0);
