// The wire form of a fractional percent is a DECIMAL STRING (api.md section 11,
// database.md section 5). Two files of the page disagree about who converts it:
// chart.js coerces at the door (`Number(percent) || 0`), render.js compares the raw
// value. Same input, two behaviours.
//
// Run:  node probe.mjs
import { Node, installDocument } from '../../scripts/dom-stub.mjs';
import { yOf } from '../../src/web/chart.js';

installDocument({ 'view-list': new Node('section'), 'view-cards': new Node('section') });
const { renderRow } = await import('../../src/web/render.js');

const ghostOf = (limit) => {
  const row = renderRow(limit);
  const bar = row.find((n) => n.className === 'bar');
  const ghost = bar.children.find((n) => n.className === 'bar-ghost');
  return ghost ? ghost.style.width : null;
};

const asNumbers = { kind: 'session', percent: 9, resets_at: null,
                    forecast: { percent_at_reset: 11 } };
const asStrings = { kind: 'session', percent: '9', resets_at: null,
                    forecast: { percent_at_reset: '11' } };

console.log('a limit at 9 % with a forecast of 11 % at reset');
console.log(`  percent as JSON numbers  -> forecast ghost: ${ghostOf(asNumbers)}`);
console.log(`  percent as decimal strings -> forecast ghost: ${ghostOf(asStrings)}`);
console.log();
console.log('the same two values through chart.js, which converts at its door:');
console.log(`  yOf(9)   = ${yOf(9)}     yOf('9')   = ${yOf('9')}`);
console.log(`  yOf(11)  = ${yOf(11)}    yOf('11')  = ${yOf('11')}`);
console.log();
console.log('render.js:83 is `fc.percent_at_reset > limit.percent`:');
console.log(`  11 > 9      -> ${11 > 9}`);
console.log(`  '11' > '9'  -> ${'11' > '9'}   <- string comparison, and the ghost is dropped`);
