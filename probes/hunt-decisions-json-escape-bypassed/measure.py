# -*- coding: utf-8 -*-
"""Does every string in the export go through the escaper?

    python probes/hunt-decisions-json-escape-bypassed/measure.py

THE DEFECT, until 2026-09-09. `rows_to_json` in server/handlers/exporter.nv built its
document by hand and pushed six string fields straight in -- at, account_id, email,
kind, model, resets_at. The file did not import `json` at all, so the escaper it was
supposed to use was not even in scope.

WHY IT MATTERS MORE THAN IT LOOKS. An e-mail is the thing an export exists to carry,
and RFC 5321 allows a quote inside the local part. One such address and the export
stops being JSON: the consumer gets a parse error at a byte offset rather than "your
data has an odd character in it". A backslash is worse because it is quiet -- it
escapes whatever follows, so a Windows path changes the SHAPE of the document instead
of breaking it, and the consumer reads different data without any error at all.

`json.nv`'s own header records that this class was found and fixed once before. It
came back in the one handler that writes JSON by hand.

WHAT THIS CHECKS. Source, not runtime: the handler is Nova and building it here would
mean a compiler and a DuckDB build for one assertion. So the check is that no string
field reaches the document without `quote`, and that the file imports it. The escaper
itself has its own tests next to json.nv.
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "server" / "handlers" / "exporter.nv"

bad = 0


def fail(msg):
    global bad
    print("  FAIL:", msg)
    bad = 1


if not SRC.exists():
    print("  FAIL: exporter.nv not found -- this probe measured nothing")
    sys.exit(1)

text = SRC.read_text(encoding="utf-8")

# 1. The escaper must be in scope at all.
if not re.search(r"import\s+claude_limits\.server\.json\.\{[^}]*\bquote\b", text):
    fail("exporter.nv does not import `quote` -- the escaper is not even in scope")
else:
    print("imports quote: yes")

# 2. The function under test.
m = re.search(r"fn rows_to_json\([^)]*\)[^{]*\{(.*?)\n\}", text, re.S)
if not m:
    fail("cannot find rows_to_json -- renamed? this probe needs updating")
    sys.exit(1)
body = m.group(1)

# 3. THE DEFECT'S SIGNATURE: a string literal that OPENS a JSON string and is
#    followed by a bare append of a value. In the old code every field looked like
#        sb.append("{\"at\":\"")
#        sb.append(r.at)
#    so an append whose argument ends in an unterminated quote is the tell.
opens = re.findall(r'sb\.append\("[^"]*\\"\)\s*\n\s*sb\.append\(([^)]+)\)', body)
raw = [o.strip() for o in opens if "quote(" not in o]
if raw:
    fail(f"{len(raw)} value(s) appended straight into an open JSON string: {raw}")
else:
    print("no value appended into an open string literal")

# 4. And positively: every field of Row that is a string must appear inside quote().
STRING_FIELDS = ["at", "account_id", "kind", "model", "resets_at"]
missing = [f for f in STRING_FIELDS if f"quote(r.{f})" not in body]
if missing:
    fail(f"string fields not passed through quote: {missing}")
else:
    print(f"all {len(STRING_FIELDS)} string fields of Row go through quote")

# The e-mail is computed into a local first (masked or not), so it is checked by name.
if "quote(email)" not in body:
    fail("the e-mail -- the field this export exists to carry -- is not quoted")
else:
    print("the e-mail goes through quote")

# 5. A control: the NUMERIC and BOOLEAN fields must NOT be quoted, or the document
#    would carry numbers as strings and every consumer would need to convert them.
for f, why in (("percent", "a number"), ("locked", "a boolean")):
    if f"quote(r.{f})" in body or (f == "locked" and "quote(bool_str" in body):
        fail(f"{f} is quoted, but it is {why} -- quoting everything is not the fix")
print("percent and locked are left unquoted, as they must be")

print("\nFAILED" if bad else "\nOK: every string in the export is escaped, and only the strings")
sys.exit(bad)
