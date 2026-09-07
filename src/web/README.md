# src/web — the page, embedded in the binary

Three files, served from `embed_dir("web")`: `index.html`, `app.css`, `app.js`.
Not one file: the CSP refuses inline `<style>` and `<script>` (subplan 01.3 §1), and
a page built as one renders blank. Reasoning: subplan 01.1 §0.

`scripts/check-page.py` guards the three things that break the page silently: an
external URL, an inline block, and a `var(--x)` that is never defined. Its own first
run caught a false positive worth keeping in mind — it read the comment *explaining*
that inline blocks are forbidden as an inline block. It now strips comments first: a
check that cannot tell code from prose about code cries wolf, and a guard that cries
wolf gets switched off.

## Fonts are an open item, and the page does not wait for them

The design artboard loads Manrope and JetBrains Mono from `fonts.googleapis.com`.
**The page must not**, and copying that `<link>` is the likeliest mistake here: it
breaks the no-external-resources rule, and the CSP blocks it anyway — so the fonts
would quietly fail to arrive rather than fail loudly.

The `.woff2` files are not in the repository yet. Until they are, the stacks in
`app.css` fall back to the artboard's own second choices — Segoe UI / system-ui and
Cascadia Mono / Consolas — so the page reads correctly today. Adding the files later
is one `@font-face` block and touches nothing else.

Both families are open-licensed (SIL OFL), so shipping them is allowed; obtaining
the binaries is the part still to do, and it is deliberately not a blocker.

## What is here and what is not

Does: view switching remembered per browser; the live indicator with its degraded
state; the freshness clock; the refresh button with its 429 handling; the footer
counts; and, since T2.20, the list view — account blocks with their states and one
row per limit window (name, bar, percent, reset caption, elapsed-time strip).

Does not yet: the cards and statistics views, the settings panel, the forecast ghost
beyond drawing it when the backend supplies one.

**`format.js` is separate for a reason.** The arithmetic of a row — the elapsed
share, the whole-cell geometry, the duration wording — is exactly the kind that is
wrong in a way nobody notices on screen. It takes no DOM and is tested under node:

    node scripts/test-format.mjs

Seventeen checks, both directions where it matters. The suite has already earned its
keep twice: it caught its own wrong invariant (a zero-width fill is legal, not a
clipped cell), and a reverse probe swapping `round` for `floor` in the cell geometry
is caught immediately.

One spec behaviour is pinned there on purpose rather than left to chance: below half
a cell of usage the bar shows nothing, because 01.1 §2.2 says `round()`. The percent
beside the bar still reads the true number, so nothing is hidden — but if that ever
reads wrong, the change belongs in the spec first, not in the renderer.

The page still derives no figure of its own beyond the elapsed share, which 01.1
§2.6 explicitly assigns to it. Severity, the forecast and the reset captions arrive
ready from the backend so the SDL widget shows the same numbers.
