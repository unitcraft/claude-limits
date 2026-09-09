#!/bin/sh
# Run from the repository root.
set -e
echo "== description one: what GET emits =="
sed -n '176,190p' src/server/handlers/config.nv
echo
echo "== description two: what PUT accepts =="
sed -n '515,522p' src/server/handlers/config.nv
echo
echo "== divergence 1: the plan puts folders INSIDE config =="
sed -n '411,414p' docs/plans/01.3-api.md
echo "   render_state puts it at the root (line 185 above); apply reads it inside (line 519)"
echo
echo "== divergence 2: two keys are emitted and not accepted =="
sed -n '144,148p' src/server/handlers/config.nv
sed -n '331,348p' src/server/handlers/config.nv
echo
echo "== divergence 3: the plan names tls_key and tls_fingerprint =="
sed -n '419,419p' docs/plans/01.3-api.md
sed -n '430,431p' docs/plans/01.3-api.md
grep -n "tls_fingerprint" src/ -r --include=*.nv || echo "   tls_fingerprint: absent from the whole tree"
echo
echo "== and no test compares the key SET with the contract =="
sed -n '120,135p' src/server/handlers/config_test.nv
