#!/bin/sh
# Evidence for a CONTRADICTION, not a finding. See CONTRADICTION.md.
#
# check-web.mjs takes no input but its own directory, so each tree carries a
# BYTE-IDENTICAL copy of it; the sha256 lines prove nothing was edited. The eight
# python checkers it calls are 2-line stubs here.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-web.mjs" ]; do root=$(dirname "$root"); done

echo "--- the copy is the runner itself, unmodified ---"
sha256sum "$root/scripts/check-web.mjs" "$here/gap/scripts/check-web.mjs"

echo "--- GAP: a failing check-*.py sits in scripts/ ---"
(cd "$here/gap" && node scripts/check-web.mjs; echo "EXIT=$?")

echo "--- CONTROL: the same failure named test-*.mjs ---"
(cd "$here/control" && node scripts/check-web.mjs; echo "EXIT=$?")
