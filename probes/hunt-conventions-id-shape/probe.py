# -*- coding: utf-8 -*-
"""What shape an identifier has is decided per fixture, and nothing checks it.

The convention says an identifier is a UUID v7 in canonical form (api.md section 11,
database.md section 3.3). Three of the four API fixtures obey; one does not, and part
of the page's tests are built on that one.

Run:  python probe.py     (reads only; writes nothing)
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
UUID7 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
ID_KEYS = ("id", "account_id", "login_dir_id", "folder_id")


def ids(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ID_KEYS and isinstance(v, str):
                out.add(v)
            ids(v, out)
    elif isinstance(node, list):
        for v in node:
            ids(v, out)


print("identifier shapes in the page fixtures:")
for f in sorted((REPO / "fixtures" / "api").glob("*.json")):
    found = set()
    ids(json.loads(f.read_text(encoding="utf-8")), found)
    bad = sorted(v for v in found if not UUID7.match(v))
    verdict = "all UUID v7" if not bad else "%d NOT UUID v7: %s" % (len(bad), bad[:4])
    print("  fixtures/api/%-24s %2d ids   %s" % (f.name, len(found), verdict))
print()

print("who would notice? every checker of the web set, run as check-web.mjs runs it:")
for name, args in (("check-fixtures.py", []), ("check-page.py", []),
                   ("check-config-fixture.py", []), ("check-dir-fixtures.py", []),
                   ("lint-openapi.py", ["fixtures/openapi/sample.json"])):
    p = subprocess.run([sys.executable, str(REPO / "scripts" / name), *args],
                       capture_output=True, text=True, cwd=str(REPO))
    in_output = "uuid" in (p.stdout or "").lower()
    in_source = "uuid" in (REPO / "scripts" / name).read_text(encoding="utf-8").lower()
    print("  %-24s exit=%d  'uuid' in its source: %-5s  in its output: %s"
          % (name, p.returncode, in_source, in_output))
print()
print("the convention, api.md:511 : | identifier | UUID v7 as a string |")
print("the acceptance, 01.3-api.md section 8 item 9, asks the CONTRACT for it;")
print("no check in this repository looks at the shape of an id in a FIXTURE.")

# the suite that reads this fixture, and what it asserts about ids:
suite_path = REPO / "scripts" / "test-render.mjs"
suite = suite_path.read_text(encoding="utf-8")
print()
print("who reads the fixture that disagrees:")
for i, l in enumerate(suite.splitlines(), 1):
    if "snapshot-mixed" in l:
        print("  scripts/test-render.mjs:%-4d %s" % (i, l.strip()[:76]))
print("  -> 27 tests of the list renderer (grep -c '^test(') run on ids of that shape;")
print("     none of them asserts anything about the shape of an id.")
