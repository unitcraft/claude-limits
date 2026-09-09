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

run "GAP: two error responses that are not RFC 9457, saying the WORD Problem" gap
run "CONTROL: the same response with the word removed" control
