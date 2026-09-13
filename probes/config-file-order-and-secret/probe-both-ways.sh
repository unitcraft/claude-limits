#!/usr/bin/env bash
# Break config_file.nv four ways, watch it redden, put it back.
#
# Lessons already paid for and carried here: the editing python is native Windows and
# needs a Windows path; a mutation that fails to apply ABORTS instead of printing a
# verdict; and the runner is asked to REFUSE when it could not measure, because a peer
# rebuilding nova-cli once made this shape print six failures against a clean tree.
set -uo pipefail
cd <repos>/claude-limits || exit 2

SRC=src/storage/config_file.nv
BAK='<repos>/claude-limits/.probe-cfgfile.bak'
W='<repos>/claude-limits/src/storage/config_file.nv'
cp "$SRC" "$BAK" || exit 2

run() {
  out=$(./nova.sh test src/storage/ 2>&1)
  plain=$(echo "$out" | sed -e 's/\x1b\[[0-9;]*m//g')
  if echo "$plain" | grep -q "nova binary not found"; then
    echo "REFUSED: no compiler; nothing was measured"; return 2
  fi
  if ! echo "$plain" | grep -qE '^PASS: [0-9]+ '; then
    echo "REFUSED: the run did not reach a verdict"; return 2
  fi
  if echo "$plain" | grep -qE '^PASS: 2  FAIL: 0'; then
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

echo "A untouched (expect PASS):                        $(run)"

# The secret. If redaction stops happening, the token reaches the database.
mutate '            ro indent = " ".repeat(line.byte_len() - t.byte_len())
            "${indent}access_token = \\"***\\""' '            ro indent = " ".repeat(line.byte_len() - t.byte_len())
            "${indent}${line.trim_ascii_start()}"'
echo "B1 the token is NOT redacted (expect FAIL):       $(run)"
cp "$BAK" "$SRC"

# The order. History after the write keeps the NEW text, which has no token line.
mutate '    if !before.missing && before.text != "" {
        ConfigHistory.save(redact(before.text), source.to_str())
    }

    match write_atomic(path.to_path(), render(cfg).bytes()) {
        Ok(_) => Written
        Err(_) => WriteFailed
    }' '    ro wrote = match write_atomic(path.to_path(), render(cfg).bytes()) {
        Ok(_) => Written
        Err(_) => WriteFailed
    }
    if !before.missing && before.text != "" {
        ConfigHistory.save(redact(load(path).text), source.to_str())
    }
    wrote'
echo "B2 history written AFTER the file (expect FAIL):  $(run)"
cp "$BAK" "$SRC"

# The conflict check. Without it a stale editor silently overwrites a newer file.
mutate '    if changed(before, mtime_of(path), file_there(path)) { return Conflict }' '    ro _unused_conflict = changed(before, mtime_of(path), file_there(path))'
echo "B3 no conflict check (expect FAIL):               $(run)"
cp "$BAK" "$SRC"

# A failed write reported as success -- the shape that loses a settings file quietly.
mutate '        Err(_) => WriteFailed
    }
}' '        Err(_) => Written
    }
}'
echo "B4 a failed write reports success (expect FAIL):  $(run)"
cp "$BAK" "$SRC"

rm -f "$BAK"
echo "C restored (expect PASS):                         $(run)"
git -C <repos>/claude-limits status --porcelain -- src/storage/
echo "(end)"
