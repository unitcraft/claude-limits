// A DOM small enough to read and faithful in the places the page depends on.
//
// Shared by test-render.mjs and test-reorder.mjs. It implements only what src/web
// actually touches; anything else is deliberately absent so that a renderer reaching
// for a new API fails loudly here rather than passing on a shim that quietly does
// nothing.
//
// THE ONE THING IT MUST GET RIGHT is that insertBefore and append MOVE a node that
// already has a parent. Both reorder.js and render.js reorder by re-inserting nodes
// they have already placed; a stub that merely pushed would show every moved card
// twice and every test about order would be measuring a fiction.

export class Node {
  constructor(tag) {
    this.tag = tag;
    this.className = '';
    this._text = '';
    this.children = [];
    this.dataset = {};
    // Enough of CSSStyleDeclaration for the page: named properties assigned
    // directly, plus setProperty for the custom ones (`--swatch`, `--line`), which
    // cannot be assigned as fields at all in a real DOM.
    this.style = {
      _custom: {},
      setProperty(k, v) { this._custom[k] = String(v); },
      getPropertyValue(k) { return this._custom[k] ?? ''; },
    };
    this.attrs = {};
    this.title = '';
    this.parent = null;
    this.listeners = {};
    this.focused = false;
  }

  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text || this.children.map((c) => c.textContent).join(' '); }

  get parentElement() { return this.parent; }

  _adopt(n) {
    if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1);
    n.parent = this;
    return n;
  }

  append(...kids) { for (const k of kids) this.children.push(this._adopt(k)); }
  prepend(...kids) { for (const k of kids.reverse()) this.children.unshift(this._adopt(k)); }

  insertBefore(n, ref) {
    // The reference index is taken BEFORE the node is detached: detaching first
    // would shift it when the node being moved sits earlier in the same parent.
    const i = ref ? this.children.indexOf(ref) : this.children.length;
    const wasEarlier = n.parent === this && this.children.indexOf(n) < i;
    this._adopt(n);
    this.children.splice(wasEarlier ? i - 1 : i, 0, n);
    return n;
  }

  /** Sibling insert, as the DOM has it: node.after(x) puts x right behind node. */
  after(...kids) {
    const p = this.parent;
    if (!p) return;
    let ref = p.children[p.children.indexOf(this) + 1] || null;
    for (const k of kids) { p.insertBefore(k, ref); ref = p.children[p.children.indexOf(k) + 1] || null; }
  }

  replaceWith(n) {
    const p = this.parent;
    if (!p) return;
    const i = p.children.indexOf(this);
    if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1);
    p.children[i] = n;
    n.parent = p;
    this.parent = null;
  }

  remove() {
    const p = this.parent;
    if (!p) return;
    p.children.splice(p.children.indexOf(this), 1);
    this.parent = null;
  }

  replaceChildren(...kids) {
    for (const c of this.children) c.parent = null;
    this.children = [];
    this.append(...kids);
  }

  // `class` is mirrored into className because that is what selector matching reads
  // here, and SVG elements are built with setAttribute('class', ...) — in a real DOM
  // an SVG element's className is not a string, and querySelector('.chart') still
  // works off the attribute. Without the mirror every SVG lookup would find nothing.
  setAttribute(k, v) {
    this.attrs[k] = String(v);
    if (k === 'class') this.className = String(v);
  }
  getAttribute(k) { return this.attrs[k] ?? null; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  focus() { this.focused = true; }

  querySelector(sel) { return this.find((n) => matches(n, sel)); }
  querySelectorAll(sel) { return this.all((n) => matches(n, sel)); }

  find(pred) {
    for (const c of this.children) {
      if (pred(c)) return c;
      const d = c.find(pred);
      if (d) return d;
    }
    return null;
  }

  all(pred, out = []) {
    for (const c of this.children) { if (pred(c)) out.push(c); c.all(pred, out); }
    return out;
  }

  /**
   * Cards are laid out 100 px apart from y=0, which is all dropIndexFor needs.
   *
   * The index counts only siblings of the SAME class, so inserting the drop
   * indicator between two cards does not shift every card's geometry by one slot —
   * which it would if the position were taken among all children, and every drag
   * test would then be measuring the indicator rather than the cards.
   */
  getBoundingClientRect() {
    const peers = this.parent
      ? this.parent.children.filter((n) => n.className === this.className)
      : [this];
    const i = Math.max(0, peers.indexOf(this));
    return { top: i * 100, bottom: i * 100 + 90, left: 0, right: 342 };
  }

  get clientWidth() { return 342; }
}

/**
 * `.class`, `tag`, and `[data-x]` / `[data-x="v"]`.
 *
 * The attribute form is here because the page uses it and the stub did not: every
 * querySelectorAll('[data-path]') quietly returned nothing, which made showErrors
 * paint nothing AND made the test for unmatched errors pass for the wrong reason —
 * it found no paths, so every error looked unmatched. A selector the stub cannot
 * parse must never silently mean "no elements".
 */
export const matches = (n, sel) => {
  if (sel.startsWith('.')) return String(n.className).split(' ').includes(sel.slice(1));
  if (sel.startsWith('[')) {
    const m = /^\[([a-z-]+)(?:=["']?([^"'\]]*)["']?)?\]$/.exec(sel);
    if (!m) throw new Error(`dom-stub: selector not supported: ${sel}`);
    const key = m[1].startsWith('data-')
      ? m[1].slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())
      : m[1];
    const have = m[1].startsWith('data-') ? n.dataset[key] : n.attrs[m[1]];
    return m[2] === undefined ? have !== undefined : String(have) === m[2];
  }
  if (/[.[\]=#\s]/.test(sel)) throw new Error(`dom-stub: selector not supported: ${sel}`);
  return n.tag === sel;
};

/**
 * Install a document whose getElementById answers from `views`, keyed by id.
 * Returns the created body so a test can inspect what was appended to it.
 */
export function installDocument(views = {}) {
  const body = new Node('body');
  // The views live INSIDE the body, as they do on the page: layoutCells sweeps
  // document.querySelectorAll('.bar'), and a view parked outside the body would make
  // that sweep silently find nothing.
  for (const v of Object.values(views)) body.append(v);
  globalThis.document = {
    createElement: (t) => new Node(t),
    createElementNS: (ns, t) => { const n = new Node(t); n.ns = ns; return n; },
    getElementById: (id) => views[id] || null,
    querySelectorAll: (sel) => body.all((n) => matches(n, sel)),
    body,
  };
  return body;
}
