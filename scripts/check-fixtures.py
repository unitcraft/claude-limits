"""Fixture guard: every usage fixture parses, and none of them carries a secret.

Takes the directory as argv[1] so the reverse probe can point it at a poisoned copy.

FOUND BY ITS OWN REVERSE PROBE (2026-09-07): the first version answered "clean" and
exit 0 when it found ZERO files — green on nothing measured. A check that passes on
an empty set is not a check, so zero files is now a failure.
"""
import json, pathlib, re, sys

# Derived from this file, not typed in. A hard-coded absolute default means a
# second clone scans the FIRST clone and prints a verdict about a tree the
# person is not looking at. The directory is already printed on every run
# below, so a verdict can be matched to what produced it -- that half was
# right from the start; this is the other half.
base = (pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1
        else pathlib.Path(__file__).resolve().parent.parent / "fixtures")

if not base.is_dir():
    print("SECRET SCAN: FAILED")
    print(f"   {base} is not a directory -- nothing was scanned, and a green "
          f"here would mean nothing")
    sys.exit(1)

# `sk-ant-fixture-…` is the DELIBERATE fake shape the fixtures README mandates, and
# tests search a program's output for exactly it to prove no token escaped. Anything
# else starting `sk-ant-` is treated as a live token. Without this carve-out the
# guard would redden on the very convention it is meant to protect — found 2026-09-07
# while writing the directory fixtures, before it could fire.
secrets = [
    (re.compile(r"sk-ant-(?!fixture-)[A-Za-z0-9_-]{10,}"), "live-looking token"),
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org))[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "non-example e-mail"),
    # Every spelling these files can hold: a raw backslash, the DOUBLE backslash a
    # JSON string always produces, and the forward slash that is legal on Windows and
    # common in TOML. Until 2026-09-08 only the first was matched -- and a raw
    # backslash inside JSON is invalid JSON, so the rule reported a parse error and
    # never a secret. It could not fire on anything it scanned.
    (re.compile(r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)(?!me\b)[A-Za-z]"), "real user path"),
]

bad = []

# EVERY text fixture, not only `.json`. Until 2026-09-08 this read `.json` alone: 24
# files of 35, and the eleven it skipped included five `config/*.toml` -- in a schema
# that HAS an `access_token` key. A secret scan that skips the files most likely to
# hold a secret is a scan whose green says "we did not look there".
#
# An allowlist of extensions rather than a guess at what is binary: guessing is how a
# scanner starts skipping things quietly again. A new fixture format is one entry,
# and the skipped list below makes the omission visible instead of silent.
TEXT_SUFFIXES = {".json", ".toml", ".txt", ".md", ".csv", ".yml", ".yaml", ".ini", ".env", ""}

everything = sorted(f for f in base.rglob("*") if f.is_file())
files = sorted(f for f in everything if f.suffix.lower() in TEXT_SUFFIXES)
skipped = [f for f in everything if f not in set(files)]
print(f"fixtures found: {len(files)} of {len(everything)} in {base}")
if skipped:
    kinds = sorted({(f.suffix.lower() or "(no extension)") for f in skipped})
    print(f"  NOT read ({len(skipped)}): {', '.join(kinds)} -- add the suffix above if one is text")
if not files:
    print("FAIL: zero fixtures — a check that passes on an empty set measures nothing")
    sys.exit(1)

# Reading a file for SECRETS and parsing it as a DOCUMENT are two jobs, and they were
# one loop until 2026-09-08. Widening the scan to every text fixture then made the
# guard report TOML and Markdown as INVALID JSON -- the same shape of fault it was
# being repaired for, committed while repairing it.
JSON_LIKE = {".json"}

for f in files:
    raw = f.read_text(encoding="utf-8")
    rel = f.relative_to(base).as_posix()

    # Secrets: every text fixture, whatever its format.
    for rx, what in secrets:
        m = rx.search(raw)
        if m:
            bad.append(f"{rel}: {what} -> {m.group(0)[:40]}")

    if f.suffix.lower() not in JSON_LIKE:
        print(f"  {rel:52s} scanned, not JSON")
        continue

    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        bad.append(f"{rel}: INVALID JSON — {e}")
        continue
    limits = doc.get("limits")
    n = len(limits) if isinstance(limits, list) else "n/a"
    kinds = [l.get("kind") for l in limits] if isinstance(limits, list) else "n/a"
    # Path relative to fixtures/, never the bare name: five files here are called
    # `.credentials.json`, and a failure naming only the basename says nothing.
    print(f"  {f.relative_to(base).as_posix():<52} valid JSON, limits={n} {kinds}")

print()
print("SECRET SCAN:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
