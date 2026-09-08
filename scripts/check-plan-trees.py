# The trees drawn in plan 01 must not show `.nv` files at the package root, and must
# show a `src/` level -- the owner's rule: "никаких .nv файлов в корне claude-limits".
#
# UNTIL 2026-09-08 THIS FILE COULD NOT FAIL. It had no `sys.exit` at all, and it is in
# the CHECKERS list of check-web.mjs, which judges by exit code -- so it printed `ok`
# whatever it found, including the very thing it was written to find.
import pathlib, re, sys

# Derived from this file, never written out: an absolute default means a copy of the
# repository checks the ORIGINAL and calls it clean.
p = pathlib.Path(__file__).resolve().parent.parent / "docs" / "plans" / "01-widget-on-nova.md"
if not p.exists():
    print(f"FAILED: {p} does not exist -- nothing to check")
    sys.exit(1)
lines = p.read_text(encoding="utf-8").splitlines()

# Collect every fenced tree block and report .nv entries that sit at depth 1
# (i.e. directly in the package root rather than under src/).
in_block = False
block_name = None
offenders = []
for i, l in enumerate(lines, 1):
    if l.startswith("```"):
        in_block = not in_block
        if in_block:
            block_name = None
        continue
    if not in_block:
        continue
    if l.endswith("/") and ("nova-sdl" in l or "claude-limits" in l):
        block_name = l.strip()
    # depth-1 entry: starts with the first-level connector, no extra indent
    # `/` MUST be in the class: the first version matched only bare filenames and
    # gave a false green on `├── bin/claude_limits.nv`, which is just as much a
    # root-level entry. Found 2026-09-07 by reading the tree after the check said
    # it was clean.
    m = re.match(r"^[├└]── ([A-Za-z0-9_./-]+\.nv)\b", l)
    if m:
        offenders.append((block_name or "?", i, m.group(1)))

bad = []

print("root-level .nv entries still shown in plan trees:")
if offenders:
    for b, n, f in offenders:
        print(f"  {b} line {n}: {f}")
        bad.append(f"{b} line {n}: `{f}` sits at the package root")
else:
    print("  none")

# Both trees must be FOUND and must show a src/ level. A tree that cannot be located
# is not "nothing to say" -- it means the document was restructured under the check.
for needle in ("nova-sdl/", "claude-limits/"):
    idx = next((i for i, l in enumerate(lines) if l.strip().startswith(needle)), None)
    if idx is None:
        print(f"{needle} tree: NOT FOUND")
        bad.append(f"{needle} tree not found in {p.name} -- the check measured nothing for it")
        continue
    window = "\n".join(lines[idx:idx + 30])
    shown = "src/" in window
    print(f"{needle} tree shows a src/ level: {shown}")
    if not shown:
        bad.append(f"{needle} tree shows no src/ level")

print("PLAN TREES:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
