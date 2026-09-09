#!/bin/sh
# Full command. Two runs: the machine's own zone, and UTC.
# (node on this Windows box honours TZ=UTC and ignores other zone names -- so the
#  second run is UTC, and the first is whatever the machine is set to. The point is
#  that the answer MOVES with the machine, while the server's label does not.)
cd "$(dirname "$0")" || exit 1
echo "=== run 1: this machine's own zone ==="
node probe.mjs
echo
echo "=== run 2: the same page open in a UTC browser ==="
TZ=UTC node probe.mjs
