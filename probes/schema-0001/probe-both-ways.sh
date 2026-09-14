#!/usr/bin/env bash
# Break the MIGRATION four ways, watch the schema test redden, put it back.
#
# The subject here is the SQL file, not Nova code — which is the point: a schema test
# that only ever sees one schema proves nothing about its own sensitivity.
set -uo pipefail
cd <repos>/claude-limits || exit 2

SRC=migrations/0001_init.sql
BAK='<repos>/claude-limits/.probe-schema.bak'
W='<repos>/claude-limits/migrations/0001_init.sql'
cp "$SRC" "$BAK" || exit 2

run() {
  out=$(./nova.sh test src/storage/ --filter schema_test 2>&1)
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
    echo "FAIL <- $(echo "$plain" | grep -oE 'FAIL: [a-z`].*' | head -1 | cut -c1-54)"
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

echo "A untouched (expect PASS):                            $(run)"

# A value dropped from a CHECK list — the silent kind: inserts keep working until
# somebody hits the missing one.
mutate "kind IN ('single','parent','empty','missing')" "kind IN ('single','parent','empty')"
echo "B1 a value falls out of folder.kind (expect FAIL):    $(run)"
cp "$BAK" "$SRC"

# The e-mail normalisation CHECK removed: the same person enters twice.
mutate "CONSTRAINT account_email_ck CHECK (email = lower(email) AND email = trim(email))" "CONSTRAINT account_email_ck CHECK (true)"
echo "B2 the e-mail CHECK stops checking (expect FAIL):     $(run)"
cp "$BAK" "$SRC"

# A service column gone from one table.
mutate "CREATE TABLE occupancy (
  id           UUID PRIMARY KEY," "CREATE TABLE occupancy (
  id           UUID PRIMARY KEY,
  is_current   BOOLEAN,"
echo "B3 an is_* column appears (expect FAIL):              $(run)"
cp "$BAK" "$SRC"

# The draft table F5 owns, shipped early.
mutate "-- ── 01.2 §3.17" "CREATE TABLE notification (id UUID PRIMARY KEY);

-- ── 01.2 §3.17"
echo "B4 notification ships early (expect FAIL):            $(run)"
cp "$BAK" "$SRC"

rm -f "$BAK"
echo "C restored (expect PASS):                             $(run)"
git -C <repos>/claude-limits status --porcelain -- migrations/
echo "(end)"
