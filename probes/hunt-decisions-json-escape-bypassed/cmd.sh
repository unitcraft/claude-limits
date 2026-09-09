#!/bin/sh
# Run from the repository root.
set -e
echo "== the door, and why the file exists at all =="
sed -n '8,13p' src/server/json.nv
sed -n '51,52p' src/server/json.nv
sed -n '79,79p' src/server/json.nv
echo
echo "== carrier 1: the whole JSON export is concatenated past the door =="
grep -n "^import" src/server/handlers/exporter.nv
sed -n '223,250p' src/server/handlers/exporter.nv
echo
echo "   and r.model comes from someone else's JSON:"
sed -n '76,79p' src/usage/parse.nv
echo
echo "== carrier 2: the path list, twenty lines from the rule it breaks =="
sed -n '57,62p' src/server/dto.nv
sed -n '68,78p' src/server/dto.nv
echo "   (json.nv already has the correct spelling of exactly this:)"
sed -n '203,208p' src/server/json.nv
echo "   (and escape exists for the backslash a Windows path carries:)"
sed -n '18,20p' src/server/json_test.nv
echo
echo "== nothing tests the json export against a quote or a backslash =="
sed -n '151,162p' src/server/handlers/exporter_test.nv
