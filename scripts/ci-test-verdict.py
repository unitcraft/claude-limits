#!/usr/bin/env python3
"""ci-test-verdict.py -- read a `nova test src` transcript and decide the CI step.

    nova test src ... > test.out 2>&1; python scripts/ci-test-verdict.py test.out

WHY NOT THE EXIT CODE. `nova test src` exits non-zero while ONE known compiler
defect stands (below), so the exit code alone would keep CI red for a reason
nobody here can fix -- and a CI that is always red is read by nobody. The known
failure is named here, WITH the text it must fail with, so that:

  * any OTHER failure fails the step;
  * the known one failing DIFFERENTLY fails the step (a new defect hiding behind
    an old name);
  * the known one PASSING fails the step too -- the exception has outlived its
    reason and must be removed, or it would hide the next failure of that file.

And a transcript with no summary, or with zero passes, fails: an empty
measurement is not a green one.
"""
import re
import sys

# file -> (verdict it fails with, text that must appear in its line, why)
KNOWN = {
    "src/claude_limits": (
        "CC-FAIL",
        "NovaValue_TcpStream",
        "test mode compiles polaris serve_connection with a TcpStream value where a "
        "pointer is wanted; `nova build` of the same file passes (to the integrator, "
        "plan 01.5 T2.27)",
    ),
}

LINE = re.compile(r"^(PASS|CC-FAIL|CODEGEN-FAIL|RUN-FAIL|CHECK-FAIL|TIMEOUT|SKIP)\s+(\S+)\s*(.*)$")
SUMMARY = re.compile(r"PASS:\s*(\d+)\s+FAIL:\s*(\d+)")


def main(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    # The runner colours its summary; strip ANSI before reading it.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    verdicts = {}
    for line in plain.splitlines():
        m = LINE.match(line.strip())
        if m:
            verdicts.setdefault(m.group(2), (m.group(1), m.group(3)))
    s = SUMMARY.search(plain)
    bad = []
    if not s:
        bad.append("no `PASS: n FAIL: m` summary in the transcript -- the run may not have happened")
    elif int(s.group(1)) == 0:
        bad.append("zero passes -- an empty measurement, not a green one")
    for name, (verdict, rest) in sorted(verdicts.items()):
        if verdict in ("PASS", "SKIP"):
            continue
        known = KNOWN.get(name)
        if known is None:
            bad.append(f"{name}: {verdict} {rest[:300]}")
        elif verdict != known[0] or known[1] not in rest:
            bad.append(f"{name}: {verdict}, but the known failure is {known[0]} with "
                       f"`{known[1]}` -- a different failure behind a known name: {rest[:300]}")
        else:
            print(f"known failure, allowed: {name} -- {known[2]}")
    for name in KNOWN:
        if verdicts.get(name, ("", ""))[0] == "PASS":
            bad.append(f"{name} PASSES now -- remove it from KNOWN in scripts/ci-test-verdict.py")
        elif name not in verdicts:
            bad.append(f"{name} did not run at all -- the known failure cannot be confirmed")
    if s:
        print(f"summary: PASS {s.group(1)}, FAIL {s.group(2)}")
    if bad:
        print("TEST VERDICT: FAILED")
        for b in bad:
            print("   " + b)
        sys.exit(1)
    print("TEST VERDICT: clean")


if len(sys.argv) != 2:
    sys.exit("usage: ci-test-verdict.py <nova test transcript>")
main(sys.argv[1])
