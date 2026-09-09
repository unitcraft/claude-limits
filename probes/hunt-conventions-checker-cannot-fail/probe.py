# -*- coding: utf-8 -*-
"""Two members of the web check answer a different question than their header says.

  A. scripts/check-plan-trees.py has no exit path other than 0. check-web.mjs judges
     the checkers BY EXIT CODE (its own header, lines 16-18), so this one is green
     whatever it prints.

  B. scripts/lint-openapi.py says (lines 13-16) that a route added to the contract
     "without being added to the spec -- or the reverse" is what the check is FOR.
     Only one direction is implemented: the plan's routes are looked for in the
     contract, never the contract's in the plan.

Run:  python probe.py     (writes only into this directory)
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent


def run(args):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=str(REPO))
    return p.returncode, (p.stdout or "").strip()


# --- A ------------------------------------------------------------------------
guard = REPO / "scripts" / "check-plan-trees.py"
code, out = run([str(guard)])
exits = re.findall(r"sys\.exit\([^)]*\)|SystemExit\([^)]*\)", guard.read_text(encoding="utf-8"))
print("A. scripts/check-plan-trees.py")
print(f"   exit={code}")
print(f"   exit statements in the whole file: {exits or 'NONE'}")
print("   its own failure branches, verbatim from the source:")
for i, line in enumerate(guard.read_text(encoding="utf-8").splitlines(), 1):
    if "print(f\"{needle} tree: not found\")" in line or "line {n}" in line:
        print(f"     :{i} {line.strip()}")
print("   -> whatever it finds, check-web.mjs (lines 93-100) reads exit 0 and prints `ok`.")
print()

# --- B ------------------------------------------------------------------------
sample = REPO / "fixtures" / "openapi" / "sample.json"
spec = json.loads(sample.read_text(encoding="utf-8"))
planned = set()
plan = (REPO / "docs" / "plans" / "01.3-api.md").read_text(encoding="utf-8")
for line in plan.splitlines():
    m = re.match(r"^\|\s*`(GET|POST|PUT|DELETE|PATCH|HEAD) ([^`]+)`\s*\|", line)
    if m:
        planned.add(f"{m.group(1)} {m.group(2)}")

extra = "/api/accounts/{account_id}/token"
spec["paths"][extra] = json.loads(json.dumps(spec["paths"]["/api/snapshot"]))
out_path = HERE / "extra-route.json"
out_path.write_text(json.dumps(spec, indent=1), encoding="utf-8")

code, out = run([str(REPO / "scripts" / "lint-openapi.py"), str(out_path)])
print("B. a route added to the CONTRACT that no plan table mentions:")
print(f"   added: GET {extra}")
print(f"   is it in the 01.3 section 2 table? {'GET ' + extra in planned}")
print(f"   exit={code}   {[l for l in out.splitlines() if l.startswith('OPENAPI LINT')][0]}")
print(f"   {out.splitlines()[0]}")
print("   -> the count of described routes moved; the verdict did not.")
