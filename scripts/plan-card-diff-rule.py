# -*- coding: utf-8 -*-
"""Which cards does the joiner move, and are they the ones it was aimed at?

A rule change that moves cards it was not aimed at is a different rule from the one
I described. So: classify every card with the joiner ON and OFF, and print only the
differences.
"""
import importlib.util
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# Beside this file, not at a path typed out by hand: the absolute one named
# the author's disk in a public repository, and broke on any other.
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan-card-status.py")

spec = importlib.util.spec_from_file_location("pcs", SRC)
pcs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcs)


def verdict(marks):
    vs = set()
    for mk in marks:
        c = pcs.classify(mk)
        if c:
            vs.add(c)
    if "done" in vs:
        return "done"
    if "partial" in vs:
        return "partial"
    if "not-done" in vs:
        return "not-done"
    if "unclassified" in vs:
        return "needs-reading"
    return "unmarked"


def read_cards_nojoin(path):
    """The previous behaviour: no joining of a wrapped bold span."""
    lines = io.open(path, encoding="utf-8").read().splitlines()
    starts = [(i, m.group(1), m.group(2).strip())
              for i, ln in enumerate(lines) for m in [pcs.CARD.match(ln)] if m]
    out = []
    for n, (i, tid, title) in enumerate(starts):
        limit = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(i + 1, limit):
            if pcs.HEADING.match(lines[j]):
                limit = j
                break
        marks = []
        for ln in lines[i + 1:limit]:
            m = pcs.BOLD_BULLET.match(ln)
            if m and any(c.isalpha() for c in m.group(1)):
                if not pcs.is_label(m.group(1)):
                    marks.append(m.group(1).strip())
                continue
            for mid in pcs.BOLD_ANY.findall(ln):
                t = mid.strip()
                if not t or pcs.is_label(t):
                    continue
                if any(t.upper().startswith(p)
                       for p in pcs.DONE + pcs.PARTIAL + pcs.NOT_DONE):
                    marks.append(t)
        out.append((tid, marks))
    return out


new = {tid: verdict(m) for tid, _t, _l, m in pcs.read_cards(pcs.DEFAULT_PLAN)}
old = {tid: verdict(m) for tid, m in read_cards_nojoin(pcs.DEFAULT_PLAN)}

moved = [(t, old[t], new[t]) for t in new if old.get(t) != new[t]]
print("cards moved by the joiner: %d" % len(moved))
for t, a, b in moved:
    print("  %-8s %-13s -> %s" % (t, a, b))

if moved:
    print("\nmarks of each moved card, as the joiner now sees them:")
    for tid, _title, _ln, marks in pcs.read_cards(pcs.DEFAULT_PLAN):
        if any(tid == t for t, _a, _b in moved):
            print("  %s:" % tid)
            for mk in marks:
                print("     %-13s %r" % (pcs.classify(mk), mk[:96]))
