# -*- coding: utf-8 -*-
"""Refuses any file carrying an index bit that hides it from `git status`.

WHY, AND IT IS NOT HYPOTHETICAL. The integrator spent an evening on a guard that printed
"1028 <= baseline 1028" locally and "1030 > 1028" on CI -- the same commit, two verdicts.
The cause was `skip-worktree` on `.vscode/settings.json`: the blob held an absolute path
that the working copy no longer had, and the bit hid the difference from `git status`
ENTIRELY. The tree looked clean and `git diff` was empty (registry 221.1 #1088).

WHAT IT PROTECTS HERE. This session has closed thirty commits today and each one said
"tree clean" on the strength of `git status --porcelain` being empty. That sentence is
only as good as the absence of these bits: a file with `skip-worktree` is invisible to
the very command the claim rests on, so "clean" would mean "clean apart from what I
cannot see".

THE BITS, and why both are refused:

  * `S` -- skip-worktree: git stops comparing the file at all. Meant for local config
    that must not be committed back; it silently turns the index into fiction.
  * `h` -- assume-unchanged: a promise git takes at face value. Whoever makes it
    forgets, and the file then ships whatever the blob held.

A file that genuinely must differ locally belongs in `.gitignore` or in a file the
repository does not track -- both of which are visible decisions.

`git ls-files -v` prints one letter per file: `H` is the ordinary state. Anything else
is reported, so a bit nobody here has thought of is loud rather than tolerated.

Exit codes: 0 clean, 1 a hidden bit found, 2 could not measure.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MEANING = {
    "S": "skip-worktree -- git stops comparing this file; the index becomes fiction",
    "h": "assume-unchanged -- a promise git believes; the blob ships regardless",
}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "-v"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print("REFUSED: cannot list the index -- %s" % e)
        return 2

    rows = [l for l in out.splitlines() if l.strip()]
    if not rows:
        print("REFUSED: the index lists no files. 'No hidden bits' and 'did not look' "
              "print the same, and only one of them is good news.")
        return 2

    hidden = [(l[0], l[2:]) for l in rows if l[0] != "H"]

    print("files in the index: %d" % len(rows))
    if not hidden:
        print("ok: every file is plain `H` -- `git status` sees all of them")
        return 0

    print("FAIL: %d file(s) carry an index bit that hides them from `git status`:"
          % len(hidden))
    for tag, path in hidden:
        why = MEANING.get(tag, "unknown bit -- reported because it is not `H`")
        print("  %s  %-50s %s" % (tag, path[:50], why))
    print("\nA 'tree clean' claim made with one of these present is worth less than it "
          "reads: the file is invisible to the command the claim rests on. Clear it "
          "with `git update-index --no-skip-worktree <path>`, or stop tracking the file.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
