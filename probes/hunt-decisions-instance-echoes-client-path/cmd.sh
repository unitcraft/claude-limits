#!/bin/sh
# Run from the repository root.
set -e
echo "== the door, and the sentinel in it =="
sed -n '204,208p' src/server/routes.nv
echo
echo "== who passes the sentinel today =="
grep -n 'api(""' src/server/routes.nv
echo "   and everything under /api/ that is not registered reaches it:"
sed -n '110,112p' src/server/static.nv
echo
echo "== the plan wants a template =="
sed -n '72,73p' docs/plans/01.3-api.md
echo
echo "== the convention wants a template, and says why =="
sed -n '282,282p' docs/conventions/api.md
echo "   and the checklist repeats it:"
sed -n '709,709p' docs/conventions/api.md
echo
echo "== the code records the choice knowingly =="
sed -n '86,90p' src/server/routes.nv
echo
echo "== and the value lands verbatim in the body =="
sed -n '255,257p' src/server/errors.nv
echo
echo "== the test pins the echo =="
sed -n '109,112p' src/server/routes_test.nv
echo
echo "== recorded deviations of the plan (count), none of them this one =="
grep -c "^| D[0-9]" docs/plans/01.3-api.md
