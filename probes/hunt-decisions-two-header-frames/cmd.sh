#!/bin/sh
# Run from the repository root.
set -e
echo "== door one =="
sed -n '130,138p' src/server/routes.nv
echo
echo "== door two, same name, four headers instead of six =="
sed -n '71,77p' src/server/static.nv
echo
echo "== the plan wants the id on EVERY response =="
sed -n '680,682p' docs/plans/01.3-api.md
echo
echo "== the convention wants it on file responses by name =="
sed -n '400,409p' docs/conventions/api.md
echo
echo "== the code calls the omission deliberate =="
sed -n '25,27p' src/server/static.nv
echo
echo "== and the test pins the four-header set =="
sed -n '102,111p' src/server/static_test.nv
echo
echo "== deviation table of the plan: no row for it =="
grep -n "X-Request-Id" docs/plans/01.3-api.md | sed -n '1,20p'
echo "-- rows D1..D8 of section 9:"
grep -n "^| D[0-9]" docs/plans/01.3-api.md
