#!/bin/sh
# Run from the repository root.
set -e
echo "== renderer one, the declared door =="
sed -n '140,154p' src/server/routes.nv
echo
echo "== renderer two, past it =="
sed -n '602,608p' src/server/handlers/config.nv
echo
echo "== the invariant, written as executable code =="
sed -n '233,241p' src/server/errors.nv
echo
echo "== every call site of it in the whole tree =="
grep -rn "well_formed" src/ --include=*.nv
echo
echo "== so 429/503 hold only because five constructors remember =="
sed -n '130,169p' src/server/errors.nv | grep -n "retry_after = Some"
echo "   (and the field is plain and writable:)"
sed -n '52,56p' src/server/errors.nv
echo
echo "== what the plan asks for =="
sed -n '612,612p' docs/plans/01.3-api.md
sed -n '680,682p' docs/plans/01.3-api.md
