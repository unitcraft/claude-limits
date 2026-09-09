#!/bin/sh
# One command, both states.
#
# check-artboard-labels.py takes no input at all: it derives every path from its own
# location (ROOT = __file__.parent.parent). The only way to run it over a tree of my
# own is to put a BYTE-IDENTICAL copy of it in that tree; the sha256 lines below are
# the proof that nothing was edited. Nothing in the repository is touched.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-artboard-labels.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

echo "--- the copies are the guard itself, unmodified ---"
sha256sum "$root/scripts/check-artboard-labels.py" \
          "$here/gap/scripts/check-artboard-labels.py" \
          "$here/control/scripts/check-artboard-labels.py"

echo "--- GAP: seven design labels, produced by nothing, matched by noise ---"
(cd "$here/gap" && python scripts/check-artboard-labels.py; echo "EXIT=$?")

echo "--- CONTROL: the same tree with the noise removed from app.js ---"
(cd "$here/control" && python scripts/check-artboard-labels.py; echo "EXIT=$?")

echo "--- the real tree: which accepted labels occur ONLY inside a comment ---"
python "$here/where-matched.py" "$root"
