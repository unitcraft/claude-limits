# -*- coding: utf-8 -*-
"""For cards with no status note: do the files they promise actually exist?

WHY. plan-card-status.py counts what the plan SAYS. It cannot say whether an unmarked
card is untouched or merely unmarked -- and T0.4 was caught in exactly that state
("ПРОГНАН, КАРТОЧКА БЫЛА ПРОСТО НЕ ОТМЕЧЕНА"). So a remainder built from "unmarked" is
inflated by however many cards were finished by someone who forgot the bullet. This
script asks the tree instead of the prose.

WHAT IT IS NOT, and this is the whole caveat. **A file existing does not mean the card
is done.** The card promises behaviour; the file is only its address. A present file
means "worth reading before you redo this"; an absent one is the stronger signal,
because a card whose outputs are all missing was certainly not finished. The output
therefore never prints a verdict -- it prints EVIDENCE and says which way it leans.
Calling this "done" would be the same mistake as counting `nova test` PASS: 0 as green.

HOW PATHS ARE FOUND. Only backticked tokens on a "Выходы:" bullet and its continuation
lines. Backticks are the plan's own convention for a path, so this reads the author's
markup rather than guessing at prose. A token is treated as a path if it contains a
slash or ends in a known extension; anything else is reported as skipped, out loud,
so a missed path shows up as a skip rather than as a silent absence.
"""
import argparse
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PLAN = os.path.join(ROOT, "docs", "plans", "01.5-work-breakdown.md")

CARD = re.compile(r"^\*\*(T\d+\.\d+)\s*·\s*(.+?)\*\*(.*)$")
HEADING = re.compile(r"^#{1,6}\s")
BOLD_BULLET = re.compile(r"^\s*[-*]\s*\*\*([^*]{2,80}?)\*\*")
OUTPUTS = re.compile(r"^\s*[-*]\s*Выходы\s*:")
BULLET = re.compile(r"^\s*[-*]\s")
TICKED = re.compile(r"`([^`]+)`")
EXTS = (".nv", ".md", ".toml", ".py", ".sh", ".ps1", ".mjs", ".json",
        ".yml", ".yaml", ".c", ".h", ".html", ".css", ".js")


def looks_like_path(tok):
    tok = tok.strip().rstrip(",.;:")
    if not tok or " " in tok.strip():
        return None
    if "/" in tok or tok.endswith(EXTS):
        return tok
    return None


# A card writes `storage/repo.nv`, and the file lives at `src/storage/repo.nv` -- the
# plan's module paths are relative to the source root, while its docs and scripts are
# relative to the repository. Resolving only from the repository root reports a file
# that exists as missing, and "missing" is precisely the signal this script exists to
# produce, so a wrong one is worse than no answer.
#
# The first version did exactly that and still printed the right answer, because every
# path it checked happened to be absent under both bases. A coincidence that looks like
# a working check is the failure this whole file is written against, so it is named
# here rather than quietly fixed: caught 2026-09-10 01:33, by hand, not by the script.
BASES = ("", "src")


def resolve(p):
    for b in BASES:
        full = os.path.join(ROOT, b, p) if b else os.path.join(ROOT, p)
        if os.path.exists(full):
            return full
    return None


def cards_of(path):
    lines = io.open(path, encoding="utf-8").read().splitlines()
    starts = [(i, m.group(1)) for i, ln in enumerate(lines)
              for m in [CARD.match(ln)] if m]
    for n, (i, tid) in enumerate(starts):
        limit = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        for j in range(i + 1, limit):
            if HEADING.match(lines[j]):
                limit = j
                break
        span = lines[i + 1:limit]
        marked = any(BOLD_BULLET.match(ln) and
                     not BOLD_BULLET.match(ln).group(1).startswith(("Приёмка", "ЭФФЕКТ"))
                     for ln in span)
        outs, collecting = [], False
        for ln in span:
            if OUTPUTS.match(ln):
                collecting = True
            elif collecting and BULLET.match(ln):
                collecting = False
            if collecting:
                outs.extend(TICKED.findall(ln))
        yield tid, i + 1, marked, outs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=DEFAULT_PLAN)
    ap.add_argument("--all", action="store_true",
                    help="every card, not only the unmarked ones")
    a = ap.parse_args()

    rows = list(cards_of(a.plan))
    if not rows:
        print("REFUSED: zero cards -- shape changed, and zero would read as 'nothing "
              "to check' when it means 'could not measure'")
        return 2

    looked = 0
    all_present, none_present, mixed, no_paths = [], [], [], []
    for tid, ln, marked, outs in rows:
        if marked and not a.all:
            continue
        looked += 1
        paths, skipped = [], []
        for tok in outs:
            p = looks_like_path(tok)
            (paths if p else skipped).append(p or tok)
        if not paths:
            no_paths.append((tid, ln, skipped))
            continue
        found = [p for p in paths if resolve(p)]
        missing = [p for p in paths if p not in found]
        rec = (tid, ln, found, missing, skipped)
        if not missing:
            all_present.append(rec)
        elif not found:
            none_present.append(rec)
        else:
            mixed.append(rec)

    print("plan cards examined: %d of %d (%s)"
          % (looked, len(rows), "all" if a.all else "unmarked only"))
    print()
    print("EVERY PROMISED FILE EXISTS -- %d card(s). Leans DONE-BUT-UNMARKED; read the"
          % len(all_present))
    print("card before redoing it. Existence is an address, not behaviour.")
    for tid, ln, found, _m, _s in all_present:
        print("  %-8s L%-5d %s" % (tid, ln, ", ".join(found)[:100]))

    print()
    print("NOTHING PROMISED EXISTS -- %d card(s). The STRONG signal: not started."
          % len(none_present))
    for tid, ln, _f, missing, _s in none_present:
        print("  %-8s L%-5d %s" % (tid, ln, ", ".join(missing)[:100]))

    print()
    print("PARTLY THERE -- %d card(s). Needs a human; half a card is not a fraction of"
          % len(mixed))
    print("done, it is an unknown.")
    for tid, ln, found, missing, _s in mixed:
        print("  %-8s L%-5d missing: %s" % (tid, ln, ", ".join(missing)[:80]))

    print()
    print("NO PATH FOUND ON THE Выходы LINE -- %d card(s). NOT evidence of anything:"
          % len(no_paths))
    print("the card may promise behaviour rather than files, or word it differently.")
    for tid, ln, skipped in no_paths:
        print("  %-8s L%-5d skipped tokens: %s" % (tid, ln, ", ".join(skipped)[:70]))

    print()
    print("ok: %d card(s) examined; this script reports evidence, never a verdict"
          % looked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
