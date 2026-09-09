# -*- coding: utf-8 -*-
"""Identifiers in fixtures must have the shape the system actually produces.

    python scripts/check-fixture-ids.py

WHY. 01.2-storage.md item 7: every key is a UUID v7, from `Uuid.v7()`. Three fixtures
followed that; a fourth used `acc-0001` and `d-1001`, shapes nothing in the system can
emit. Twenty-seven tests rendered against it, and not one of them looked at the shape
-- which is why the divergence survived: the tests did not care, so nothing objected.

A fixture in a shape the system cannot produce is a test of a system we do not have.
It passes, and it tells you nothing about the one we do.

WHAT IS CHECKED. Any JSON value under a key ending in `id` (or named exactly `id`)
must be a UUID -- v7 by preference, since that is what the schema says, and the check
names the version it found when it is not 7. Values that are plainly not identifiers
are left alone: an empty string, and `null`.

WHAT IS NOT CHECKED, deliberately. Fixtures under `fixtures/config/` and
`fixtures/dirs/`, which model FILES ON DISK rather than API bodies -- a config file
names accounts by e-mail, not by key, and demanding UUIDs there would be wrong rather
than strict.
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BASE = REPO / "fixtures"

# Directories modelling on-disk files rather than API payloads.
SKIP_DIRS = {"config", "dirs"}

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-([1-8])[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)

bad = []
checked = 0
files = 0


def looks_like_id_key(key):
    k = key.lower()
    return k == "id" or k.endswith("_id")


def walk(node, path, rel):
    global checked
    if isinstance(node, dict):
        for k, v in node.items():
            if looks_like_id_key(k) and isinstance(v, str):
                checked += 1
                if v == "":
                    continue
                m = UUID.match(v)
                if not m:
                    bad.append(f"{rel}: {path}.{k} = {v!r} is not a UUID -- the schema "
                               f"says every key is a UUID v7 (01.2 item 7)")
                elif m.group(1) != "7":
                    bad.append(f"{rel}: {path}.{k} = {v!r} is a UUID v{m.group(1)}, "
                               f"not v7")
            walk(v, f"{path}.{k}", rel)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]", rel)


if not BASE.exists():
    print("FIXTURE IDS: FAILED")
    print("   no fixtures/ directory -- nothing was checked")
    sys.exit(1)

for f in sorted(BASE.rglob("*.json")):
    if any(part in SKIP_DIRS for part in f.relative_to(BASE).parts[:-1]):
        continue
    files += 1
    rel = f.relative_to(REPO)
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        bad.append(f"{rel}: not valid JSON ({e})")
        continue
    walk(doc, "$", rel)

print(f"fixtures read: {files}, identifier values checked: {checked}")

# Zero of either means the check measured nothing, which would then stay green while
# the fixtures drifted into any shape at all.
if files == 0 or checked == 0:
    print("FIXTURE IDS: FAILED")
    print(f"   files={files}, ids={checked} -- this check found nothing to judge, so "
          f"its green would mean nothing")
    sys.exit(1)

print("FIXTURE IDS:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
