#!/bin/sh
# Run from the repository root.
set -e
echo "== the decision, written down and argued =="
sed -n '19,25p' src/server/json.nv
echo
echo "== the door knows the scale and does not require it (int in, int out) =="
sed -n '140,145p' src/server/json.nv
echo
echo "== one quantity, four scales =="
sed -n '56,57p' src/model/forecast.nv
sed -n '88,91p' src/model/forecast.nv
sed -n '106,106p' src/model/forecast.nv
sed -n '156,158p' src/server/dto.nv
sed -n '240,240p' src/server/dto.nv
echo
echo "== and nothing converts Forecast into ForecastView =="
grep -rn "ForecastView" src/ --include=*.nv | grep -v "_test.nv"
echo
echo "== the suffix that already lies: bp means 1/10000, the doc says hundredths =="
sed -n '192,194p' src/server/dto.nv
sed -n '267,267p' src/server/dto.nv
echo
echo "== what the plan expects on the wire =="
sed -n '34,35p' docs/plans/01.3-api.md
sed -n '261,261p' docs/plans/01.3-api.md
