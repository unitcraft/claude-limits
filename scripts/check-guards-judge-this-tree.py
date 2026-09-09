# -*- coding: utf-8 -*-
"""Every checker must judge THE TREE IT IS RUN IN, and refuse when there is nothing.

    python scripts/check-guards-judge-this-tree.py

WHY. Two checkers named this machine's repository by absolute path --
`pathlib.Path(r"<repos>\\claude-limits")` -- so wherever they ran, they
read that copy. Run from a worktree, a CI checkout or a colleague's clone, they would
report on a tree nobody asked about: a fault under test passes, and a fault in the
untested copy reddens a run that has nothing to do with it.

`check-plan-trees.py` had already written the reasoning in its own header -- "an
absolute default means a copy of the repository checks the ORIGINAL and calls it
clean" -- and derived its own root from `__file__`. Knowing the hazard did not spread
it to the neighbours. That is what a checker is for.

HOW IT MEASURES. Each checker is copied into an empty directory -- `scripts/` and
nothing else -- and run there. A checker that reads the tree around it finds nothing
and must say so. A checker that exits 0 is either reading somewhere else, or cannot
fail at all. Both are the same defect from the reader's side: a green that carries no
information.

WHAT IT DOES NOT CLAIM. Exit 0 over an empty tree is not automatically wrong: a
checker whose entire input is a literal table inside the file has nothing to lose. No
such checker exists here today, and if one is written, name it in ALLOWED below WITH
its reason -- and a name left there once its file is gone is itself a failure, because
an exception nobody removes is how a rule quietly stops applying.
"""
import pathlib
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent
SELF = pathlib.Path(__file__).name

# name -> why exit 0 over an empty tree is honest for it
ALLOWED = {}

checkers = sorted([p for p in SCRIPTS.glob("check-*.py") if p.name != SELF] +
                  [p for p in SCRIPTS.glob("lint-*.py")])

if not checkers:
    print("FAILED: no checkers found beside this file -- nothing was measured")
    sys.exit(1)

tmp = pathlib.Path(tempfile.mkdtemp(prefix="guards-empty-"))
(tmp / "scripts").mkdir()
for c in checkers:
    shutil.copy2(c, tmp / "scripts" / c.name)

bad = []
lenient = []
try:
    for c in checkers:
        args = [sys.executable, str(tmp / "scripts" / c.name)]
        if c.name == "lint-openapi.py":
            # It takes a path. Passing one that does not exist here IS the question.
            args.append("fixtures/openapi/sample.json")
        try:
            r = subprocess.run(args, cwd=tmp, capture_output=True, text=True, timeout=180)
            code = r.returncode
        except subprocess.TimeoutExpired:
            bad.append(f"{c.name}: hung on an empty tree (over 180 s) -- it is doing "
                       f"something other than looking around itself")
            continue
        if code == 0:
            lenient.append(c.name)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

for name in lenient:
    if name in ALLOWED:
        continue
    bad.append(f"{name}: says CLEAN over an EMPTY tree. Either it reads a path it "
               f"names outright instead of the tree it runs in, or it cannot fail. "
               f"Derive the root from `__file__` and refuse when the input is empty.")

# An exception left behind after its file is gone silently narrows the rule.
for name in sorted(ALLOWED):
    if name not in lenient:
        bad.append(f"{name}: listed as allowed to pass on an empty tree, and it does "
                   f"not -- a stale exception. Remove the entry.")

print(f"checkers run against an empty tree: {len(checkers)}, "
      f"green there: {len(lenient)}, allowed: {len(ALLOWED)}")
print("GUARDS JUDGE THIS TREE:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
