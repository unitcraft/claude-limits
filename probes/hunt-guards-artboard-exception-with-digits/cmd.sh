#!/bin/sh
# One command, both states. Each tree carries a BYTE-IDENTICAL copy of the guard
# (it takes no input and derives every path from __file__); the sha256 lines prove
# nothing was edited.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-artboard-labels.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

echo "--- the copies are the guard itself, unmodified ---"
sha256sum "$root/scripts/check-artboard-labels.py" \
          "$here/gap/scripts/check-artboard-labels.py" \
          "$here/control/scripts/check-artboard-labels.py"

echo "--- GAP: the artboard shows the label, the exceptions file excepts it, it has digits ---"
(cd "$here/gap" && python scripts/check-artboard-labels.py; echo "EXIT=$?")

echo "--- CONTROL: the same two files with the numbers taken out of the label ---"
(cd "$here/control" && python scripts/check-artboard-labels.py; echo "EXIT=$?")
