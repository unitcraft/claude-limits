// reorder.js — dragging and keyboard reordering of the cards view (task T2.22).
//
// A module of its own, and not part of app.js, for the same reason render.js is one:
// what goes wrong here is order arithmetic and rollback, and both can be exercised
// under node with a DOM stub (scripts/test-reorder.mjs). What CANNOT be tested that
// way — pixel geometry from getBoundingClientRect — is pushed out into `dropIndexFor`
// in format.js, which takes plain numbers and is tested directly.
//
// Everything here follows subplan 01.1 §4.1.
import { dropIndexFor, landingIndex } from './format.js';

const hasClass = (n, cls) =>
  !!n && typeof n.className === 'string' && n.className.split(' ').includes(cls);

/**
 * Wire a container of `.card` elements for reordering.
 *
 * `commit(emails)` must return a promise: it is the `PUT /api/config` of 01.3 §3.8,
 * and the rollback below hangs on being able to await it. `toast(text)` shows a
 * failure to the person.
 *
 * WHY THE ORDER IS APPLIED BEFORE THE SERVER AGREES. The alternative — wait for the
 * PUT, then move the card — puts a network round trip between the drop and the
 * result, and a card that snaps back for 200 ms before landing reads as a bug. So
 * the DOM moves at once, the order the drag started from is kept, and a refusal
 * restores it with a message. That is the sequence 01.1 §4.1 asks for: release ->
 * new order straight into the DOM, then PUT, error -> roll back and a toast.
 */
export function createReorder({ container, commit, toast }) {
  let grabbed = null;        // the card being moved, by pointer or by keyboard
  let before = null;         // e-mail order to restore if the server refuses
  let line = null;           // the drop indicator between cards
  let pointerMode = false;

  const cards = () => Array.from(container.children).filter((n) => hasClass(n, 'card'));
  const emails = () => cards().map((c) => c.dataset.email);
  const indexOf = (card) => cards().indexOf(card);

  // ------------------------------------------------------------ indicator --

  /**
   * Draw the drop line at `slot`, counted over ALL cards including the one being
   * dragged: the artboard leaves an empty outline where the card came from, so it
   * still occupies a place in the list while it is in the air.
   */
  function showLine(slot) {
    if (!line) {
      line = document.createElement('div');
      line.className = 'drop-line';
      line.setAttribute('aria-hidden', 'true');
    }
    const list = cards();
    container.insertBefore(line, list[slot] || null);
  }

  function hideLine() {
    if (line && line.remove) line.remove();
  }

  // ------------------------------------------------------------ the move ---

  /** Put `card` at index `to` of the list WITHOUT it. The one place order changes. */
  function place(card, to) {
    const rest = cards().filter((c) => c !== card);
    container.insertBefore(card, rest[to] || null);
  }

  function start(card) {
    grabbed = card;
    before = emails();
    card.dataset.grabbed = 'true';
  }

  /**
   * Finish a move: keep the new order on screen and ask the server for it. A refusal
   * restores the order the drag STARTED from — not the one before the last step,
   * which is what a naive undo would give after several keyboard moves.
   */
  async function finish() {
    const card = grabbed;
    if (!card) return;
    delete card.dataset.grabbed;
    hideLine();
    grabbed = null;
    pointerMode = false;

    const now = emails();
    const was = before;
    before = null;
    if (!was || now.join(' ') === was.join(' ')) return;   // nothing actually moved

    try {
      await commit(now);
    } catch {
      restore(was);
      if (toast) toast('could not save order');
    }
  }

  /**
   * Reinstate an e-mail order in the DOM, ignoring cards that have since vanished —
   * a snapshot can arrive between the drop and the refusal, and an account that is
   * no longer there must not resurrect as an empty node.
   */
  function restore(order) {
    const byEmail = new Map(cards().map((c) => [c.dataset.email, c]));
    for (const email of order) {
      const card = byEmail.get(email);
      if (card) container.insertBefore(card, null);   // insert at the end = reorder
    }
  }

  function cancel() {
    const card = grabbed;
    if (!card) return;
    delete card.dataset.grabbed;
    hideLine();
    const was = before;
    grabbed = null;
    before = null;
    pointerMode = false;
    if (was) restore(was);
  }

  // ------------------------------------------------------------- keyboard --
  //
  // 01.1 §4.1: the handle is focusable, Space takes, arrows move, Space puts down,
  // Esc cancels. Enter counts as Space because a button fires a click on both and a
  // person who has just tabbed to a control reaches for Enter first.

  function onKeyDown(e) {
    const handle = hasClass(e.target, 'card-handle') ? e.target : null;
    if (!handle) return;
    const card = handle.parentElement || handle.parent;
    if (!card) return;

    if (e.key === ' ' || e.key === 'Enter' || e.key === 'Spacebar') {
      e.preventDefault();
      if (grabbed === card) finish();
      else if (!grabbed) start(card);
      return;
    }
    if (e.key === 'Escape') { e.preventDefault(); cancel(); return; }
    if (grabbed !== card) return;
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;

    e.preventDefault();
    const from = indexOf(card);
    const to = from + (e.key === 'ArrowDown' ? 1 : -1);
    if (to < 0 || to >= cards().length) return;      // at an end: stay, do not wrap
    place(card, to);
    if (handle.focus) handle.focus();                // the DOM move drops focus
  }

  // -------------------------------------------------------------- pointer --
  //
  // HTML5 drag-and-drop is the primary mechanism (01.1 §4.1); pointer events are the
  // fallback for touch, where dragstart never fires. Both end in the same `place` +
  // `finish`, so an off-by-one cannot exist in one path and not the other.

  const slotFromY = (y) => dropIndexFor(cards().map((c) => c.getBoundingClientRect()), y);

  function drop(card, y) {
    place(card, landingIndex(indexOf(card), slotFromY(y)));
    finish();
  }

  function onPointerDown(e) {
    if (!hasClass(e.target, 'card-handle')) return;
    if (e.pointerType === 'mouse') return;           // mouse goes through HTML5 DnD
    const card = e.target.parentElement;
    if (!card) return;
    pointerMode = true;
    start(card);
    if (e.target.setPointerCapture) e.target.setPointerCapture(e.pointerId);
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (!pointerMode || !grabbed) return;
    showLine(slotFromY(e.clientY));
  }

  function onPointerUp(e) {
    if (!pointerMode || !grabbed) return;
    drop(grabbed, e.clientY);
  }

  // ----------------------------------------------------------- HTML5 drag --

  function onMouseDown(e) {
    // A card becomes draggable only while the pointer is on its handle: a card
    // draggable everywhere would swallow text selection inside it.
    if (hasClass(e.target, 'card-handle')) {
      const card = e.target.parentElement;
      if (card) card.draggable = true;
    }
  }

  function onDragStart(e) {
    const card = e.target;
    if (!hasClass(card, 'card')) return;
    start(card);
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      // Firefox refuses to start a drag with nothing on the transfer.
      e.dataTransfer.setData('text/plain', card.dataset.email || '');
    }
  }

  function onDragOver(e) {
    if (!grabbed) return;
    e.preventDefault();                              // "yes, you may drop here"
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    showLine(slotFromY(e.clientY));
  }

  function onDrop(e) {
    if (!grabbed) return;
    e.preventDefault();
    const card = grabbed;
    card.draggable = false;
    drop(card, e.clientY);
  }

  function onDragEnd() {
    // Fires after a drop and after an abandoned drag alike. If `onDrop` already ran,
    // `grabbed` is null and this does nothing; otherwise the card was dropped
    // outside the container and the order goes back.
    if (grabbed) { grabbed.draggable = false; cancel(); }
  }

  function attach() {
    container.addEventListener('keydown', onKeyDown);
    container.addEventListener('mousedown', onMouseDown);
    container.addEventListener('pointerdown', onPointerDown);
    container.addEventListener('pointermove', onPointerMove);
    container.addEventListener('pointerup', onPointerUp);
    container.addEventListener('dragstart', onDragStart);
    container.addEventListener('dragover', onDragOver);
    container.addEventListener('drop', onDrop);
    container.addEventListener('dragend', onDragEnd);
  }

  // The handlers are returned as well as attached: the tests drive them directly,
  // because a stub that faithfully reproduced event dispatch would be a browser.
  return { attach, onKeyDown, onDragStart, onDragOver, onDrop, onDragEnd, cancel, emails };
}
