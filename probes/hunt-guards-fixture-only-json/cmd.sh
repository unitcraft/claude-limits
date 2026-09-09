#!/bin/sh
# One command, both states, plus an inventory of the real tree.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-fixtures.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

run() {
  echo "--- $1 ---"
  python "$root/scripts/check-fixtures.py" "$here/$2"
  echo "EXIT=$?"
}

run "GAP: the same three secrets in a .toml, a .txt and a .claude.json.bak" gap
run "CONTROL: the same secrets inside a .json" control

echo "--- the real tree: how many fixture files exist, how many are opened ---"
python "$here/inventory.py" "$root/fixtures"
