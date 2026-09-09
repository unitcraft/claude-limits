#!/bin/sh
# One command, both states. Finds the repository root by walking up from this file,
# so the probe keeps working after it is moved.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-page.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

run() {
  echo "--- $1 ---"
  python "$root/scripts/check-page.py" "$here/$2"
  echo "EXIT=$?"
}

run "GAP: four inline blocks the CSP refuses (data-src, <SCRIPT>, <STYLE>, onclick)" web-gap
run "CONTROL: the same code in the one form the regex knows" web-control
