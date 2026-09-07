"""Fixture guard: every usage fixture parses, and none of them carries a secret.

Takes the directory as argv[1] so the reverse probe can point it at a poisoned copy.

FOUND BY ITS OWN REVERSE PROBE (2026-09-07): the first version answered "clean" and
exit 0 when it found ZERO files — green on nothing measured. A check that passes on
an empty set is not a check, so zero files is now a failure.
"""
import json, pathlib, re, sys

base = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else r"<repos>\claude-limits\fixtures")

# `sk-ant-fixture-…` is the DELIBERATE fake shape the fixtures README mandates, and
# tests search a program's output for exactly it to prove no token escaped. Anything
# else starting `sk-ant-` is treated as a live token. Without this carve-out the
# guard would redden on the very convention it is meant to protect — found 2026-09-07
# while writing the directory fixtures, before it could fire.
secrets = [
    (re.compile(r"sk-ant-(?!fixture-)[A-Za-z0-9_-]{10,}"), "live-looking token"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org))[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "non-example e-mail"),
    (re.compile(r"[A-Za-z]:\\Users\\(?!me\b)[A-Za-z]"), "real user path"),
]

bad = []
# Recursive: fixtures/usage/*.json and the dotfiles under fixtures/dirs/**.
files = sorted(f for f in base.rglob("*") if f.is_file() and f.suffix == ".json")
files += sorted(f for f in base.rglob(".claude.json"))
files += sorted(f for f in base.rglob(".credentials.json"))
files = sorted(set(files))
print(f"fixtures found: {len(files)} in {base}")
if not files:
    print("FAIL: zero fixtures — a check that passes on an empty set measures nothing")
    sys.exit(1)

for f in files:
    raw = f.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        bad.append(f"{f.relative_to(base).as_posix()}: INVALID JSON — {e}")
        continue
    limits = doc.get("limits")
    n = len(limits) if isinstance(limits, list) else "n/a"
    kinds = [l.get("kind") for l in limits] if isinstance(limits, list) else "n/a"
    # Path relative to fixtures/, never the bare name: five files here are called
    # `.credentials.json`, and a failure naming only the basename says nothing.
    print(f"  {f.relative_to(base).as_posix():<52} valid JSON, limits={n} {kinds}")
    for rx, why in secrets:
        m = rx.search(raw)
        if m:
            bad.append(f"{f.relative_to(base).as_posix()}: {why} -> {m.group(0)[:24]}")

print()
print("SECRET SCAN:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
