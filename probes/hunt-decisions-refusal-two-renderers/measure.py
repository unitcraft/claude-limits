# -*- coding: utf-8 -*-
"""Is the error-shape invariant checked where errors actually leave?

    python probes/hunt-decisions-refusal-two-renderers/measure.py

THE DEFECT, until 2026-09-09. `well_formed` (server/errors.nv:236) states three rules
the contract makes: a 422 carries at least one field error, a 429 or 503 carries
Retry-After, a 405 carries Allow. It was called six times in the tree and all six were
inside errors_test.nv.

An invariant asserted only about hand-built values in a test says the CONSTRUCTORS are
right. It says nothing about what leaves the process, which is the thing it is written
about. Every error goes out through one function -- routes.problem -- and that
function did not consult it.

WHAT THE FIX IS NOT. It does not panic and it does not withhold the reply. A malformed
error body is still a better answer than none, and dying inside the error path is how
one bad reply becomes an outage. The breach travels as a header, where a test and a
person can both see it, and the response still goes out.

Checked here by reading the source: this is Nova, and standing up the handler for one
assertion would mean a compiler and a database.
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
ROUTES = REPO / "src" / "server" / "routes.nv"
ERRORS = REPO / "src" / "server" / "errors.nv"

bad = 0


def fail(msg):
    global bad
    print("  FAIL:", msg)
    bad = 1


for f in (ROUTES, ERRORS):
    if not f.exists():
        print(f"  FAIL: {f.name} missing -- this probe measured nothing")
        sys.exit(1)

routes = ROUTES.read_text(encoding="utf-8")
errors = ERRORS.read_text(encoding="utf-8")

# 1. The invariant still exists and still states its three rules.
m = re.search(r"export fn well_formed\(.*?\n\}", errors, re.S)
if not m:
    fail("well_formed is gone from errors.nv")
else:
    body = m.group(0)
    for code, what in (("422", "a validation error with no fields"),
                       ("429", "a rate limit with no Retry-After"),
                       ("405", "a method refusal with no Allow")):
        if code not in body:
            fail(f"well_formed no longer mentions {code} ({what})")
    print("well_formed states its three rules")

# 2. It is called on the response path, not only in tests.
prob = re.search(r"export fn problem\(.*?\n\}", routes, re.S)
if not prob:
    fail("routes.problem not found -- renamed? this probe needs updating")
    sys.exit(1)
# A CALL, not a mention. The first version of this check tested `"well_formed" in
# body`, and the function's own comment explains the invariant BY NAME -- so removing
# the call left the probe green. A control that does not redden proves nothing, and
# that one was measuring a comment.
prob_code = "\n".join(
    line for line in prob.group(0).split("\n")
    if not line.strip().startswith("//"))
if not re.search(r"\bwell_formed\s*\(", prob_code):
    fail("routes.problem does not CALL well_formed -- the invariant is back to being "
         "asserted only in tests (a mention in a comment is not a check)")
else:
    print("routes.problem calls well_formed")

# 3. Every caller in the tree, counted. The point of the finding was the RATIO.
callers = {}
for f in sorted((REPO / "src").rglob("*.nv")):
    n = len(re.findall(r"\bwell_formed\s*\(", f.read_text(encoding="utf-8", errors="replace")))
    if n:
        callers[str(f.relative_to(REPO))] = n
print("callers:", callers)

non_test = {k: v for k, v in callers.items() if not k.endswith("_test.nv")}
if not non_test:
    fail("every call to well_formed is in a test again")
else:
    print(f"non-test callers: {sorted(non_test)}")

# 4. The response still goes out. A fix that refuses to answer would satisfy the
#    check above and be worse than the defect.
if re.search(r"panic\(|abort\(|throw ", prob.group(0)):
    fail("problem() can now panic or throw -- an error path that dies turns one bad "
         "reply into an outage")
else:
    print("problem() still returns a response on every path")

print("\nFAILED" if bad else "\nOK: the invariant is checked where errors leave, and the reply still leaves")
sys.exit(bad)
