// Does a rejected `fetch` on the refresh button tell the person anything?
//
//   node probes/hunt-conventions-silent-failure-refresh/measure.mjs
//
// THE DEFECT, until 2026-09-09. `refresh()` was `try { ... } finally { ... }` with no
// `catch`. When fetch rejects -- backend down, socket refused, DNS gone -- the
// spinner stopped and nothing else happened. The page then looked exactly as it does
// on success with no news: unchanged. Four of the five handlers in app.js already had
// a catch, and that is what made the fifth look finished rather than forgotten.
//
// api.md:26 -- "no silent outcomes".
//
// This probe does not import app.js: that module reaches for `document` at load. It
// reproduces the two shapes side by side and asserts the difference, which is the
// property under test -- whether a rejection reaches the person at all.

const said = [];
const toast = (t) => said.push(t);

// The shape as it was.
async function refreshOld(fetchImpl) {
  const btn = { dataset: {} };
  btn.dataset.spinning = 'true';
  try {
    await fetchImpl('/api/snapshot/refresh', { method: 'POST' });
  } finally {
    btn.dataset.spinning = 'false';
  }
}

// The shape as it is.
async function refreshNew(fetchImpl) {
  const btn = { dataset: {} };
  btn.dataset.spinning = 'true';
  try {
    await fetchImpl('/api/snapshot/refresh', { method: 'POST' });
  } catch (e) {
    toast(`could not reach the backend (${e.message})`);
  } finally {
    btn.dataset.spinning = 'false';
  }
}

const refuses = () => Promise.reject(new Error('Failed to fetch'));

let bad = 0;

// The old shape: the rejection escapes as an unhandled promise and the person is
// told nothing. Catch it here so the probe itself does not die on it.
said.length = 0;
let escaped = false;
await refreshOld(refuses).catch(() => { escaped = true; });
console.log('old shape -> said:', JSON.stringify(said), ' rejection escaped:', escaped);
if (said.length !== 0) {
  console.log('  FAIL: the old shape is supposed to say nothing; the probe models it wrong');
  bad = 1;
}
if (!escaped) {
  console.log('  FAIL: the old shape should let the rejection escape unhandled');
  bad = 1;
}

// The new shape: the person is told, and nothing escapes.
said.length = 0;
escaped = false;
await refreshNew(refuses).catch(() => { escaped = true; });
console.log('new shape -> said:', JSON.stringify(said), ' rejection escaped:', escaped);
if (said.length !== 1 || !said[0].includes('could not reach the backend')) {
  console.log('  FAIL: a rejected fetch must reach the person');
  bad = 1;
}
if (escaped) {
  console.log('  FAIL: the rejection should be handled, not rethrown');
  bad = 1;
}

// And the shape in the file must be the new one. A probe that only compares two
// local copies proves nothing about the page, so read the source and check.
const src = await (await import('node:fs/promises')).readFile(
  new URL('../../src/web/app.js', import.meta.url), 'utf8');
const body = src.slice(src.indexOf('async function refresh(btn)'));
const end = body.indexOf('\n}\n');
const fn = body.slice(0, end);
if (!/\}\s*catch\s*\(/.test(fn)) {
  console.log('  FAIL: refresh() in app.js has no catch — the defect is back');
  bad = 1;
} else if (!/toast\(/.test(fn)) {
  console.log('  FAIL: refresh() catches but tells nobody');
  bad = 1;
} else {
  console.log('app.js refresh(): has a catch, and it calls toast');
}

console.log(bad ? '\nFAILED' : '\nOK: a rejected refresh reaches the person');
process.exit(bad);
