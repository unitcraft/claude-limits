"""Guard for the page frame: no external resources, no inline code, tokens defined.

The three things that would each break the page silently:
  * an external URL — forbidden by 01.1 §0 and blocked by the CSP, and the artboard
    this page is modelled on DOES pull fonts from Google, so copying is a live risk;
  * an inline <style> or <script> — the CSP refuses them and the page renders blank;
  * a var(--x) with no definition — the property silently falls back to nothing.
"""
import pathlib, re, sys

# THE DEFAULT IS THIS CHECKOUT, found from this file -- not an absolute path typed in.
#
# It used to be `<repos>\claude-limits\src\web`, hard-coded. Run from a
# second clone, the guard read the FIRST clone's page and printed a verdict about it:
# `clean` for a tree the person had never looked at, with nothing in the output saying
# which files were read. The same shape of mistake as reading a stale log.
#
# Two things follow, and the second is why the first is not enough:
#   * the root is derived from __file__, so a clone judges itself;
#   * and the directory is PRINTED, always, so a verdict can be matched to a tree
#     even when someone passes an argument.
DEFAULT_WEB = pathlib.Path(__file__).resolve().parent.parent / "src" / "web"
web = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_WEB


def must_read(name):
    """Read a file the page cannot exist without, or refuse with a sentence.

    An unhandled FileNotFoundError says the same thing in six lines of traceback and
    leaves the reader to work out that the DIRECTORY was wrong rather than the file
    missing from a real page.
    """
    f = web / name
    if not f.is_file():
        print(f"judging: {web}")
        print("PAGE GUARD: FAILED")
        print(f"   {name} is not there. Either this is not a page directory, or the "
              f"page is missing a file it cannot work without.")
        sys.exit(1)
    return f.read_text(encoding="utf-8")


html = must_read("index.html")
css = must_read("app.css")
js = must_read("app.js")

bad = []

# 1. external resources anywhere
# A HOST, not a domain name. The pattern required the last label to be LETTERS, so
# `http://93.184.216.34/tracker.gif` produced `external references: 0` -- measured
# 2026-09-09. An address is the obvious way to fetch something without a name that
# anybody would recognise in a review, which makes it the case worth catching most.
#
# Three alternatives, in the order they occur in a URL: a dotted-quad address, a
# bracketed IPv6 address, and a name ending in a letter-only label.
EXTERNAL = re.compile(r"""(?:https?:)?//(?!\s)(?:
      \d{1,3}(?:\.\d{1,3}){3}                     # 93.184.216.34
    | \[[0-9A-Fa-f:]+\]                            # [2606:2800:220:1::]
    | [A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}
)""", re.X)
for name, text in (("index.html", html), ("app.css", css), ("app.js", js)):
    for m in EXTERNAL.finditer(text):
        line = text[:m.start()].count("\n") + 1
        # A URL inside a comment naming what NOT to do is the point, not a defect.
        ctx = text.splitlines()[line - 1]
        if ctx.strip().startswith(("*", "//", "<!--")) or "fonts.googleapis" in ctx and "not" in ctx.lower():
            continue
        bad.append(f"{name}:{line}: external reference {m.group(0)}")

# 2. inline code — checked on the markup with COMMENTS STRIPPED.
# Found by its own first run: the page carries a comment explaining that inline
# <style> and <script> are refused by the CSP, and the guard read that sentence as
# the very thing it forbids. A check that cannot tell code from prose about code
# cries wolf, and a guard that cries wolf gets switched off.
markup = re.sub(r"<!--.*?-->", "", html, flags=re.S)

# CASE-INSENSITIVE, and `src` matched as a WHOLE ATTRIBUTE. Measured 2026-09-09:
# three of four embedded-code forms walked past this check.
#
#   <SCRIPT>…</SCRIPT>          HTML tag names are case-insensitive; the pattern was not
#   <STYLE>…</STYLE>            same
#   <div onclick="…">           an event handler is inline script by another spelling,
#                               and nothing looked for one at all
#
# The fourth, `<script data-src="x">`, was caught -- but by the LOCAL-REFERENCE check
# below complaining that `x` does not exist, not by this rule. `\bsrc=` matches inside
# `data-src=` because a hyphen is a word boundary, so the negative lookahead read a
# script with a bogus attribute as an external one. Rename the attribute to something
# without a hyphen and it would have passed silently.
#
# A page whose whole security argument is "the CSP refuses inline code" needs this
# check to see the code the CSP would refuse -- all of it, not the lower-case quarter.
if re.search(r"<style[\s>]", markup, re.I):
    bad.append("index.html: inline <style> — the CSP refuses it")
if re.search(r"<script(?![^>]*(?<![-\w])src\s*=)[^>]*>", markup, re.I):
    bad.append("index.html: inline <script> — the CSP refuses it")

# Event-handler attributes are inline script with a different syntax, and the CSP
# refuses them for the same reason. Listed rather than matched by `on\w+=`, which
# would also hit legitimate attributes on custom elements.
for handler in ("onclick", "onload", "onerror", "onsubmit", "onchange", "oninput",
                "onmouseover", "onmouseout", "onfocus", "onblur", "onkeydown",
                "onkeyup", "onkeypress", "ondblclick", "oncontextmenu", "onwheel",
                "onscroll", "ontoggle", "onanimationend", "ontransitionend"):
    if re.search(r"[\s\"']" + handler + r"\s*=", markup, re.I):
        bad.append(f"index.html: inline event handler `{handler}=` — "
                   f"the CSP refuses it, and it is script by another spelling")

# 2b. every LOCAL reference must resolve to a file that exists.
#
#     The external check above and this one are two halves of one class: "the page
#     asks for something it cannot get". Only the first half was written, and the
#     miss was immediate -- index.html linked icon.svg for a day while no such file
#     existed, and the guard said "external references: 0" and called that clean.
#     A 404 for a favicon is quiet; a 404 for app.js is a blank page, and the same
#     blind spot covers both.
for m in re.finditer(r'(?:href|src)\s*=\s*["\']([^"\'#?]+)', markup):
    ref = m.group(1)
    if ref.startswith(("http:", "https:", "//", "data:", "mailto:")):
        continue                                  # the external check owns those
    if not (web / ref).exists():
        line = markup[:m.start()].count("\n") + 1
        bad.append(f"index.html:{line}: references {ref}, which does not exist")

# 3. every var(--x) used must be defined in :root -- OR set from the scripts, which
#    is a different animal and must not be forced into :root.
#
#    A design TOKEN lives in :root: one value for the whole page, and a typo in its
#    name is exactly what this check catches. A LOCAL custom property (`--line` on one
#    chart, `--swatch` on one legend square) is per-element by nature: it carries a
#    different value on every node, and a root definition for it would be a value
#    nobody ever reads. Requiring one would teach the next writer to declare a fake
#    default just to quiet the guard -- and a guard that trains people to lie to it is
#    worse than no guard.
#
#    So: a var() is accepted when the name is a root token, or when some script
#    actually sets it (`setProperty('--x'` / `--x: ` inside a style string). A name
#    that is neither is still the typo this check exists for.
used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
root = css.split(":root")[1].split("}")[0] if ":root" in css else ""
defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", root))

set_by_script = set()
for js in sorted(web.glob("*.js")):
    text = js.read_text(encoding="utf-8")
    set_by_script |= set(re.findall(r"setProperty\(\s*['\"](--[a-z0-9-]+)", text))
    set_by_script |= set(re.findall(r"`?\s*(--[a-z0-9-]+)\s*:", text))

for miss in sorted(used - defined - set_by_script):
    bad.append(f"app.css: var({miss}) used, not a :root token and set by no script")

# --- the live dot: colour is the acceptance of T2.21, so a machine holds it -------
#
# "with the server stopped the dot is grey ... once it starts, green". test-live.mjs
# holds the WORD the dot says; this holds the COLOUR, because a green dot over a dead
# backend is the most misleading state this page has, and no js test can see a stylesheet.
dot = re.search(r"\.live-dot\s*\{([^}]*)\}", css)
if not dot:
    bad.append("app.css: no .live-dot rule -- T2.21's dot has no colour at all")
elif "var(--live)" not in dot.group(1):
    bad.append("app.css: .live-dot does not paint itself with var(--live)")

for mode in ("polling", "connecting"):
    if not re.search(r'\.live\[data-state="%s"\][^{]*\.live-dot' % mode, css):
        bad.append(f'app.css: nothing repaints the dot for data-state="{mode}" '
                   f'-- it would stay green while the backend is unreachable')

print(f"judging: {web}")
print(f"tokens defined: {len(defined)}, tokens used: {len(used)}")
print(f"external references: {sum(1 for b in bad if 'external' in b)}")
print("PAGE GUARD:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
