#!/bin/sh
# One command, both states. Finds the repository root by walking up from this file.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-page.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

run() {
  echo "--- $1 ---"
  python "$root/scripts/check-page.py" "$here/$2"
  echo "EXIT=$?"
}

run "GAP: the dot is repainted in every state, and repainted GREEN" web-gap
run "CONTROL: the polling rule deleted" web-control
