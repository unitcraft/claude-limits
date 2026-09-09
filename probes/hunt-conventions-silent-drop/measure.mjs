// Where does a settings control's value actually go?
//
//   node probes/hunt-conventions-silent-drop/measure.mjs
//
// THE DEFECT, until 2026-09-09. `collect()` decided a control's destination by
// matching the LAST SEGMENT of its path against BROWSER_ONLY. Two things were wrong
// with that at the same time:
//
//   * `ui.countdown` matched, so it was dropped from the PUT body -- and nothing
//     picked it up afterwards. Toggling it produced an empty body, Save closed the
//     panel, and localStorage was never written. The switch moved and nothing
//     happened, which api.md:26 forbids in as many words.
//
//   * `view` is in that list, so the first config key ever spelled `widget.view`
//     would have been swallowed the same way -- silently, and for a completely
//     unrelated reason.
//
// A leaf name is not an address. Controls now carry data-store="browser", and the
// two halves are collected separately.
//
// 01.1 lines 300-301 are the authority: countdown -> localStorage.countdown,
// hide_stale -> `[ui] hide_stale` in the config file. Two switches, one section,
// different destinations.
import { collect, collectBrowser, BROWSER_ONLY } from '../../src/web/settings.js';

// A panel is a DOM tree; this is the smallest stand-in that the two functions use.
function stub(controls) {
  const nodes = controls.map((c) => ({
    dataset: { path: c.path, ...(c.store ? { store: c.store } : {}) },
    getAttribute: (k) => (k === 'aria-checked' ? String(!!c.on) : null),
    value: c.value ?? '',
    className: c.kind,
  }));
  return {
    querySelectorAll(sel) {
      const want = sel.replace('.', '');
      return nodes.filter((n) => n.className === want);
    },
    querySelector() { return null; },
  };
}

const panel = stub([
  { kind: 'toggle', path: 'ui.countdown', on: true, store: 'browser' },
  { kind: 'toggle', path: 'ui.hide_stale', on: true },
  // The key the old filter would have eaten for an unrelated reason.
  { kind: 'toggle', path: 'widget.view', on: true },
]);

const cfg = collect(panel);
const browser = collectBrowser(panel);

console.log('config tree  :', JSON.stringify(cfg));
console.log('browser part :', JSON.stringify(browser));

let bad = 0;
const check = (c, m) => { if (!c) { console.log('  FAIL:', m); bad = 1; } };

// The browser setting reaches the browser half and NOT the config body.
check(browser.countdown === true, 'countdown did not reach the browser half');
check(!(cfg.ui && 'countdown' in cfg.ui),
      'countdown leaked into the config body -- the backend answers 422 extra_forbidden');

// Its neighbour, in the same section, goes the other way.
check(cfg.ui && cfg.ui.hide_stale === true,
      'hide_stale did not reach the config body, but 01.1:301 puts it there');
check(!('hide_stale' in browser), 'hide_stale leaked into the browser half');

// And the key that the leaf-name filter would have eaten.
check(cfg.widget && cfg.widget.view === true,
      'widget.view was dropped -- the destination is being decided by leaf name again');

// The list is now documentation, and must still describe the panel. If a control
// gains data-store="browser" without being named here, the record has drifted.
check(BROWSER_ONLY.includes('countdown'),
      'BROWSER_ONLY no longer lists countdown, though the control declares it');

console.log(bad ? '\nFAILED' : '\nOK: each control goes where it declares, not where its name suggests');
process.exit(bad);
