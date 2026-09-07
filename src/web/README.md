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

## What this skeleton does and does not do

Does: view switching with the choice remembered per browser, the live indicator with
its degraded state, the freshness clock, the refresh button with its 429 handling,
the footer counts.

Does not: render a single limit row or account block — those are T2.20, and the
containers stay empty on purpose. It also never derives a number. Severity, the
elapsed share, the forecast and the reset captions all arrive ready from the
backend, so the SDL widget shows the same figures (01.1 §0).
