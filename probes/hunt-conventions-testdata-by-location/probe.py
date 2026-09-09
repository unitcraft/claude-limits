# -*- coding: utf-8 -*-
"""The rule "test data carries only synthetic addresses" is held by ONE machine,
and that machine looks (a) only inside fixtures/, (b) only INSIDE the file.

Three runs, all of scripts/check-fixtures.py, the project's own guard:

  1. the real fixtures directory                     -> whatever it says today
  2. a tree holding the literals that live today in
     scripts/test-reorder.mjs                        -> FAILED, by the guard's own rule
  3. a fixture whose CONTENT is spotless and whose
     NAME is an e-mail                               -> clean, and the guard prints it

Everything is written under this directory. Nothing in the repository is touched.

Run:  python probe.py
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
GUARD = REPO / "scripts" / "check-fixtures.py"


def run(where):
    p = subprocess.run([sys.executable, str(GUARD), str(where)],
                       capture_output=True, text=True, cwd=str(REPO))
    return p.returncode, p.stdout.strip()


def show(title, where):
    code, out = run(where)
    verdict = next((l for l in out.splitlines() if l.startswith("SECRET SCAN")), out.splitlines()[-1])
    print(f"{title}")
    print(f"   exit={code}   {verdict}")
    for l in out.splitlines():
        if l.startswith("  ") and "->" in l:
            print(f"   {l.strip()}")
    return code, out


# --- 0. where the literals actually live -------------------------------------
suite = REPO / "scripts" / "test-reorder.mjs"
found = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                              suite.read_text(encoding="utf-8"))))
print(f"addresses hard-coded in scripts/test-reorder.mjs: {found}")
print("the guard's own rule, scripts/check-fixtures.py:21, calls anything outside")
print("example.com / example.org a 'non-example e-mail'.")
print()

# --- 1. control: the real fixtures ------------------------------------------
show("1. the real fixtures/ directory, as this run finds it", REPO / "fixtures")
print()

# --- 2. the same literals, moved into a fixture-shaped tree ------------------
tree = HERE / "as-a-fixture"
shutil.rmtree(tree, ignore_errors=True)
(tree / "usage").mkdir(parents=True)
(tree / "usage" / "order.json").write_text(
    json.dumps({"_comment": "the exact accounts_order literal of scripts/test-reorder.mjs:23",
                "accounts_order": found}, indent=1), encoding="utf-8")
show("2. the SAME strings, sitting inside a fixture tree", tree)
print("   the file in scripts/ is never read by this guard: it scans *.json under the")
print("   directory it is given, and no run of it is ever given scripts/.")
print()

# --- 3. the datum in the NAME instead of the content -------------------------
named = HERE / "name-carries-it"
shutil.rmtree(named, ignore_errors=True)
(named / "usage").mkdir(parents=True)
# scripts/claude_limits.py:328 looks a recorded reply up as `<offline_dir>/<email>.json`,
# so this is the file name the reference tool asks a person to create.
(named / "usage" / "firstname.lastname@customer-corp.ru.json").write_text(
    json.dumps({"limits": [], "_comment": "content is spotless"}, indent=1), encoding="utf-8")
code, out = show("3. spotless content, the e-mail is the FILE NAME", named)
printed = [l for l in out.splitlines() if "@" in l]
print("   what the guard printed about it:")
for l in printed:
    print(f"     {l.strip()}")
