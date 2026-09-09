# -*- coding: utf-8 -*-
"""Report only: for the REAL tree, which artboard labels does
check-artboard-labels.py accept, and on what evidence?

    python where-matched.py <repo-root>

Label extraction and normalisation are copied from the guard
(scripts/check-artboard-labels.py:67-75, :109-111), so the arithmetic is the guard's
own. Nothing is modified; this script only reads and prints.

The third section is the interesting one: a label the guard calls "produced by the
page" while no source line contains it inside a STRING LITERAL -- every match is a
comment, an identifier or a CSS property.
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(sys.argv[1]).resolve()
ART = ROOT / "docs" / "design" / "browser-page"
WEB = ROOT / "src" / "web"
PAGE = ["Main.dc.html", "MainBlocks.dc.html", "CardsView.dc.html",
        "StatsView.dc.html", "StatsFolders.dc.html", "SettingsPanel.dc.html"]


def labels_of(p):
    t = p.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    out = []
    for m in re.finditer(r">([^<>]+)<", t):
        s = " ".join(m.group(1).split())
        if s and not s.startswith("&") and len(s) <= 60:
            out.append(s)
    return list(dict.fromkeys(out))


def normalise(s):
    return re.sub(r"[\s·→–—.,:;()\[\]]+", " ", s).strip().lower()


files = sorted(WEB.glob("*.js")) + sorted(WEB.glob("*.html")) + sorted(WEB.glob("*.css"))
texts = {f.name: f.read_text(encoding="utf-8", errors="replace") for f in files}
hay_n = normalise("\n".join(texts[f.name] for f in files))

COMMENT = ("//", "*", "/*", "<!--")
STRING = re.compile(r"""'[^']*'|"[^"]*"|`[^`]*`|>[^<>]*<""")


def evidence(label):
    """Every source line whose normalised form contains the normalised label."""
    n = normalise(label)
    hits = []
    for fn, t in texts.items():
        for i, ln in enumerate(t.splitlines(), 1):
            if n in normalise(ln):
                in_string = any(n in normalise(s) for s in STRING.findall(ln))
                hits.append((fn, i, ln.strip(), ln.strip().startswith(COMMENT), in_string))
    return hits


accepted, only_comment, tiny, never_a_string = [], [], [], []
for name in PAGE:
    for label in labels_of(ART / name):
        if re.search(r"\d", label):
            continue
        n = normalise(label)
        if not n or n not in hay_n:
            continue
        accepted.append((name, label))
        hits = evidence(label)
        if hits and all(h[3] for h in hits):
            only_comment.append((name, label, hits))
        if len(n) <= 3:
            tiny.append((name, label))
        if hits and not any(h[4] for h in hits):
            never_a_string.append((name, label, hits))

print(f"labels the guard accepts as produced by the page: {len(accepted)}")
print()
print("1. accepted ONLY because the words appear in a COMMENT:")
for name, label, hits in only_comment:
    print(f"   {name}: `{label}`")
    for fn, i, ln, _, _ in hits:
        print(f"        {fn}:{i}: {ln[:100]}")
print()
print("2. accepted with a normalised form of three characters or fewer:")
for name, label in tiny:
    print(f"   {name}: `{label}`")
print()
print("3. accepted although NO source line carries them inside a string literal:")
for name, label, hits in never_a_string:
    print(f"   {name}: `{label}`")
    for fn, i, ln, _, _ in hits:
        print(f"        {fn}:{i}: {ln[:100]}")
