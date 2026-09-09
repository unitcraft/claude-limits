# -*- coding: utf-8 -*-
"""Count the files under a fixtures directory that check-fixtures.py never opens.

    python inventory.py <fixtures-dir>

The collection rule is copied from scripts/check-fixtures.py:27-30 (suffix .json,
plus the two dotfile names it lists) -- this script only reports, it changes nothing.
"""
import pathlib, sys

base = pathlib.Path(sys.argv[1])
allf = [f for f in base.rglob("*") if f.is_file()]
scanned = set(f for f in base.rglob("*") if f.is_file() and f.suffix == ".json")
scanned |= set(base.rglob(".claude.json")) | set(base.rglob(".credentials.json"))
print(f"files under {base.as_posix()}: {len(allf)}   opened by the secret scan: {len(scanned)}")
for f in sorted(set(allf) - scanned):
    print("   not scanned:", f.relative_to(base).as_posix())
