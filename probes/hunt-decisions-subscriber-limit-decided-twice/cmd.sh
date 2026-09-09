#!/bin/sh
# Run from the repository root.
set -e
echo "== one number, written twice, neither exported =="
grep -rn "MAX_SUBSCRIBERS" src/ --include=*.nv | grep -v "_test.nv"
echo
echo "== decision one: the registry admits =="
sed -n '62,75p' src/model/store.nv
echo
echo "== decision two: the handler refuses, on the same state, without asking =="
sed -n '98,106p' src/server/handlers/events.nv
sed -n '151,163p' src/server/handlers/events.nv
echo
echo "== the counter kept by one of them, meant for the other's endpoint =="
sed -n '40,40p' src/model/store.nv
grep -n "rejected" src/server/handlers/health.nv || echo "   HealthState has no field for it"
echo
echo "== the plan states the limit once =="
sed -n '313,314p' docs/plans/01.3-api.md
