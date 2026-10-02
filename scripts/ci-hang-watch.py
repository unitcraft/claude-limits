"""Hang watch for `nova test` in CI: the evidence registry 221.1 #1612 asks for.

WHY. Twice a test hung in CI for the whole 900-second limit and was killed (repo_test
2026-10-01, config_file_test 2026-10-02 run 36946930912), the next runs were green,
and the log said only "killed after 913119ms". A hang killed without a stack is a
hypothesis forever. This script runs BESIDE `nova test` and, for a test process alive
longer than the threshold, prints its name, its pid and every thread's stack -- before
the runner's timeout kills it.

HOW. Every 20 s it lists processes (CIM, through PowerShell) whose executable path
contains MATCH (the runner builds each test into `%TEMP%\\nova_tests-<n>\\`). One older
than AFTER seconds is dumped ONCE with `cdb -pv` (non-invasive: the process is not
stopped or changed) running `~*kn 64` -- every thread's stack with frame numbers.
Without `cdb` it says so and prints what it can: name, pid, age, command line.

Exit: it runs until killed by the step that started it; it never fails the step.

Environment (for trying it locally):
  HANG_WATCH_AFTER_SEC  age that counts as a hang, default 600 (the limit is 900)
  HANG_WATCH_MATCH      substring of the executable path, default "nova_tests-"
  HANG_WATCH_EVERY_SEC  poll period, default 20
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

AFTER = int(os.environ.get("HANG_WATCH_AFTER_SEC", "600"))
MATCH = os.environ.get("HANG_WATCH_MATCH", "nova_tests-").lower()
EVERY = int(os.environ.get("HANG_WATCH_EVERY_SEC", "20"))
CDB_CANDIDATES = [
    r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe",
    r"C:\Program Files\Windows Kits\10\Debuggers\x64\cdb.exe",
]

PS = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath } | "
      "Select-Object ProcessId, Name, ExecutablePath, CommandLine, "
      "@{n='Started';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")


def say(line):
    print(f"HANG WATCH: {line}", flush=True)


def processes():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", PS], capture_output=True,
                             text=True, timeout=60).stdout
        data = json.loads(out) if out.strip() else []
    except (subprocess.SubprocessError, ValueError, OSError) as e:
        say(f"could not list processes: {e}")
        return []
    return data if isinstance(data, list) else [data]


def cdb():
    for c in CDB_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def dump(p, age):
    say(f"{p.get('Name')} pid {p.get('ProcessId')} alive {age:.0f} s -- treated as hung")
    say(f"path {p.get('ExecutablePath')}")
    say(f"command {p.get('CommandLine')}")
    exe = cdb()
    if not exe:
        say("cdb not found: no stacks (looked in " + "; ".join(CDB_CANDIDATES) + ")")
        return
    try:
        r = subprocess.run([exe, "-pv", "-p", str(p["ProcessId"]), "-c", "~*kn 64; q"],
                           capture_output=True, text=True, timeout=180)
        for line in (r.stdout or "").splitlines():
            print(f"HANG STACK {p.get('ProcessId')}: {line}", flush=True)
        if r.returncode != 0:
            say(f"cdb exited {r.returncode}: {(r.stderr or '').strip()[:300]}")
    except subprocess.TimeoutExpired:
        say("cdb did not finish in 180 s")


def main():
    say(f"watching processes under '*{MATCH}*' older than {AFTER} s, every {EVERY} s")
    # Said at the start, not only at a hang: whether this runner can give stacks at all
    # is then known from the first log, not discovered on the day it was needed.
    say(f"stacks via {cdb() or 'NOTHING: cdb is not installed here'}")
    dumped = set()
    while True:
        now = datetime.now(timezone.utc)
        for p in processes():
            path = (p.get("ExecutablePath") or "").lower()
            if MATCH not in path or p.get("ProcessId") in dumped:
                continue
            try:
                started = datetime.fromisoformat(p["Started"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            age = (now - started).total_seconds()
            if age >= AFTER:
                dumped.add(p.get("ProcessId"))
                dump(p, age)
        time.sleep(EVERY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
