#!/usr/bin/env bash
# Break db.nv four ways, watch it redden, put it back.
#
# Carried forward from every probe before it: a Windows path for the native python, a
# mutation that ABORTS rather than printing a verdict when it fails to apply, and a
# runner that REFUSES when it could not measure instead of reporting a failure.
set -uo pipefail
# The repository root is DERIVED, not written down: this file is public, and a
# hard-coded path both leaks the author's disk layout and breaks on every other
# machine. `$0` is inside `probes/<name>/`, so the root is two levels up.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$R" || exit 2

SRC=src/storage/db.nv
BAK="$R/.probe-db.bak"
W="$R/src/storage/db.nv"
cp "$SRC" "$BAK" || exit 2

run() {
  out=$(./nova.sh test src/storage/ --filter db_test 2>&1)
  plain=$(echo "$out" | sed -e 's/\x1b\[[0-9;]*m//g')
  if echo "$plain" | grep -q "nova binary not found"; then
    echo "REFUSED: no compiler; nothing was measured"; return 2
  fi
  if ! echo "$plain" | grep -qE '^PASS: [0-9]+ '; then
    echo "REFUSED: the run did not reach a verdict"; return 2
  fi
  if echo "$plain" | grep -qE '^PASS: 1  FAIL: 0'; then
    echo "PASS"
  else
    echo "FAIL <- $(echo "$plain" | grep -oE 'FAIL: [a-z].*' | head -1 | cut -c1-56)"
  fi
}

mutate() {
  python -c "
import io,sys
s=io.open(r'$BAK',encoding='utf-8',newline='').read()
o='''$1'''; n='''$2'''
if s.count(o)!=1:
    sys.exit('MUTATION DID NOT APPLY: %d matches for %r' % (s.count(o), o[:44]))
io.open(r'$W','w',encoding='utf-8',newline='').write(s.replace(o,n,1))
" || { echo "PROBE ABORTED: could not mutate"; cp "$BAK" "$SRC"; exit 3; }
}

echo "A untouched (expect PASS):                          $(run)"

# The refusal the card names: a database from the future must not open.
mutate "export fn too_new(found int) -> bool => found > KNOWN_SCHEMA" "export fn too_new(found int) -> bool => false"
echo "B1 a future schema opens anyway (expect FAIL):      $(run)"
cp "$BAK" "$SRC"

# Counting instead of filtering — the bug a gap in the numbering hides.
mutate "            if !taken[i] && all[i].version > have {" "            if !taken[i] {"
echo "B2 pending ignores what we already have (FAIL):     $(run)"
cp "$BAK" "$SRC"

# A fresh database reported as somebody else's: a log line on every first start.
mutate "    if before == \"\" { return false }" "    if before == \"\" { return true }"
echo "B3 an empty owner counts as a change (FAIL):        $(run)"
cp "$BAK" "$SRC"

# The key regenerated on every start: the history becomes unreadable at the next boot.
mutate "        Ok(true) => {
            match read_text(key_path.to_path()) {
                Ok(s) => Ok(s.trim_ascii())
                Err(_) => Err(KeyUnreadable)
            }
        }" "        Ok(true) => {
            Ok(Base64.encode_url(Random.bytes(KEY_BYTES)))
        }"
echo "B4 the key is regenerated, not read (expect FAIL):  $(run)"
cp "$BAK" "$SRC"

rm -f "$BAK"
echo "C restored (expect PASS):                           $(run)"
git -C "$R" status --porcelain -- src/storage/
echo "(end)"
