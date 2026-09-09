#!/bin/sh
# One command, both states. `checkout/` is a stand-in for a second working copy of
# this repository: it carries BYTE-IDENTICAL copies of the two guards (the sha256
# lines below prove it) and a src/web + fixtures of its own, with five violations.
here=$(cd "$(dirname "$0")" && pwd)
root=$here
while [ "$root" != "/" ] && [ ! -f "$root/scripts/check-page.py" ]; do root=$(dirname "$root"); done
export PYTHONIOENCODING=utf-8

echo "--- the copies are the guards themselves, unmodified ---"
sha256sum "$root/scripts/check-page.py" "$here/checkout/scripts/check-page.py" \
          "$root/scripts/check-fixtures.py" "$here/checkout/scripts/check-fixtures.py"

cd "$here/checkout" || exit 1

echo "--- GAP: run them from inside this checkout, the way check-web.mjs does (no argument) ---"
python scripts/check-page.py
echo "PAGE EXIT=$?"
python scripts/check-fixtures.py | tail -3
echo "FIXTURES EXIT=${PIPESTATUS[0]}"

echo "--- CONTROL: the same guards, this checkout named explicitly ---"
python scripts/check-page.py src/web
echo "PAGE EXIT=$?"
python scripts/check-fixtures.py fixtures | tail -4
echo "FIXTURES EXIT=${PIPESTATUS[0]}"
