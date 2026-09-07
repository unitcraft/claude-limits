"""Guard for the page frame: no external resources, no inline code, tokens defined.

The three things that would each break the page silently:
  * an external URL — forbidden by 01.1 §0 and blocked by the CSP, and the artboard
    this page is modelled on DOES pull fonts from Google, so copying is a live risk;
  * an inline <style> or <script> — the CSP refuses them and the page renders blank;
  * a var(--x) with no definition — the property silently falls back to nothing.
"""
import pathlib, re, sys

web = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                   else r"<repos>\claude-limits\src\web")
html = (web / "index.html").read_text(encoding="utf-8")
css = (web / "app.css").read_text(encoding="utf-8")
js = (web / "app.js").read_text(encoding="utf-8")

bad = []

# 1. external resources anywhere
EXTERNAL = re.compile(r"""(?:https?:)?//(?!\s)[A-Za-z0-9.-]+\.[A-Za-z]{2,}""")
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
if re.search(r"<style[\s>]", markup):
    bad.append("index.html: inline <style> — the CSP refuses it")
if re.search(r"<script(?![^>]*\bsrc=)[^>]*>", markup):
    bad.append("index.html: inline <script> — the CSP refuses it")

# 3. every var(--x) used must be defined in :root
used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
root = css.split(":root")[1].split("}")[0] if ":root" in css else ""
defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", root))
for miss in sorted(used - defined):
    bad.append(f"app.css: var({miss}) used but never defined in :root")

print(f"tokens defined: {len(defined)}, tokens used: {len(used)}")
print(f"external references: {sum(1 for b in bad if 'external' in b)}")
print("PAGE GUARD:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
