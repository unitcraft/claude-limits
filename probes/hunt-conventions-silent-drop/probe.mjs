// What the settings panel does with a value it will not send.
//
// `collect()` filters by the LAST SEGMENT of a control's path against BROWSER_ONLY
// (settings.js:293-299). Nothing tells the person. The header of the file explains
// the filter as protection against `422 extra_forbidden` -- that is, the loud refusal
// the API convention prescribes is replaced by a silent drop on the client.
//
// Run:  node probe.mjs
import { readFileSync, readdirSync } from 'node:fs';
import { Node, installDocument } from '../../scripts/dom-stub.mjs';

installDocument({});
const S = await import('../../src/web/settings.js');
const reply = JSON.parse(readFileSync(new URL('../../fixtures/api/config.json', import.meta.url)));
const at = (panel, path) => panel.all((n) => n.dataset && n.dataset.path === path)[0];
const flip = (n) => n.setAttribute('aria-checked', String(n.getAttribute('aria-checked') !== 'true'));

console.log('BROWSER_ONLY =', JSON.stringify(S.BROWSER_ONLY));
console.log();

// --- A. a control the person can flip, whose value goes nowhere ---------------
{
  const panel = S.renderSettings(reply);
  const t = at(panel, 'ui.countdown');
  console.log('A. the "Reset time / show countdown" toggle (settings.js:169-170)');
  console.log(`   present in the panel : ${!!t}`);
  flip(t);
  console.log(`   flipped, now         : aria-checked=${t.getAttribute('aria-checked')}`);
  console.log(`   body of the PUT      : ${JSON.stringify(S.bodyOf(panel))}`);
  console.log(`   isEmptyDiff -> Save closes the panel without a request: ${S.isEmptyDiff(S.bodyOf(panel))}`);
  // and the other half: does anything in the page write it to localStorage?
  const web = new URL('../../src/web/', import.meta.url);
  const writers = [];
  for (const f of readdirSync(web).filter((x) => x.endsWith('.js'))) {
    const text = readFileSync(new URL(f, web), 'utf8');
    for (const m of text.matchAll(/localStorage\.(setItem|getItem)\(\s*'([^']+)'/g)) {
      writers.push(`${f}: localStorage.${m[1]}('${m[2]}')`);
    }
  }
  console.log('   every localStorage key the page touches:');
  for (const w of writers) console.log(`     ${w}`);
  console.log(`   any of them "countdown"? ${writers.some((w) => w.includes("'countdown'"))}`);
}

// --- B. a control the panel CALLS browser-only and sends to the file ----------
{
  const panel = S.renderSettings(reply);
  const notes = panel.all((n) => n.className === 'settings-note').map((n) => n.textContent);
  console.log();
  console.log('B. the same section is captioned (settings.js:168):');
  console.log(`   "${notes[0]}"`);
  flip(at(panel, 'ui.hide_stale'));
  console.log(`   flipping "Hide logins with an expired token" gives a body of`);
  console.log(`   ${JSON.stringify(S.bodyOf(panel))}   <- into the config FILE`);
}

// --- C. the filter matches a leaf name anywhere in the tree -------------------
{
  const panel = S.renderSettings(reply);
  const box = panel.all((n) => n.className === 'settings-section')[0];
  const made = new Node('input');
  made.className = 'input';
  made.setAttribute('type', 'text');
  made.dataset.path = 'widget.view';         // a future setting, nothing to do with the page view
  made.value = 'compact';
  box.append(made);
  const body = S.collect(panel);
  console.log();
  console.log('C. a control at path `widget.view` (leaf `view` is in BROWSER_ONLY):');
  console.log(`   collect() returns widget = ${JSON.stringify(body.widget)}`);
  console.log('   the filter is `BROWSER_ONLY.includes(parts[parts.length - 1])`,');
  console.log('   so ANY future setting whose leaf is view/bar_style/countdown/');
  console.log('   stats_range/stats_group disappears from the save without a word.');
}
