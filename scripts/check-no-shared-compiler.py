# -*- coding: utf-8 -*-
"""The compiler this repository runs is a COPY, never the binary in the nova tree.

    python scripts/check-no-shared-compiler.py

WHY (2026-10-01). A running `nova.exe` holds its file, and the nova integrator's
`cargo build` cannot replace a held file: two rebuilds carrying a compiler fix failed
with "failed to remove file ... Access is denied" while this project's builds and
tests ran `../nova/nova-cli/target/release/nova.exe` directly. The first answer was a
line in an agent's memory; the owner's verdict was that memory is not a mechanism --
a guard is. This is that guard.

WHAT IT HOLDS.
  1. BEHAVIOUR, not text: `scripts/nova_run.py` (the one door; `./nova.sh` is a line
     that calls it) is ASKED which executable it would run (`NOVA_RUN_WHICH=1`). The
     answer, as an ABSOLUTE path, must lie inside this repository's `target/` and must
     not be the binary of the nova tree it reads. Comparing absolute paths and not the
     tail `nova-cli/target/release/nova` is the integrator's advice: the tail is the
     same in every worktree, and their own guard reddened on a neighbour's binary.
  2. `nova.sh` runs `scripts/nova_run.py` and nothing else; there is no PowerShell
     twin to drift from it (`nova.ps1` was removed, 2026-10-02).
  3. No other script or source file of this repository names the tree's binary path.
     `scripts/nova_run.py` names it to copy from; documentation (`*.md`) may talk
     about it; `.github/workflows/` is exempt -- a CI runner checks nova out into its
     own workspace and nobody else rebuilds there.

HOW IT FAILS. Over an empty tree (no `nova_run.py`) it refuses: a guard green on
nothing tells nothing (`check-guards-judge-this-tree.py`). When the nova tree has no
built compiler, (1) cannot be asked and the guard says so and fails -- an unanswered
question is not a pass.
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SELF = pathlib.Path(__file__).resolve()
RUNNER = ROOT / "scripts" / "nova_run.py"
WRAPPER = ROOT / "nova.sh"

TREE_BIN = re.compile(r"nova-cli[/\\]target[/\\]release[/\\]nova")
SCAN = {".sh", ".ps1", ".py", ".mjs", ".js", ".nv", ".toml", ".bat", ".cmd"}
SKIP_DIRS = {"target", ".git", "node_modules", "__pycache__"}
EXEMPT_DIRS = {(".github", "workflows")}

problems = []

# 1. the runner, asked
if not RUNNER.is_file():
    problems.append("scripts/nova_run.py: missing -- the one door that runs a COPY of the compiler")
else:
    env = dict(os.environ, NOVA_RUN_WHICH="1")
    r = subprocess.run([sys.executable, str(RUNNER)], env=env, capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    if r.returncode != 0 or not lines:
        problems.append(f"scripts/nova_run.py: could not say what it runs (exit {r.returncode}): {r.stderr.strip()[:200]}")
    else:
        runs = pathlib.Path(lines[-1]).resolve()
        nova = pathlib.Path(os.environ["NOVA_MAIN_REPO"]).resolve() if os.environ.get("NOVA_MAIN_REPO") else (ROOT.parent / "nova").resolve()
        tree = {(nova / "nova-cli" / "target" / "release" / n).resolve() for n in ("nova.exe", "nova")}
        target = (ROOT / "target").resolve()
        if runs in tree:
            problems.append(f"scripts/nova_run.py: runs the nova tree's own binary {runs}")
        if target not in runs.parents:
            problems.append(f"scripts/nova_run.py: runs {runs}, which is not a copy inside {target}")

# 2. the shell wrapper only calls the runner
if not WRAPPER.is_file():
    problems.append("nova.sh: missing -- the acceptance commands run it")
else:
    text = WRAPPER.read_text(encoding="utf-8", errors="replace")
    if "scripts/nova_run.py" not in text:
        problems.append("nova.sh: does not call scripts/nova_run.py")
    if TREE_BIN.search(text):
        problems.append("nova.sh: names the nova tree's binary -- it must only call scripts/nova_run.py")
if (ROOT / "nova.ps1").exists():
    problems.append("nova.ps1: a second implementation of the runner -- one door, in Python (scripts/nova_run.py)")

# 3. nobody else names the tree's binary
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in SCAN:
        continue
    rel = p.relative_to(ROOT)
    parts = rel.parts
    if any(part in SKIP_DIRS for part in parts):
        continue
    if p.resolve() in (SELF, RUNNER.resolve(), WRAPPER.resolve()):
        continue
    if any(parts[:len(e)] == e for e in EXEMPT_DIRS):
        continue
    for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if TREE_BIN.search(line):
            problems.append(f"{rel.as_posix()}:{n}: names the compiler in the nova tree -- run ./nova.sh (a copy) instead")

if problems:
    for x in problems:
        print("FAIL: " + x)
    print(f"SHARED COMPILER: {len(problems)} problem(s)")
    sys.exit(1)
print("SHARED COMPILER: clean -- ./nova.sh runs a copy inside target/, nothing else names the tree's binary")
