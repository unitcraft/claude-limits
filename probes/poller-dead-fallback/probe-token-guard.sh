#!/usr/bin/env bash
# The token guard, both ways. Focused: the other four mutations of this file are
# already proven in probes/poller-dead-fallback/, and only the new code needs its own
# proof -- but it still gets A and C, because a mutation row without them says nothing
# about whether the suite was green to begin with.
set -uo pipefail
cd <repos>/claude-limits || exit 2

SRC=src/usage/poller.nv
BAK='<repos>/claude-limits/.probe-token.bak'
W='<repos>/claude-limits/src/usage/poller.nv'
cp "$SRC" "$BAK" || exit 2

run() {
  out=$(./nova.sh test src/usage/ --filter poller 2>&1)
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
    echo "FAIL <- $(echo "$plain" | grep -oE 'FAIL: [a-z].*' | head -1 | cut -c1-58)"
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

echo "A untouched (expect PASS):                       $(run)"

mutate "        TokenState.Stale => false
        TokenState.NoToken => false" "        TokenState.Stale => true
        TokenState.NoToken => true"
echo "B1 a dead token is asked anyway (expect FAIL):   $(run)"
cp "$BAK" "$SRC"

# The mirror: refusing everyone would also make "zero calls" true, and the control
# test exists precisely to catch it.
mutate "        TokenState.Ok => true" "        TokenState.Ok => false"
echo "B2 nobody is ever asked (expect FAIL):           $(run)"
cp "$BAK" "$SRC"

rm -f "$BAK"
echo "C restored (expect PASS):                        $(run)"
git -C <repos>/claude-limits status --porcelain -- src/usage/
echo "(end)"
