# -*- coding: utf-8 -*-
"""One named limit, one place. A second copy is not a tidiness problem.

    python scripts/check-duplicate-limits.py

WHY. `MAX_SUBSCRIBERS = 32` existed twice -- in model/store.nv and in
server/handlers/events.nv -- and NEITHER was exported. The copy was not carelessness;
it was the only spelling available to the second module. A number that cannot be
shared gets duplicated by whoever needs it, the two drift, and nothing anywhere says
they have.

The cost was already paid here. `store.subscribe` counts refusals into
`Registry.rejected`, documented "for /api/health"; the live decision is made by
`events.opening`, which does not touch the counter and cannot -- it takes the registry
by value. So the metric read zero forever, and /api/health never read it either, so
nothing contradicted the zero.

WHAT IS CHECKED. A SCREAMING_CASE constant declared in more than one module under
src/. That spelling is reserved for limits and thresholds here, which are exactly the
values whose copies do damage. A constant declared once, exported or not, is fine.

WHAT IS NOT. Local `ro`/`mut` bindings, and lowercase names: naming a local the same
thing twice is not a shared decision made twice.
"""
import collections
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "src"

CONST = re.compile(
    r"^\s*(?:export\s+)?const\s+([A-Z][A-Z0-9_]{2,})\s*=\s*([^\n/]+)", re.M)

where = collections.defaultdict(list)
files = 0

for f in sorted(SRC.rglob("*.nv")):
    if f.name.endswith("_test.nv"):
        continue
    files += 1
    text = f.read_text(encoding="utf-8", errors="replace")
    for m in CONST.finditer(text):
        line = text[: m.start()].count("\n") + 1
        where[m.group(1)].append((str(f.relative_to(REPO)), line, m.group(2).strip()))

# THE SAME NAME IS NOT THE SAME DECISION. `ONLY_FIELD` is declared in three handlers
# with three different values -- "path", "account_id", "allow_lan" -- because each
# body allows one field and they are different fields. That is a shared NAMING habit,
# not a shared number, and nothing drifts when one changes. The first run of this
# check reported all three, which would have taught a reader to skim it.
#
# A copy does damage when the name AND the value agree: then two modules are making
# one decision twice, and a change to either is a silent divergence.
dupes = {}
for k, v in where.items():
    if len(v) < 2:
        continue
    values = {x[2] for x in v}
    if len(values) == 1:
        dupes[k] = v

print(f"modules read: {files}, SCREAMING_CASE constants: {len(where)}")

# A scan that found no constants is not a clean scan.
if files == 0 or not where:
    print("DUPLICATE LIMITS: FAILED")
    print(f"   files={files}, constants={len(where)} -- nothing was judged")
    sys.exit(1)

print("DUPLICATE LIMITS:", "clean" if not dupes else "FAILED")
for name, sites in sorted(dupes.items()):
    print(f"   {name} is declared in {len(sites)} modules:")
    for path, line, val in sites:
        print(f"     {path}:{line}  = {val}")
    print(f"     Export it from one and import it into the others. Two copies of a "
          f"limit drift, and the drift is silent.")

sys.exit(1 if dupes else 0)
