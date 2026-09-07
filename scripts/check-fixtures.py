"""Fixture guard: every usage fixture parses, and none of them carries a secret.

Takes the directory as argv[1] so the reverse probe can point it at a poisoned copy.

FOUND BY ITS OWN REVERSE PROBE (2026-09-07): the first version answered "clean" and
exit 0 when it found ZERO files — green on nothing measured. A check that passes on
an empty set is not a check, so zero files is now a failure.
"""
import json, pathlib, re, sys

base = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else r"<repos>\claude-limits\fixtures\usage")

secrets = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"), "live-looking token"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org))[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "non-example e-mail"),
    (re.compile(r"[A-Za-z]:\\Users\\(?!me\b)[A-Za-z]"), "real user path"),
]

bad = []
files = sorted(base.glob("*.json"))
print(f"fixtures found: {len(files)} in {base}")
if not files:
    print("FAIL: zero fixtures — a check that passes on an empty set measures nothing")
    sys.exit(1)

for f in files:
    raw = f.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        bad.append(f"{f.name}: INVALID JSON — {e}")
        continue
    limits = doc.get("limits")
    n = len(limits) if isinstance(limits, list) else "n/a"
    kinds = [l.get("kind") for l in limits] if isinstance(limits, list) else "n/a"
    print(f"  {f.name:<30} valid JSON, limits={n} {kinds}")
    for rx, why in secrets:
        m = rx.search(raw)
        if m:
            bad.append(f"{f.name}: {why} -> {m.group(0)[:24]}")

print()
print("SECRET SCAN:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
