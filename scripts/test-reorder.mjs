// Behaviour test for the cards reordering (task T2.22), under node.
//
//   node scripts/test-reorder.mjs
//
// The acceptance in 01.5 is "the order survives a reload; a 412 rolls back and
// toasts; keyboard moving per 01.1 §10" — and every one of those is a sequence, not
// a picture. A screenshot cannot show that Esc after three arrow presses returns to
// where the drag STARTED, or that a card dropped downwards lands one slot short
// because the list closed up behind it. Those are the two bugs this file exists for.
//
// The handlers are called directly rather than dispatched: a stub that reproduced
// event dispatch, capture and default actions would be a browser, and the thing
// under test is the order arithmetic, not the event system.
import assert from 'node:assert/strict';
import { Node, installDocument } from './dom-stub.mjs';

const view = new Node('section');
installDocument({ 'view-cards': view });
const { createReorder } = await import('../src/web/reorder.js');

// ------------------------------------------------------------------ harness --

const EMAILS = ['a@x.com', 'b@x.com', 'c@x.com', 'd@x.com'];

/** A fresh view of four cards, plus a controller whose commit is recordable. */
function fresh({ fail = false } = {}) {
  view.replaceChildren();
  const handles = [];
  for (const email of EMAILS) {
    const card = new Node('article');
    card.className = 'card';
    card.dataset.email = email;
    const handle = new Node('button');
    handle.className = 'card-handle';
    card.append(handle);
    handles.push(handle);
    view.append(card);
  }
  const seen = { commits: [], toasts: [] };
  const r = createReorder({
    container: view,
    commit: async (emails) => {
      seen.commits.push(emails);
      if (fail) throw new Error('412');
    },
    toast: (t) => seen.toasts.push(t),
  });
  return { r, seen, handles };
}

const order = () => view.children.filter((n) => n.className === 'card').map((n) => n.dataset.email);
const key = (target, k) => ({ target, key: k, preventDefault() {} });
const drag = (target, y) => ({
  target, clientY: y, preventDefault() {},
  dataTransfer: { setData() {}, effectAllowed: '', dropEffect: '' },
});

let passed = 0;
const test = async (name, fn) => {
  try { await fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

console.log('keyboard reordering (01.1 §4.1, §10)');

await test('Space takes the card, and the card says so', async () => {
  const { r, handles } = fresh();
  r.onKeyDown(key(handles[0], ' '));
  assert.equal(view.children[0].dataset.grabbed, 'true');
});

await test('arrows move the card and Space puts it down', async () => {
  const { r, seen, handles } = fresh();
  r.onKeyDown(key(handles[0], ' '));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  assert.deepEqual(order(), ['b@x.com', 'a@x.com', 'c@x.com', 'd@x.com']);
  r.onKeyDown(key(handles[0], ' '));
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(seen.commits, [['b@x.com', 'a@x.com', 'c@x.com', 'd@x.com']]);
  assert.equal(view.children[1].dataset.grabbed, undefined, 'the card is put down');
});

await test('the handle keeps focus across the move', async () => {
  const { r, handles } = fresh();
  r.onKeyDown(key(handles[2], ' '));
  r.onKeyDown(key(handles[2], 'ArrowUp'));
  assert.equal(handles[2].focused, true, 'moving the node in the DOM drops focus by itself');
});

await test('Esc returns to where the drag STARTED, not one step back', async () => {
  const { r, seen, handles } = fresh();
  r.onKeyDown(key(handles[0], ' '));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  assert.deepEqual(order(), ['b@x.com', 'c@x.com', 'd@x.com', 'a@x.com']);
  r.onKeyDown(key(handles[0], 'Escape'));
  assert.deepEqual(order(), EMAILS, 'three moves, one Esc, all the way back');
  assert.deepEqual(seen.commits, [], 'a cancelled move is not saved');
});

await test('an arrow at the end does not wrap around', async () => {
  const { r, handles } = fresh();
  r.onKeyDown(key(handles[0], ' '));
  r.onKeyDown(key(handles[0], 'ArrowUp'));
  assert.deepEqual(order(), EMAILS, 'the first card stays first');
  r.onKeyDown(key(handles[0], 'Escape'));
  r.onKeyDown(key(handles[3], ' '));
  r.onKeyDown(key(handles[3], 'ArrowDown'));
  assert.deepEqual(order(), EMAILS, 'and the last stays last');
});

await test('taking and putting down without moving sends nothing', async () => {
  const { r, seen, handles } = fresh();
  r.onKeyDown(key(handles[1], ' '));
  r.onKeyDown(key(handles[1], ' '));
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(seen.commits, [], 'a PUT that changes nothing still costs a 412 later');
});

await test('a key on something that is not a handle is ignored', async () => {
  const { r, seen } = fresh();
  r.onKeyDown(key(view.children[0], ' '));
  assert.equal(view.children[0].dataset.grabbed, undefined);
  assert.deepEqual(seen.commits, []);
});

console.log('\nrefusal and rollback (01.1 §4.1)');

await test('a refused order rolls back and says so', async () => {
  const { r, seen, handles } = fresh({ fail: true });
  r.onKeyDown(key(handles[0], ' '));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  r.onKeyDown(key(handles[0], ' '));
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(seen.commits.length, 1, 'it was attempted');
  assert.deepEqual(order(), EMAILS, 'and undone');
  assert.deepEqual(seen.toasts, ['could not save order']);
});

await test('a rollback survives an account vanishing in the meantime', async () => {
  const { r, seen, handles } = fresh({ fail: true });
  r.onKeyDown(key(handles[0], ' '));
  r.onKeyDown(key(handles[0], 'ArrowDown'));
  view.children.find((n) => n.dataset.email === 'd@x.com').remove();
  r.onKeyDown(key(handles[0], ' '));
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(order(), ['a@x.com', 'b@x.com', 'c@x.com'], 'no ghost card resurrected');
  assert.deepEqual(seen.toasts, ['could not save order']);
});

console.log('\npointer drag (01.1 §4.1)');

await test('the drop line lands in the slot the pointer is over', async () => {
  const { r } = fresh();
  const card = view.children[0];
  r.onDragStart(drag(card, 10));
  r.onDragOver(drag(card, 160));       // between the second and the third card
  const kinds = view.children.map((n) => n.className);
  assert.deepEqual(kinds, ['card', 'card', 'drop-line', 'card', 'card']);
});

await test('dropping downwards lands where the line was, not one short', async () => {
  const { r, seen } = fresh();
  const card = view.children[0];
  r.onDragStart(drag(card, 10));
  r.onDragOver(drag(card, 160));
  r.onDrop(drag(card, 160));
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(order(), ['b@x.com', 'a@x.com', 'c@x.com', 'd@x.com'],
    'the classic off-by-one: the list closes up behind the card as it leaves');
  assert.deepEqual(seen.commits, [['b@x.com', 'a@x.com', 'c@x.com', 'd@x.com']]);
  assert.equal(view.children.length, 4, 'the drop line is gone');
});

await test('dropping upwards needs no correction', async () => {
  const { r } = fresh();
  const card = view.children[3];
  r.onDragStart(drag(card, 310));
  r.onDrop(drag(card, 60));            // above the second card, below the first
  await new Promise((res) => setTimeout(res, 0));
  assert.deepEqual(order(), ['a@x.com', 'd@x.com', 'b@x.com', 'c@x.com']);
});

await test('a drag abandoned outside the list puts the order back', async () => {
  const { r, seen } = fresh();
  const card = view.children[0];
  r.onDragStart(drag(card, 10));
  r.onDragOver(drag(card, 260));
  r.onDragEnd();
  assert.deepEqual(order(), EMAILS);
  assert.deepEqual(seen.commits, []);
  assert.equal(view.children.length, 4, 'and takes its drop line with it');
});

await test('dragover before any dragstart does nothing at all', async () => {
  const { r } = fresh();
  r.onDragOver(drag(view.children[0], 160));
  assert.equal(view.children.length, 4, 'no orphan drop line from a drag we did not start');
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
