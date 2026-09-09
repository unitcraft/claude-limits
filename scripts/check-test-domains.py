# -*- coding: utf-8 -*-
"""Test data must use reserved domains, wherever it lives.

    python scripts/check-test-domains.py

WHY THIS EXISTS, AND WHY IT IS NOT PART OF check-fixtures.py. That guard asks WHERE a
file is: it walks `fixtures/` and judges what it finds. Test data does not only live
there. It lives in literals inside test files, and it lives in file NAMES -- and both
were invisible to a check scoped by location.

Measured 2026-09-08: `a@x.com`, `b@x.com`, `c@x.com`, `d@x.com` appeared 37 times
across four test files. `x.com` is a REAL domain belonging to someone else. RFC 2606
reserves example.com / example.net / example.org / .test / .invalid / .example /
localhost precisely so that test data cannot address a stranger, and the database
convention says the same in its own words (database.md:444 -- test data must be
synthetic, `user1@example.com`).

Nothing dramatic happened. Nothing dramatic is the point: a test that mails, resolves
or rate-limits against a literal is one careless line away, and by then the literal is
in forty places.

WHAT IT SCANS. Test sources and fixtures, by CONTENT and by FILE NAME. Not the whole
repository: documentation quotes real domains legitimately, and a guard that cries
about prose gets disabled.
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

# RFC 2606 and RFC 6761, plus the one every developer machine already resolves.
RESERVED = (".example.com", ".example.net", ".example.org",
            "example.com", "example.net", "example.org",
            ".test", ".invalid", ".example", ".localhost", "localhost")

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")

# Where test data lives. Each entry is (directory, glob).
SCAN = [
    ("scripts", "test-*.mjs"),
    ("scripts", "test_*.py"),
    ("src", "**/*_test.nv"),
    ("fixtures", "**/*"),
    ("probes", "**/*.mjs"),
    ("probes", "**/*.py"),
]

TEXT_SUFFIXES = {".json", ".toml", ".txt", ".md", ".csv", ".yml", ".yaml",
                 ".ini", ".env", ".mjs", ".js", ".py", ".nv", ""}


# A FILE EXTENSION IS NOT PART OF A DOMAIN. `probe@customer-corp.example.json` is a
# filename, and reading ".json" as the last label made the check report a reserved
# domain as a real one -- found by running it against a probe whose whole subject is
# addresses in filenames. Stripped here rather than by narrowing the pattern: the
# filename case is one this check exists to catch, so it has to keep matching it and
# judge the domain underneath.
FILE_SUFFIXES = (".json", ".toml", ".txt", ".md", ".csv", ".yml", ".yaml",
                 ".ini", ".env", ".log", ".bak", ".nv", ".py", ".mjs", ".js")


def reserved(domain):
    d = domain.lower().rstrip(".")
    for suf in FILE_SUFFIXES:
        if d.endswith(suf):
            d = d[: -len(suf)]
            break
    return any(d == r.lstrip(".") or d.endswith(r) for r in RESERVED)


bad = []
scanned = 0
seen = set()

for root, pattern in SCAN:
    base = REPO / root
    if not base.exists():
        continue
    for f in sorted(base.glob(pattern)):
        if not f.is_file() or f in seen:
            continue
        if f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        seen.add(f)
        scanned += 1
        rel = f.relative_to(REPO)

        # The file NAME carries data too, and a name is copied into logs and reports
        # by anything that lists what it read.
        for m in EMAIL.finditer(f.name):
            if not reserved(m.group(1)):
                bad.append(f"{rel}: the FILE NAME contains an address at "
                           f"{m.group(1)!r}, which is not a reserved domain")

        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            bad.append(f"{rel}: cannot read ({e})")
            continue

        hits = {}
        for i, line in enumerate(text.split("\n"), 1):
            for m in EMAIL.finditer(line):
                dom = m.group(1)
                if not reserved(dom):
                    hits.setdefault(dom, []).append(i)
        for dom, ls in sorted(hits.items()):
            where = ", ".join(str(x) for x in ls[:5]) + (" ..." if len(ls) > 5 else "")
            bad.append(f"{rel}: {len(ls)} address(es) at {dom!r} (lines {where}) -- "
                       f"RFC 2606 reserves example.com/.net/.org, .test and .invalid")

print(f"test files scanned: {scanned}")

# A scan that found no files is not a clean scan. This is the failure the whole file
# is about, one level up.
if scanned == 0:
    print("TEST DOMAINS: FAILED")
    print("   zero files scanned -- the globs match nothing, so this check measured "
          "nothing and would stay green while the tree filled up with real domains")
    sys.exit(1)

print("TEST DOMAINS:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
