# -*- coding: utf-8 -*-
"""Does the route check run both ways, or only from the plan to the contract?

    python probes/hunt-guards-openapi-route-one-way/measure.py

THE DEFECT, until 2026-09-09. lint-openapi.py looped over `planned - PHASE_6` and
asked whether each planned route reached the contract. The reverse -- a route living
in the CONTRACT and in no table of 01.3 section 2 -- was never asked, so undocumented
API surface passed in silence.

The two directions are not the same failure. One catches a route someone described
and never built; the other catches one someone built and never described. Only the
second grows by accident, which makes it the one worth having.

Worse, the file's own header said "a route added to the contract without being added
to the spec -- OR THE REVERSE -- is what the check is FOR". True about the intent,
false about the code. A reader had no way to see the difference.

This probe feeds the linter a contract carrying an invented route and requires it to
fail, then feeds it the real contract and requires it to pass. Only the pair means
anything: a check that always fails would satisfy the first half alone.
"""
import io
import json
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
LINTER = REPO / "scripts" / "lint-openapi.py"
SPEC = REPO / "fixtures" / "openapi" / "sample.json"


def run(path):
    r = subprocess.run([sys.executable, str(LINTER), str(path)],
                       capture_output=True, text=True, cwd=str(REPO))
    return r.returncode, (r.stdout + r.stderr)


bad = 0

# 1. The real contract must pass. Without this, a linter broken into always-failing
#    would look like a working one.
code, out = run(SPEC)
print("real contract      -> exit", code)
if code != 0:
    print("  FAIL: the real contract should lint clean")
    print("  " + "\n  ".join(out.strip().split("\n")[-4:]))
    bad = 1

# 2. A route in the contract and in no plan table must be caught.
spec = json.loads(io.open(SPEC, encoding="utf-8").read())
spec.setdefault("paths", {})["/api/undocumented-probe"] = {
    "get": {"responses": {"200": {"description": "ok"}}}
}
tmp = pathlib.Path(tempfile.mkdtemp()) / "poisoned.json"
tmp.write_text(json.dumps(spec), encoding="utf-8")

code, out = run(tmp)
print("with an extra route -> exit", code)
last = [l for l in out.strip().split("\n") if "undocumented-probe" in l]
if code == 0:
    print("  FAIL: an undocumented route passed -- the check is one-way again")
    bad = 1
elif not last:
    print("  FAIL: the linter failed, but not about the undocumented route:")
    print("  " + "\n  ".join(out.strip().split("\n")[-3:]))
    bad = 1
else:
    print("  caught:", last[0].strip()[:100])

print("\nFAILED" if bad else "\nOK: both directions are checked")
sys.exit(bad)
