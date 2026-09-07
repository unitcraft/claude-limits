import pathlib, re

p = pathlib.Path(r"<repos>\claude-limits\docs\plans\01-widget-on-nova.md")
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

print("root-level .nv entries still shown in plan trees:")
if offenders:
    for b, n, f in offenders:
        print(f"  {b} line {n}: {f}")
else:
    print("  none")

# And confirm both trees now show a src/ level
for needle in ("nova-sdl/", "claude-limits/"):
    idx = next((i for i, l in enumerate(lines) if l.strip().startswith(needle)), None)
    if idx is None:
        print(f"{needle} tree: not found")
        continue
    window = "\n".join(lines[idx:idx + 30])
    print(f"{needle} tree shows a src/ level: {'src/' in window}")
