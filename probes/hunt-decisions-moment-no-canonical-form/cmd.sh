#!/bin/sh
# Run from the repository root.
set -e
echo "== the rule =="
sed -n '37,40p' docs/plans/01.3-api.md
echo
echo "== the inbound half exists and is one door =="
sed -n '97,106p' src/usage/parse.nv
echo
echo "== inside, a moment is an integer =="
grep -n "_ms int" src/window.nv src/model/store.nv
echo
echo "== on the wire, a moment is a bare str with no constructor =="
grep -n "fetched_at str\|next_poll_at str\|polled_at str\|resets_at str\|runs_out_at str\|    at str" src/server/dto.nv src/server/handlers/exporter.nv
echo
echo "== and nothing in the tree produces the canonical spelling =="
echo "-- functions returning an ISO string:"
grep -rn "fn .*_iso\|fn .*iso_\|fn .*_utc\|fn .*utc_" src/ --include=*.nv | grep -v "_test.nv" || echo "   (none)"
echo "-- every non-test mention of to_iso or a Z literal:"
grep -rn "to_iso" src/ --include=*.nv | grep -v "_test.nv" || echo "   (none)"
echo
echo "== meanwhile the ETag hashes that unvalidated string =="
sed -n '196,200p' src/server/handlers/snapshot.nv
