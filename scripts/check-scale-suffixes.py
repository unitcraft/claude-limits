# -*- coding: utf-8 -*-
"""A scale suffix must agree with how the field is written.

    python scripts/check-scale-suffixes.py

WHY. `elapsed_share_bp` was named in basis points (one ten-thousandth) and written
through `field_fixed2`, which emits hundredths. The docstring said hundredths, the
file header said hundredths, the writer said hundredths -- and the name said otherwise
to anyone who read the name alone.

A SUFFIX IS NOT A TYPE. Nothing checks it, nothing fails when it stops matching, and a
reader who trusts it divides by 10000 where 100 belongs. The result is a number a
hundred times too small, which reads as a plausible value rather than as an error --
the expensive kind of wrong.

Renaming that one field does not close the class: the next `_bp`, `_ms` or `_pct` can
disagree the same way. This check ties the suffix to the writer, so the two cannot
drift apart in silence.

WHAT IT KNOWS. A small table of suffix -> the writer that matches it. A field whose
name carries a known scale suffix must be written by the matching helper. A field with
no such suffix is not judged: naming a scale is optional, lying about it is not.
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "src"

# suffix -> (what it means, the divisor that turns it into the wire's fraction; None
# for a unit that stays an integer on the wire)
SCALES = {
    "_bp":          ("basis points, 1/10000", 10000),
    "_hundredths":  ("hundredths, 1/100",     100),
    "_thousandths": ("thousandths, 1/1000",   1000),
    "_milli":       ("thousandths, 1/1000",   1000),
    "_x100":        ("hundredths, 1/100",     100),
    "_ms":          ("milliseconds",          None),
    "_sec":         ("seconds",               None),
}

# WHERE A SCALE MEETS THE WIRE. Since T2.29 (serde) a fixed-point field reaches JSON
# as `(record.name_milli as f64) / 1000.0` in the record that serde writes -- the
# divisor IS the writer now.
#
# CORRECTION 2026-09-30: this half used to read `field_fixed2("wire", x.name)`
# calls, the hand-written JSON writer. T2.29 step 6 removed them; the pattern matched
# nothing, and the guard printed `writes=0` and FAILED -- correctly, and unseen,
# because the repository had no CI to run it.
CONVERSION = re.compile(
    r"\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s+as\s+f64\s*\)\s*/\s*([0-9]+)(?:\.0+)?\b")

bad = []
fields_seen = 0
files = 0

for f in sorted(SRC.rglob("*.nv")):
    if f.name.endswith("_test.nv"):
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    found = list(CONVERSION.finditer(text))
    if not found:
        continue
    files += 1
    rel = f.relative_to(REPO)
    for m in found:
        leaf = m.group(1).split(".")[-1]
        divisor = int(m.group(2))
        for suf, (meaning, want) in SCALES.items():
            if leaf.endswith(suf):
                fields_seen += 1
                if want is None or divisor != want:
                    line = text[: m.start()].count("\n") + 1
                    bad.append(
                        f"{rel}:{line}: `{leaf}` is named {suf} ({meaning}) but is "
                        f"divided by {divisor} on its way to the wire. Rename the "
                        f"field or fix the divisor -- a suffix nothing enforces is "
                        f"how a value ends up a hundred times off.")
                break

print(f"files converting a scale: {files}, conversions checked: {fields_seen}")

# The check must have found something to judge. Zero means the pattern stopped
# matching, and the guard would stay green through anything.
if files == 0 or fields_seen == 0:
    print("SCALE SUFFIXES: FAILED")
    print(f"   files={files}, conversions={fields_seen} -- nothing was judged, so a green "
          f"here would mean nothing")
    sys.exit(1)

# ---------------------------------------------------------------------------
# ONE SCALE ASSIGNED INTO ANOTHER.
#
# The half above ties a suffix to its writer, so it only sees fields on their way to
# the wire. It cannot see the hazard that is actually sitting in the tree today:
# `model/forecast.nv` produces `rate_per_hour_x100` (hundredths) and `server/dto.nv`
# wants `rate_per_hour_milli` (thousandths), and NOTHING converts between them --
# because the layer that joins model to DTO is not written yet (T2.x).
#
# Whoever writes it will put one into the other. There is no type to stop them: both
# are `int`, both are called `rate_per_hour`, and the result -- every rate ten times
# too small -- reads as a slow week rather than as a bug.
#
# So the check is added BEFORE the code it judges. It finds zero violations today,
# which is the point: it is a trap set on the path, not a report about the past.
scale_by_suffix = {suf: meaning for suf, (meaning, _d) in SCALES.items()}

inits = 0
for f in sorted(SRC.rglob("*.nv")):
    if f.name.endswith("_test.nv"):
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    rel = f.relative_to(REPO)

    # `target_name: <expr>.source_name` -- a record field initialised from a field,
    # and `target_name = <expr>.source_name` -- a plain assignment or binding.
    for m in re.finditer(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*([A-Za-z_][A-Za-z0-9_.]*)\s*[,)\n]",
            text):
        target, src = m.group(1), m.group(2)
        leaf = src.split(".")[-1]
        if leaf == target:
            continue
        t_suf = next((x for x in scale_by_suffix if target.endswith(x)), None)
        s_suf = next((x for x in scale_by_suffix if leaf.endswith(x)), None)
        if t_suf is None or s_suf is None:
            continue
        inits += 1
        if t_suf != s_suf:
            line = text[: m.start()].count("\n") + 1
            bad.append(
                f"{rel}:{line}: `{target}` is {scale_by_suffix[t_suf]} but takes its "
                f"value from `{leaf}`, which is {scale_by_suffix[s_suf]}. Convert "
                f"explicitly -- both are `int`, so nothing else will notice, and the "
                f"number that comes out looks plausible.")

# THIS HALF CANNOT SELF-TEST ON ITS FINDINGS: zero violations is the expected and
# desired state. What it can assert is that the PATTERN still matches the language --
# that scale-suffixed names are being read at all. Were the corpus to lose every one
# of them, the silence would be indistinguishable from cleanliness.
suffixed = 0
for f in sorted(SRC.rglob("*.nv")):
    if f.name.endswith("_test.nv"):
        continue
    t = f.read_text(encoding="utf-8", errors="replace")
    for suf in scale_by_suffix:
        suffixed += len(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*" + re.escape(suf) + r"\b", t))

print(f"scale-suffixed names in sources: {suffixed}, scale-to-scale copies seen: {inits}")
if suffixed == 0:
    print("SCALE SUFFIXES: FAILED")
    print("   no scale-suffixed name found anywhere -- the cross-scale half judged "
          "nothing, and its green would mean nothing")
    sys.exit(1)

print("SCALE SUFFIXES:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
