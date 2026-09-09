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

print("SCALE SUFFIXES:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
