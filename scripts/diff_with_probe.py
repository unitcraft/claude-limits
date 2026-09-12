#!/usr/bin/env python3
"""Differential: the Nova build against the Python reference, on the same inputs.

This is the acceptance mechanism for phase 1 (plan 01, decision 10 and the Ф.1
acceptance; task T1.8). Both sides read the SAME account directories and the SAME
recorded replies, and their tables must agree.

Two things this deliberately does NOT compare, and why:

  * the RELATIVE remainder ("3h 13min"). It is recomputed from the wall clock on
    every run, so two runs a minute apart would differ for no reason. The plan
    names the columns to compare — kind, percent, severity, resets_at — and the
    remainder is presentation derived from the last of them.
  * the bar and the colour. Both are presentation too, and both already have their
    own checks.

Absolute reset times ARE compared, normalised to UTC so a machine's timezone
cannot make the diff red.

Offline by default: with both sides calling the endpoint, every acceptance run
would spend two sets of requests on it — which is how this machine earned a 429
on 2026-09-07.
"""
import argparse
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parent.parent

EXIT_SAME = 0        # tables agree
EXIT_DIFFER = 1      # tables differ — the finding this script exists for
EXIT_CANNOT = 2      # could not compare (missing binary, crash) — never confused with agreement

ACCOUNT = re.compile(r"^(?P<who>\S+@\S+)\s+\((?P<org>[^)]*)\)\s+\[(?P<dirs>[^\]]*)\]\s*$")
ROW = re.compile(
    r"^\s{2}(?P<kind>\S+)\s+"
    r"(?:\[[^\]]*\]\s+)?"                       # the bar, if the side draws one
    r"(?P<pct>-|\d+)%\s+"
    r"(?P<sev>\S+)\s+resets\s+(?P<reset>.*?)\s*$"
)
STATE = re.compile(r"^\s{2}(?P<text>(token expired on disk|HTTP \d+|offline:|network error).*)$")


def to_utc(stamp):
    """`2026-09-08 01:00 (3h 13min)` -> `2026-09-07T22:00Z`. The remainder is dropped."""
    if not stamp or stamp == "-":
        return "-"
    head = stamp.split("(")[0].strip()
    try:
        local = datetime.strptime(head, "%Y-%m-%d %H:%M").astimezone()
    except ValueError:
        return head          # unparsed: compare verbatim rather than guess
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def normalise(text):
    """Table text -> the comparable lines only, in order."""
    out = []
    for line in text.splitlines():
        m = ACCOUNT.match(line.strip()) if "@" in line else None
        if m:
            dirs = ",".join(sorted(d.strip() for d in m["dirs"].split(",")))
            out.append(f"ACCOUNT {m['who'].lower()} ({m['org']}) [{dirs}]")
            continue
        m = ROW.match(line)
        if m:
            out.append(f"  ROW {m['kind']} {m['pct']}% {m['sev']} {to_utc(m['reset'])}")
            continue
        m = STATE.match(line)
        if m:
            out.append(f"  STATE {m['text'].strip()}")
    return out


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return None, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return None, f"timed out: {' '.join(cmd)}"
    return p.stdout, None if p.returncode in (0, 1) else f"exit {p.returncode}: {p.stderr.strip()[:200]}"


def main(argv):
    ap = argparse.ArgumentParser(description="diff the Nova build against the Python reference")
    ap.add_argument("dirs", nargs="+", help="account directories both sides read")
    ap.add_argument("--offline", default=str(REPO / "fixtures" / "usage"),
                    help="recorded replies both sides use (default: fixtures/usage); "
                         "pass --live to call the endpoint instead")
    ap.add_argument("--live", action="store_true", help="call the real endpoint on both sides")
    ap.add_argument("--nova", default=str(REPO / "target" / "claude-limits.exe"),
                    help="the Nova binary (default: target/claude-limits.exe)")
    args = ap.parse_args(argv)

    common = ["--color", "never", "--bar-style", "ascii"]
    offline = [] if args.live else ["--offline", args.offline]

    ref_out, err = run([sys.executable, str(REPO / "scripts" / "claude_limits.py")]
                       + common + offline + args.dirs)
    if err:
        print(f"CANNOT COMPARE: reference tool: {err}")
        return EXIT_CANNOT

    nova = pathlib.Path(args.nova)
    if not nova.is_file():
        print(f"CANNOT COMPARE: the Nova binary is not built yet ({nova}).")
        print("  Build it with:  ./nova.sh build --mode release src/main.nv -o target/claude-limits.exe")
        print("  This is exit 2, NOT success: an unbuilt side must never read as agreement.")
        return EXIT_CANNOT

    nova_out, err = run([str(nova), "--once"] + common + offline + args.dirs)
    if err:
        print(f"CANNOT COMPARE: nova binary: {err}")
        return EXIT_CANNOT

    a, b = normalise(ref_out), normalise(nova_out)

    # "Not implemented yet" is not "differs", and the difference matters: the first
    # is a phase not started, the second is a defect to chase. Found 2026-09-07 by
    # running this against the T0.0 skeleton, which exists and only prints a version
    # line — the script called that DIFFER and would have sent someone hunting.
    if a and not b:
        print("CANNOT COMPARE: the Nova side produced no comparable rows at all.")
        print(f"  It ran and exited cleanly, so the binary exists — but `--once` is not")
        print(f"  implemented yet, or it ignored the flags. Its raw output was:")
        for line in (nova_out or "").splitlines()[:3]:
            print(f"    | {line}")
        print("  Exit 2, not 1: an unimplemented side is not a disagreement.")
        return EXIT_CANNOT

    # NEITHER SIDE PRODUCED ANYTHING, and `a == b` holds trivially. That is not
    # agreement, it is an unmeasured comparison wearing the word SAME -- and this
    # script is the acceptance mechanism for the whole of phase 1, so a vacuous green
    # here certifies a phase nobody checked. Pointing it at a directory with no logins
    # is an ordinary thing to do, and it used to print
    # "SAME: 0 comparable lines agree" with the zero in plain sight.
    if not a and not b:
        print("CANNOT COMPARE: neither side produced a single comparable line.")
        print(f"  Directories given: {', '.join(args.dirs)}")
        print("  Both programs ran and exited cleanly, so this is not a crash -- there")
        print("  is simply nothing in these directories to tabulate. Point the script")
        print("  at a directory that holds a login.")
        print("  Exit 2, not 0: an empty comparison is not an agreement.")
        return EXIT_CANNOT

    if a == b:
        print(f"SAME: {len(a)} comparable lines agree "
              f"({'live' if args.live else 'offline'}, {len(args.dirs)} directories)")
        return EXIT_SAME

    print(f"DIFFER: reference {len(a)} lines, nova {len(b)} lines")
    import difflib
    for line in difflib.unified_diff(a, b, "reference", "nova", lineterm="", n=1):
        print(" ", line)
    return EXIT_DIFFER


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
