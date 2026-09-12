# -*- coding: utf-8 -*-
"""Every probe a FINDING names must exist, and every probe present must be named.

WHY. The finding in probes/enum-method-match-self/ cited five probes and shipped four:
the copy that created the fifth was in a shell command the shell rejected, and the
commit went out without it. Nothing complained. The missing one was the probe that
CORRECTED the finding -- so the document that survived argued a conclusion using
evidence the reader could not open.

BOTH DIRECTIONS, and the second is the one that catches real rot:

  * named but absent -- the document cites what nobody can read;
  * present but unnamed -- a probe sits in the tree that no finding accounts for,
    which is how a probe from an abandoned theory gets mistaken for evidence.

Checking one direction would look like a check without being one. That lesson came
from MEMORY.md's own integrity rule, where the second direction found an orphan the
first could not see.

Exit codes: 0 clean, 1 mismatch, 2 could not measure.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, "probes")
# A probe name: a letter, an underscore, then lowercase words. Matches the convention
# the finding uses when it points at one.
NAME = re.compile(r"`([a-z]_[a-z0-9_]+)`")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    if not os.path.isdir(PROBES):
        print("REFUSED: no probes/ directory at %s" % PROBES)
        return 2

    # ONLY directories that actually use the lettered-probe convention are judged.
    #
    # The first version judged every probe directory and produced two findings that
    # were not findings: `c_shims` is a manifest key in backticks, and the regex for a
    # probe name matched it. Most directories here do not letter their files at all,
    # so they contributed a stream of "0 files, 0 cited" noise around two false
    # positives.
    #
    # A check that invents findings is worse than no check: it is read once, disproved,
    # and then disbelieved when it is right. So the convention announces itself --
    # a directory is in scope when it holds at least one `<letter>_<words>.nv.txt` --
    # and the rest are counted as skipped, out loud, rather than silently passed.
    lettered = re.compile(r"^[a-z]_[a-z0-9_]+\.nv\.txt$")
    dirs, skipped = [], 0
    for d in sorted(os.listdir(PROBES)):
        full = os.path.join(PROBES, d)
        if not os.path.isfile(os.path.join(full, "FINDING.md")):
            continue
        if any(lettered.match(f) for f in os.listdir(full)):
            dirs.append(d)
        else:
            skipped += 1

    if not dirs:
        print("REFUSED: no directory uses the lettered-probe convention. 'Nothing "
              "mismatched' and 'nothing examined' print the same, and only one is "
              "good news.")
        return 2
    print("directories judged: %d; skipped (no lettered probes): %d\n"
          % (len(dirs), skipped))

    bad = 0
    for d in dirs:
        full = os.path.join(PROBES, d)
        text = io.open(os.path.join(full, "FINDING.md"), encoding="utf-8").read()
        present = {f[:-len(".nv.txt")] for f in os.listdir(full)
                   if f.endswith(".nv.txt")}
        named = set(NAME.findall(text))

        missing = sorted(n for n in named
                         if not any(p.startswith(n) for p in present))
        # A probe file and its peer test share a stem, so account for both halves.
        unnamed = sorted(p for p in present
                         if not any(p.startswith(n) for n in named))

        print("%s: %d file(s), %d name(s) cited" % (d, len(present), len(named)))
        for m in missing:
            print("  NAMED BUT ABSENT: %s -- the finding cites evidence nobody can open"
                  % m)
            bad += 1
        for u in unnamed:
            print("  PRESENT BUT UNNAMED: %s -- a probe no finding accounts for" % u)
            bad += 1

    if bad:
        print("\nFAIL: %d mismatch(es)." % bad)
        return 1
    print("\nok: every cited probe exists, and every probe is cited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
