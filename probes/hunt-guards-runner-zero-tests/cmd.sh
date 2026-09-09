#!/bin/sh
# One command, both states.
#
# check-web.mjs takes no input but its own directory, so the only way to run it over
# a tree of my own is a BYTE-IDENTICAL copy inside that tree; the sha256 lines are the
# proof that nothing was edited. The eight python checkers it calls are 2-line stubs
# here, so the only thing under test is the runner's own arithmetic.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-web.mjs" ]; do root=$(dirname "$root"); done

echo "--- the copy is the runner itself, unmodified ---"
sha256sum "$root/scripts/check-web.mjs" "$here/gap/scripts/check-web.mjs"

echo "--- GAP: the only suite iterates an empty directory and runs zero tests ---"
(cd "$here/gap" && node scripts/check-web.mjs; echo "EXIT=$?")

echo "--- CONTROL: the suite FILE is gone -- the one emptiness the runner does refuse ---"
(cd "$here/control" && node scripts/check-web.mjs; echo "EXIT=$?")
