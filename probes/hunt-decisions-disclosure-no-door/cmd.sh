#!/bin/sh
# Run from the repository root. Shows one question answered in six places.
set -e
echo "== the only thing the frame gives every handler (no disclosure in it) =="
sed -n '83,91p' src/server/routes.nv
echo
echo "== the same decision, six independent state records =="
grep -n "disclosure Disclosure" src/server/handlers/*.nv
echo
echo "== the seventh handler has no such field and prints an e-mail anyway =="
sed -n '27,32p' src/server/handlers/refresh.nv
grep -n 'field_str("email", t.email)' src/server/handlers/refresh.nv
echo
echo "== two of those six fields are ACCESS CONTROL, not redaction =="
sed -n '154,160p' src/server/handlers/token.nv
sed -n '203,211p' src/server/handlers/exporter.nv
echo
echo "== and no function anywhere maps a request to a Disclosure =="
grep -rn "Disclosure" src/ --include=*.nv | grep -v "_test.nv" | grep -c ""
grep -rn "fn .*-> Disclosure" src/ --include=*.nv || echo "  (no producer: zero matches)"
