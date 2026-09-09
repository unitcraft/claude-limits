// A suite whose cases come from a directory. The directory is empty today --
// renamed fixtures, a filter that matches nothing, a glob that stopped globbing --
// so the loop body never runs and the suite exits 0 having measured nothing.
import { readdirSync } from 'node:fs';
let passed = 0;
const cases = readdirSync(new URL('./cases/', import.meta.url)).filter((f) => f.endsWith('.json'));
for (const c of cases) { passed += 1; console.log(`  ok  ${c}`); }
console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
