# -*- coding: utf-8 -*-
"""Counts the cards of subplan 01.5 and their statuses, and refuses to guess.

WHY THIS IS A SCRIPT IN THE TREE rather than a number in a document. The count "51
cards, 20 done" was true at 2026-09-09 23:34 and will be false soon after. A number
written into a plan or a handoff note is re-derived by the next window with whatever
grep comes to mind -- and two greps of the same file gave me 2 and 51 on the same
evening. So the tree carries the MEASURE, and documents cite the command.

TWO TRAPS IT DISARMS, both measured on this file the evening it was written:

  1. THE SPAN. A card's block ends at the next card *or* the next section heading,
     whichever comes first. Bounding only by the next card lets a span swallow a
     heading and the prose beneath it; that is how T2.8's status was misread twice.

  2. THE VOCABULARY -- the more expensive of the two. The obvious implementation
     greps for the words you expect ("СДЕЛАНО", "ЗАКРЫТО"). Doing that here would
     have silently classified as unfinished every card marked "ЧАСТИЧНО",
     "НЕ НАПИСАНО", "НАЙДЕНО ДО НАЧАЛА КАРТОЧКИ" or "ТОЧКА ВХОДА ГОТОВА" -- four
     status words the author used and the reader did not think of. So this script
     never matches a status list. It COLLECTS every bold token that opens a bullet,
     prints the distinct set, and classifies only by prefixes it then names out
     loud. A word nobody anticipated shows up as UNCLASSIFIED, which is loud,
     instead of as "not done", which is plausible.

  3. THE POSITION, found later and cheaper to state than to rediscover. A status
     can arrive in the MIDDLE of a bullet: T1.6 opens "НАПИСАНО, НЕ ПРОГНАНО" and
     four lines down says "СДЕЛАНО -- покрытие стало зеленью 16:59". Reading only
     bullet-opening marks called a finished card unwritten, and a false negative
     like that is indistinguishable from an honest one -- it just makes somebody
     redo work already done. Mid-bullet marks are now taken too, but only when
     they BEGIN with a known status word; sweeping every bold span would feed the
     classifier ordinary emphasis, which is worse than missing a mark.

AND IT REFUSES A PLAUSIBLE ANSWER. `--expect-at-least N` fails when fewer cards are
found than the caller knows exist. The failure mode this guards is not a crash: it is
a regex that quietly stops matching after the file is reformatted and reports a
smaller, entirely believable number. 2 out of 51 was caught only because the reader
happened to know the order of magnitude. 47 would have been accepted.

Usage:
    python scripts/plan-card-status.py                      # the tally
    python scripts/plan-card-status.py --verbose            # every card
    python scripts/plan-card-status.py --expect-at-least 51 # for a gate
"""
import argparse
import collections
import io
import os
import re
import sys

DEFAULT_PLAN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "plans", "01.5-work-breakdown.md")

CARD = re.compile(r"^\*\*(T\d+\.\d+)\s*·\s*(.+?)\*\*(.*)$")
HEADING = re.compile(r"^#{1,6}\s")
BOLD_BULLET = re.compile(r"^\s*[-*]\s*\*\*([^*]{2,80}?)\*\*")
# Bold spans anywhere on a line, for a status that arrives mid-bullet (see cards_of).
BOLD_ANY = re.compile(r"\*\*([^*]{2,80}?)\*\*")

# Prefixes are NAMED here, in the open, rather than hidden in a grep. Anything a card
# is marked with that is not on this list is reported as UNCLASSIFIED -- deliberately
# noisy, because the alternative is a wrong tally that looks right.
DONE = ("СДЕЛАНО",
        "НАЙДЕНО ДО",
        "ТОЧКА ВХОДА")
PARTIAL = ("ЧАСТИЧНО",)
NOT_DONE = ("НЕ НАПИСАНО",
            "НАПИСАНО, НЕ ПРОГНАНО")
# Not a status at all: a card may carry it and be finished or untouched alike.
NOT_A_STATUS = ("Приёмка", "ЭФФЕКТ")


def classify(mark):
    up = mark.upper()
    for p in DONE:
        if up.startswith(p):
            return "done"
    for p in PARTIAL:
        if up.startswith(p):
            return "partial"
    for p in NOT_DONE:
        if up.startswith(p):
            return "not-done"
    for p in NOT_A_STATUS:
        if mark.startswith(p):
            return None
    return "unclassified"


def read_cards(path):
    lines = io.open(path, encoding="utf-8").read().splitlines()
    starts = [(i, m.group(1), m.group(2).strip())
              for i, ln in enumerate(lines) for m in [CARD.match(ln)] if m]
    out = []
    for n, (i, tid, title) in enumerate(starts):
        limit = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(i + 1, limit):
            if HEADING.match(lines[j]):
                limit = j
                break
        marks = []
        for ln in lines[i + 1:limit]:
            m = BOLD_BULLET.match(ln)
            if m and any(c.isalpha() for c in m.group(1)):
                marks.append(m.group(1).strip())
                continue
            # A status can arrive MID-bullet, and T1.6 is the proof: its bullet opens
            # "НАПИСАНО, НЕ ПРОГНАНО" and four lines below says "**СДЕЛАНО -- покрытие
            # стало зеленью 16:59**, PASS: 3 FAIL: 0". Reading only the opening mark
            # reported a finished card as unwritten -- a false negative indis-
            # tinguishable from an honest one, and the kind that makes somebody redo
            # work that is done.
            #
            # Only marks BEGINNING with a known status word are taken here. Taking
            # every bold span would sweep in ordinary emphasis, and a classifier fed
            # on emphasis is worse than one that misses a mark.
            for mid in BOLD_ANY.findall(ln):
                t = mid.strip()
                if t and any(t.upper().startswith(p)
                             for p in DONE + PARTIAL + NOT_DONE):
                    marks.append(t)
        out.append((tid, title, i + 1, marks))
    return out


def main():
    # This machine's console is cp1251 and the plan is Russian. Without this the
    # script's own output arrives as question marks -- and the UNCLASSIFIED section,
    # whose whole purpose is to show a status word the reader did not anticipate,
    # becomes unreadable exactly when it matters. Measured 2026-09-10 00:33.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=DEFAULT_PLAN)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--expect-at-least", type=int, default=0,
                    help="fail if fewer cards are found; catches a regex that quietly "
                         "stopped matching and returned a believable smaller number")
    a = ap.parse_args()

    if not os.path.exists(a.plan):
        print("REFUSED: no such plan: %s" % a.plan)
        return 2

    cards = read_cards(a.plan)
    if not cards:
        print("REFUSED: zero cards found. The heading shape changed. Zero here would "
              "read as 'nothing to do' when it means 'could not measure'.")
        return 2

    tally = collections.Counter()
    unclassified = []
    vocab = collections.Counter()
    for tid, title, ln, marks in cards:
        verdicts = set()
        for mk in marks:
            vocab[mk.split()[0].strip(",.:—-")] += 1
            c = classify(mk)
            if c == "unclassified":
                unclassified.append((tid, ln, mk))
            if c:
                verdicts.add(c)
        # Order matters, and "needs-reading" deliberately outranks nothing: a card
        # whose only mark is an unrecognised one must NOT land in "unmarked". Those
        # two states look identical in a tally and mean opposite things -- "nobody
        # wrote anything" versus "somebody wrote something I could not parse". The
        # first invites work; the second invites reading, and folding it into the
        # first is how a marked card gets done twice.
        if "done" in verdicts:
            tally["done"] += 1
        elif "partial" in verdicts:
            tally["partial"] += 1
        elif "not-done" in verdicts:
            tally["not-done"] += 1
        elif "unclassified" in verdicts:
            tally["needs-reading"] += 1
        else:
            tally["unmarked"] += 1

    w = sys.stdout
    # relpath() raises across Windows drives, and a probe plan lives in the temp dir
    # on C: while the repository is on D:. The crash exits 1 -- the same code the
    # expect-at-least failure uses -- so a reverse probe reddens for a reason it never
    # measured and reads as proof. Caught 2026-09-10 00:40 doing exactly that.
    try:
        shown = os.path.relpath(a.plan)
    except ValueError:
        shown = a.plan
    w.write("plan: %s\n" % shown)
    w.write("cards: %d\n" % len(cards))
    w.write("  done      %3d\n" % tally["done"])
    w.write("  partial   %3d\n" % tally["partial"])
    w.write("  not-done  %3d\n" % tally["not-done"])
    w.write("  needs-rd  %3d   <- marked, but with a word this script cannot judge.\n"
            "                     Listed in full below; read them, do not assume.\n"
            % tally["needs-reading"])
    w.write("  unmarked  %3d   <- NO status note at all. This means the card carries no\n"
            "                     mark, NOT that the work is undone: T3.0 was finished\n"
            "                     the day this ran and would sit here but for its note.\n"
            % tally["unmarked"])

    w.write("\nvocabulary actually used by the author (collected, never assumed):\n")
    for t, c in vocab.most_common():
        w.write("  %-34s %d\n" % (t, c))

    if unclassified:
        w.write("\nUNCLASSIFIED marks -- a status word this script does not know. Add it\n"
                "to DONE/PARTIAL/NOT_DONE above, or the tally is wrong in silence:\n")
        for tid, ln, mk in unclassified:
            w.write("  %-8s L%-5d %s\n" % (tid, ln, mk[:70]))

    if a.verbose:
        w.write("\nper card:\n")
        for tid, title, ln, marks in cards:
            w.write("  %-8s L%-5d %-44s %s\n"
                    % (tid, ln, title[:44], " ; ".join(marks)[:70] or "--"))

    if a.expect_at_least and len(cards) < a.expect_at_least:
        w.write("\nFAIL: found %d cards, expected at least %d. A shrinking count is the\n"
                "quiet failure -- the regex stopped matching, and the smaller number is\n"
                "believable enough to be trusted.\n" % (len(cards), a.expect_at_least))
        return 1

    w.write("\nok: %d cards measured\n" % len(cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
