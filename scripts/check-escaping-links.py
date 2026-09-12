# -*- coding: utf-8 -*-
"""Refuses any .md link that resolves outside this repository.

WHY. Five links in this package pointed into ../../nova/... They resolve on a machine
where both trees happen to sit side by side under one parent -- mine -- and are dead for
anyone who clones this repository alone, which is every reader it will ever have. The
integrator added the same check to the main repository on 2026-09-12; it does not run
here, because this is a different repository, so the rule needs its own enforcement.

IT JUDGES THE RESOLVED PATH, NOT THE TEXT. `../..` from a deep directory can be legal
while the same text from a shallow one is already outside, so counting `../` would be
the wrong measure. Every relative target is joined to its file's directory, normalised,
and required to stay under the root.

THE ROOT IS DERIVED FROM THIS FILE'S LOCATION, never written down. A checker carrying a
hard-coded path judges the tree its author had rather than the tree it was copied into,
and then passes -- green and meaningless -- in the copy. This package already rewrote
thirteen checkers for that exact defect, and the first draft of this one repeated it.

ZERO TRACKED .md FILES IS A REFUSAL, not a pass: "no findings" and "did not look" print
identically, and only one of them is good news.

Exit codes: 0 clean, 1 escaping links found, 2 could not measure.
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "*.md"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        print("REFUSED: cannot list tracked files -- %s" % e)
        return 2

    files = [f for f in out.splitlines() if f.strip()]
    if not files:
        print("REFUSED: zero tracked .md files. 'No escaping links' and 'did not look' "
              "print the same, and only one of them is good news.")
        return 2

    escaping, checked = [], 0
    for rel in files:
        full = os.path.join(ROOT, rel)
        try:
            text = io.open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        checked += 1
        for target in LINK.findall(text):
            t = target.split("#")[0].split(" ")[0].strip()
            if not t or "://" in t or t.startswith(("#", "mailto:")):
                continue
            if os.path.isabs(t) or re.match(r"^[A-Za-z]:", t):
                escaping.append((rel, t, "ABSOLUTE"))
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(full), t))
            if not resolved.lower().startswith(os.path.normpath(ROOT).lower() + os.sep):
                escaping.append((rel, t, "escapes root"))

    print(".md checked: %d" % checked)
    if not escaping:
        print("ok: no link resolves outside %s" % os.path.basename(ROOT))
        return 0

    print("FAIL: %d link(s) resolve outside this repository. They work only on a machine "
          "where the sibling tree happens to sit beside this one." % len(escaping))
    for rel, t, why in escaping:
        print("  %-54s %-9s %s" % (rel[:54], why, t[:60]))
    print("\nFix: name the other repository and path as inline code instead of linking "
          "-- unclickable, always accurate, and greppable by a reader who has that tree.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
