#!/bin/sh
# One command, both states. Finds the repository root by walking up from this file.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-fixtures.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

run() {
  echo "--- $1 ---"
  python "$root/scripts/check-fixtures.py" "$here/$2"
  echo "EXIT=$?"
}

run "GAP: two real user paths, in valid JSON, both spellings" gap
run "CONTROL: a token the scan can see, plus the ONE path spelling its regex matches" control
