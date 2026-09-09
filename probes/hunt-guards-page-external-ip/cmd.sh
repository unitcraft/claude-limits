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

run "GAP: three external pulls addressed by IP (script, preconnect, @font-face)" web-gap
run "CONTROL: the same pull with a named host" web-control
