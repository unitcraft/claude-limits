#!/bin/sh
# One command, both states. Finds the repository root by walking up from this file.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/lint-openapi.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

run() {
  echo "--- $1 ---"
  python "$root/scripts/lint-openapi.py" "$here/$2/spec.json"
  echo "EXIT=$?"
}

run "GAP: the contract carries GET /api/debug/dump, which no row of 01.3 s2 has" gap
run "CONTROL: the other direction -- GET /api/export removed from the contract" control
