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

  if (r.status === 0) {
    line('ok', suite, last);
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

// The page guard is python and prints its own verdict; same rule, judge the code.
const guard = spawnSync('python', [path.join(here, 'check-page.py')], {
  cwd: repo, encoding: 'utf8',
});
const guardOut = (guard.stdout || '').trim();
const guardLast = guardOut ? guardOut.split('\n').find((l) => l.startsWith('PAGE GUARD')) : '';
if (guard.status === 0) {
  line('ok', 'check-page.py', guardLast || 'clean');
} else {
  failed += 1;
  line('FAIL', 'check-page.py', guardLast || `exit ${guard.status}`);
  for (const l of guardOut.split('\n').slice(-8)) console.log(`         ${l}`);
}

console.log(`\n${suites.length} suites + the page guard, ${total} tests`);
console.log(failed ? `WEB CHECK: FAILED (${failed})` : 'WEB CHECK: clean');
process.exit(failed ? 1 : 0);
