#!/bin/sh
# Run from the repository root.
set -e
echo "== the frame checks size and content-type, never the query =="
sed -n '193,199p' src/server/routes.nv
echo
echo "== two verbatim copies of the parser (diff must be empty) =="
sed -n '50,66p' src/server/handlers/snapshot.nv > /tmp/qp_snapshot.txt
sed -n '134,150p' src/server/handlers/exporter.nv > /tmp/qp_exporter.txt
diff /tmp/qp_snapshot.txt /tmp/qp_exporter.txt && echo "  IDENTICAL"
echo
echo "== and they already answer 'may a parameter repeat?' differently =="
sed -n '84,87p' src/server/handlers/snapshot.nv
sed -n '181,201p' src/server/handlers/exporter.nv
echo
echo "== five handlers never look at the query at all =="
for f in health events folders token; do
  echo "--- $f"
  grep -n "query\|target()" src/server/handlers/$f.nv || echo "    (no query handling)"
done
echo "--- config"
grep -n "query\|target()" src/server/handlers/config.nv || echo "    (no query handling)"
echo
echo "== the plan says the list is closed on EVERY route =="
sed -n '49,50p' docs/plans/01.3-api.md
echo "== and that /api/events takes no query at all =="
sed -n '298,299p' docs/plans/01.3-api.md
