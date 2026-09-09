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

# suffix -> (what it means, the writers that agree with it)
SCALES = {
    "_bp":          ("basis points, 1/10000", {"field_fixed4"}),
    "_hundredths":  ("hundredths, 1/100",     {"field_fixed2", "field_fixed2_or_null"}),
    "_thousandths": ("thousandths, 1/1000",   {"field_fixed3", "field_fixed3_or_null"}),
    "_milli":       ("thousandths, 1/1000",   {"field_fixed3", "field_fixed3_or_null"}),
    "_x100":        ("hundredths, 1/100",     {"field_fixed2", "field_fixed2_or_null"}),
    "_ms":          ("milliseconds",          {"field_int", "field_int_or_null"}),
    "_sec":         ("seconds",               {"field_int", "field_int_or_null"}),
}

bad = []
fields_seen = 0
files = 0

for f in sorted(SRC.rglob("*.nv")):
    if f.name.endswith("_test.nv"):
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    if "field_" not in text:
        continue
    files += 1
    rel = f.relative_to(REPO)

    # Every `field_xxx("wire_name", <expr>.field_name)` call in the file.
    for m in re.finditer(r"\b(field_[a-z0-9_]+)\s*\(\s*\"[^\"]*\"\s*,\s*([^)]*)\)", text):
        writer, arg = m.group(1), m.group(2).strip()

        # ONLY a plain field access is judged. `field_raw("poll", object([...]))`
        # passes a nested expression, and taking the last dotted token out of it
        # picks up an identifier from deep inside -- which is exactly what the first
        # run of this check did, reporting two false positives about `interval_sec`
        # inside a nested object. A check whose first report is about itself is worth
        # fixing rather than tuning: the alternative is a guard people learn to skim.
        if "(" in arg or "[" in arg or "," in arg or " " in arg:
            continue
        leaf = arg.split(".")[-1].strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", leaf):
            continue
        fields_seen += 1
        for suf, (meaning, ok_writers) in SCALES.items():
            if leaf.endswith(suf):
                if writer not in ok_writers:
                    line = text[: m.start()].count("\n") + 1
                    bad.append(
                        f"{rel}:{line}: `{leaf}` is named {suf} ({meaning}) but is "
                        f"written by `{writer}`, which does not match. Rename the "
                        f"field or change the writer -- a suffix nothing enforces is "
                        f"how a value ends up a hundred times off.")
                break

print(f"files with field writers: {files}, field writes checked: {fields_seen}")

# The check must have found something to judge. Zero means the pattern stopped
# matching, and the guard would stay green through anything.
if files == 0 or fields_seen == 0:
    print("SCALE SUFFIXES: FAILED")
    print(f"   files={files}, writes={fields_seen} -- nothing was judged, so a green "
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
scale_by_suffix = {suf: meaning for suf, (meaning, _w) in SCALES.items()}

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
