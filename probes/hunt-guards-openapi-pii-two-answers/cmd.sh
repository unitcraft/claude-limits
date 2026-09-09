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

run "GAP: folder_path / user_email / access_token, in the URL and in a schema at once" gap
run "CONTROL: the same three values in the URL under the four bare names rule 4 lists" control
