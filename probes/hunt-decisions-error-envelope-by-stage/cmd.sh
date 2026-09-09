#!/bin/sh
# Run from the repository root.
set -e
echo "== the three precise reasons apply() produces =="
sed -n '193,199p' src/server/handlers/config.nv
sed -n '473,473p' src/server/handlers/config.nv
echo
echo "== the one envelope all three get =="
sed -n '633,637p' src/server/handlers/config.nv
sed -n '198,202p' src/server/errors.nv
echo
echo "== the plan separates the two cases =="
sed -n '458,459p' docs/plans/01.3-api.md
echo
echo "== the test looks INSIDE errors[], not at the envelope =="
sed -n '271,278p' src/server/handlers/config_test.nv
echo "   (both 'code' keys exist in one body:)"
sed -n '256,268p' src/server/errors.nv
echo
echo "== the same question, answered differently in three other handlers =="
grep -n "extra_forbidden(extra)\|invalid_request(\[FieldError" src/server/handlers/refresh.nv src/server/handlers/token.nv src/server/handlers/folders.nv
