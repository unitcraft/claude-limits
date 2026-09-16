#!/usr/bin/env bash
# Break the poller and the module that owns its floor, watch both redden, restore.
#
# B4 moved. The first version mutated `wait_after`'s fallback in poller.nv and the
# suite stayed green -- because that fallback was unreachable: every constructor in
# `outcome.nv` already sets at least the floor. The dead branch is gone and the
# guarantee now lives where it is PROVIDED, so B4 mutates `outcome.nv` instead.
#
# Two files are therefore backed up and restored, and the whole `src/usage/` suite is
# what judges, not just the poller filter -- a mutation in `outcome.nv` must be
# allowed to redden `outcome_test` too.
set -uo pipefail
# The repository root is DERIVED, not written down: this file is public, and a
# hard-coded path both leaks the author's disk layout and breaks on every other
# machine. `$0` is inside `probes/<name>/`, so the root is two levels up.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$R" || exit 2

P_SRC=src/usage/poller.nv
O_SRC=src/usage/outcome.nv
P_BAK="$R/.probe-poller.bak"
O_BAK="$R/.probe-outcome.bak"
P_W="$R/src/usage/poller.nv"
O_W="$R/src/usage/outcome.nv"
cp "$P_SRC" "$P_BAK" || exit 2
cp "$O_SRC" "$O_BAK" || exit 2

restore() { cp "$P_BAK" "$P_SRC"; cp "$O_BAK" "$O_SRC"; }

run() {
  out=$(./nova.sh test src/usage/ 2>&1)
  plain=$(echo "$out" | sed -e 's/\x1b\[[0-9;]*m//g')
  # Refuse before judging: "could not look" must never print as "looked and found
  # nothing". Measured -- a peer rebuilding nova-cli briefly removed the compiler and
  # the first version of this probe called that six failures.
  if echo "$plain" | grep -q "nova binary not found"; then
    echo "REFUSED: no compiler; nothing was measured"; return 2
  fi
  if ! echo "$plain" | grep -qE '^PASS: [0-9]+ '; then
    echo "REFUSED: the run did not reach a verdict"; return 2
  fi
  if echo "$plain" | grep -qE '^PASS: 5  FAIL: 0'; then
    echo "PASS"
  else
    echo "FAIL <- $(echo "$plain" | grep -oE 'FAIL: [a-z].*' | head -1 | cut -c1-58)"
  fi
}

mutate() {
  python -c "
import io,sys
s=io.open(r'$1',encoding='utf-8',newline='').read()
o='''$2'''; n='''$3'''
if s.count(o)!=1:
    sys.exit('MUTATION DID NOT APPLY: %d matches for %r' % (s.count(o), o[:44]))
io.open(r'$4','w',encoding='utf-8',newline='').write(s.replace(o,n,1))
" || { echo "PROBE ABORTED: could not mutate"; restore; exit 3; }
}

echo "A untouched (expect PASS):                     $(run)"

mutate "$P_BAK" "    if !due(p, iv, now_ms) { return (p, false) }" "    ro _unused_due = due(p, iv, now_ms)" "$P_W"
echo "B1 tick ignores the schedule (expect FAIL):    $(run)"
cp "$P_BAK" "$P_SRC"

mutate "$P_BAK" "    PollLog.record(a.email, got.outcome.state.to_str(), got.outcome.message, now_ms)" "    ro _unrecorded = a.email" "$P_W"
echo "B2 nothing is written down (expect FAIL):      $(run)"
cp "$P_BAK" "$P_SRC"

mutate "$P_BAK" "    if !refresh_allowed(p, now_ms) { return (p, false) }" "    ro _unused_ra = refresh_allowed(p, now_ms)" "$P_W"
echo "B3 refresh ignores the floor (expect FAIL):    $(run)"
cp "$P_BAK" "$P_SRC"

# The floor, mutated where it is DECIDED rather than where it is consumed.
mutate "$O_BAK" "    if status == 200 {
        return Outcome.of(AccountState.Ok, \"\", POLL_FLOOR_SEC, true)" "    if status == 200 {
        return Outcome.of(AccountState.Ok, \"\", 0, true)" "$O_W"
echo "B4 a 200 asks for no wait at all (expect FAIL): $(run)"
cp "$O_BAK" "$O_SRC"

restore
rm -f "$P_BAK" "$O_BAK"
echo "C restored (expect PASS):                      $(run)"
git -C "$R" status --porcelain -- src/usage/
echo "(end)"
