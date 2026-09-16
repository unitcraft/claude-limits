#!/usr/bin/env bash
# Break repo.nv four ways, watch it redden, put it back.
#
# Every mutation here is a rule the card names, and each one is the kind that ships
# quietly: a journal entry written first, a fact that overwrites itself, a rollback
# that does not happen, a value that goes in unquoted.
set -uo pipefail
# The repository root is DERIVED, not written down: this file is public, and a
# hard-coded path both leaks the author's disk layout and breaks on every other
# machine. `$0` is inside `probes/<name>/`, so the root is two levels up.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$R" || exit 2

SRC=src/storage/repo.nv
BAK="$R/.probe-repo.bak"
W="$R/src/storage/repo.nv"
cp "$SRC" "$BAK" || exit 2

run() {
  out=$(./nova.sh test src/storage/ --filter repo_test 2>&1)
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
    echo "FAIL <- $(echo "$plain" | grep -oE 'FAIL: [a-z`].*' | head -1 | cut -c1-52)"
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

echo "A untouched (expect PASS):                              $(run)"

# The journal first instead of last: a failure then leaves `poll` claiming a reading
# whose samples were never written.
mutate '    out.push(upsert_account_sql(t, ids.account))' '    out.push(insert_poll_sql(t, ids.poll, ids.account))
    out.push(upsert_account_sql(t, ids.account))'
echo "B1 the journal goes FIRST (expect FAIL):                $(run)"
cp "$BAK" "$SRC"

# No rollback on failure: a half-written tick stays.
mutate '                ro _ = Db.exec(conn, "ROLLBACK")
                return Err(e)' '                return Err(e)'
echo "B2 a failure does not roll back (expect FAIL):          $(run)"
cp "$BAK" "$SRC"

# Facts overwrite themselves: the second identical tick changes the row.
mutate 'ON CONFLICT (window_id, sampled_at) DO NOTHING' 'ON CONFLICT (window_id, sampled_at) DO UPDATE SET percent = excluded.percent'
echo "B3 a repeated sample overwrites (expect FAIL):          $(run)"
cp "$BAK" "$SRC"

# Quoting stops doubling: one apostrophe from the endpoint ends the literal.
#
# The anchor is the LOOP rather than the branch inside it: the branch is one line of
# nested quotes, and it could not survive shell -> python -> Nova escaping. The probe
# ABORTED rather than printing a row, which is how that was noticed.
mutate "    for ch in s.chars() {" "    for ch in EMPTY.chars() {"
echo "B4 quoting stops doubling (expect FAIL):                $(run)"
cp "$BAK" "$SRC"

rm -f "$BAK"
echo "C restored (expect PASS):                               $(run)"
git -C "$R" status --porcelain -- src/storage/
echo "(end)"
