# -*- coding: utf-8 -*-
"""Does the linter's forbidden-parameter list come from the registry, or from itself?

    python probes/hunt-conventions-pii-blacklist/measure.py

THE RULE. Database convention 13.7: "Реестр единственный источник для всех
производных проверок: списка полей, запрещённых в URL, ...". API convention 593-596
from the other side: "Ни один из этих списков не ведётся руками отдельно."

THE DEFECT, until 2026-09-09. `lint-openapi.py` carried
`FORBIDDEN_PARAM_NAMES = ("email", "path", "token", "account_id")` as a literal --
four names against the registry's rows -- four lines below a header paragraph
explaining why the ROUTE list is parsed rather than copied: "a second list in this
file would just drift away from the first". One rule, one file, two opposite
decisions, and the copy had already drifted.

WHAT THIS CHECKS, in both directions:
  1. the list is derived, and covers the registry's pii/subject_id/secret rows;
  2. adding a row to the registry adds a name, without touching the linter;
  3. an empty or unparseable registry makes the linter REFUSE rather than lint with
     an empty list -- a check with nothing to check passes everything.
"""
import importlib.util
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
LINTER = REPO / "scripts" / "lint-openapi.py"


def load():
    spec = importlib.util.spec_from_file_location("lint_openapi_probe", LINTER)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bad = 0


def check(cond, msg):
    global bad
    if not cond:
        print("  FAIL:", msg)
        bad = 1


m = load()
names = set(m.FORBIDDEN_PARAM_NAMES)
print("derived names (%d): %s" % (len(names), ", ".join(sorted(names))))

# 1. It is not the old literal.
check(names != {"email", "path", "token", "account_id"},
      "the list is still the four hand-written names")

# The registry's rows must be represented. These come FROM the table, so if the table
# changes and these disappear, this probe is what says so.
for expected in ("email", "account_email", "path", "folder_path", "login_dir_path",
                 "org_name", "account_org_name", "account_id", "access_token", "token"):
    check(expected in names, f"{expected!r} is in the registry but not in the list")

# `id` alone is deliberately NOT forbidden -- the linter says why in a comment. Assert
# the decision, so that reversing it has to be deliberate too.
check("id" not in names,
      "a bare `id` is forbidden; that rejects a notification id along with an account id")

# 2. A row added to the registry reaches the list, with no edit to the linter.
storage = REPO / "docs" / "plans" / "01.2-storage.md"
text = storage.read_text(encoding="utf-8")
marker = "| `account.org_name` |"
if marker not in text:
    print("  FAIL: cannot find a row to clone; the registry's shape changed")
    bad = 1
else:
    row = [l for l in text.split("\n") if l.startswith(marker)][0]
    invented = row.replace("`account.org_name`", "`account.probe_invented_field`", 1)
    patched = text.replace(row, row + "\n" + invented, 1)
    tmp = pathlib.Path(tempfile.mkdtemp()) / "01.2-storage.md"
    tmp.write_text(patched, encoding="utf-8")
    grown = set(m._forbidden_from_registry(tmp))
    print("with one invented registry row: %d names" % len(grown))
    check("probe_invented_field" in grown,
          "a new registry row did not reach the list -- the derivation is not reading it")
    check("account_probe_invented_field" in grown,
          "the table_column spelling is missing for a new row")

# 3. An empty registry must REFUSE, not pass.
empty = pathlib.Path(tempfile.mkdtemp()) / "01.2-storage.md"
empty.write_text("## 10. nothing here\n\nno table at all.\n", encoding="utf-8")
try:
    m._forbidden_from_registry(empty)
    print("  FAIL: an empty registry produced a list instead of refusing")
    bad = 1
except SystemExit as e:
    print("empty registry -> refused:", str(e).split("\n")[0][:80])

# A missing registry file, likewise.
missing = pathlib.Path(tempfile.mkdtemp()) / "absent.md"
try:
    m._forbidden_from_registry(missing)
    print("  FAIL: a missing registry produced a list instead of refusing")
    bad = 1
except SystemExit as e:
    print("missing registry -> refused:", str(e).split("\n")[0][:80])

print("\nFAILED" if bad else "\nOK: the forbidden list is the registry's, and an "
                             "unreadable registry stops the linter")
sys.exit(bad)
