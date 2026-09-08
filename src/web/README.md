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

## The guard checks both halves of "asks for something it cannot get"

It counted external references and stopped there — so `index.html` linked `icon.svg`
for a day while no such file existed, and the guard printed `external references: 0`
and called that clean. A missing favicon is a quiet 404; a typo in the `app.js` path
is a blank page, and the same blind spot covered both. Local `href`/`src` targets are
now resolved against this directory, and the reverse probe is one line: rename the
file, watch the guard redden.

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
state and its own reconnect schedule; the freshness clock; the refresh button with
its 429 handling; the footer counts; the list view — account blocks with their states
and one row per limit window (name, bar, percent, reset caption, elapsed-time strip);
the cards view with drag and keyboard reordering; the statistics views; and the
settings panel, including what it does when the file changes underneath it.

Does not yet: the forecast ghost beyond drawing it when the backend supplies one, and
anything that needs the history endpoints — those are T2.15, and the statistics views
read fixtures until it lands.

## Running the checks

One command, and it is the only one worth remembering:

    node scripts/check-web.mjs

It DISCOVERS the suites rather than listing them, runs the page guard after them, and
judges every one by its exit code rather than by the summary it prints. All three
properties were bought with real defects: a hand-written list quietly measures less
each time a suite is added, and `test-render.mjs` spent a day printing a green
summary line before its last test had run.

Until 2026-09-08 there was no such command and no CI in this repository, so the page
was judged by a person typing nine commands from memory. That is a habit, not an
acceptance, and habits stop holding exactly when the work gets interesting.

**`format.js` is separate for a reason.** The arithmetic of a row — the elapsed
share, the whole-cell geometry, the duration wording — is exactly the kind that is
wrong in a way nobody notices on screen. It takes no DOM and is tested under node
(`scripts/test-format.mjs`, run for you by the command above).

Both directions where it matters. The suite has already earned its
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
