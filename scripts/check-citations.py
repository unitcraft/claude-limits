# -*- coding: utf-8 -*-
"""Every `<plan> §<n>` citation must point at a section that plan actually has.

    python scripts/check-citations.py

WHY. A citation to a section that is not there is worse than none: the reader looks,
finds nothing, and stops trusting the citations around it. In a status line or a code
comment those citations are the only thing tying a claim to the document that
authorised it, so one broken reference devalues every true one beside it.

Found on 2026-09-08 by hand: a status line written that same morning cited §3.3 of
subplan 01.1. That plan runs 3.1, 3.2, then §4; the rule lives in the 3.2 table. One broken
reference out of 187 -- which is exactly the density that makes a machine worth
having, since nobody re-reads 187 of anything.

A QUOTE OF A BAD CITATION IS NOT A BAD CITATION, and this checker cannot tell the
difference -- it reads prose as data. The first fix explained the error by quoting
it and went red again. There is no clever way around that: a text explaining a wrong
reference has to mention it. The convention is to word such an explanation so the
plan name does not sit right before the section number -- write "§3.3 of subplan
01.1", not the other way round -- and to say in the text that the word order is
deliberate, so the next editor does not "tidy" it back. This docstring obeys its own
rule: it was reported by the checker until it did, which is the shortest possible
demonstration that the rule is real.
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = pathlib.Path(__file__).resolve().parent.parent
PLANS_DIR = REPO / "docs" / "plans"

# Cited as `01.1`, `01.3`... Discovered rather than listed: a new subplan must be
# covered without editing this file, and a renamed one must not silently drop out.
PLANS = {}
for p in sorted(PLANS_DIR.glob("01.*-*.md")):
    key = p.name.split("-", 1)[0]
    PLANS[key] = p

# `01.1 §2.6`, `01.3 sec.3.8`, `subplan 01.2 §3.11`. The gap allows a word or two
# between the plan and the section, and no more: further apart they are two
# separate references, not one.
RX = re.compile(r"\b(01\.\d+)\b[^\n]{0,24}?(?:§|sec\.|section\s+)\s*(\d+(?:\.\d+)*)")

TARGETS = (sorted((REPO / "src" / "web").glob("*.js"))
           + sorted((REPO / "scripts").glob("*.mjs"))
           + sorted((REPO / "scripts").glob("*.py"))
           + sorted(PLANS_DIR.glob("*.md"))
           + sorted((REPO / "docs" / "reports").glob("*.md"))
           + [REPO / "docs" / "handoff.md", REPO / "docs" / "executor-brief.md"])


def headings(path):
    """The section numbers a plan really carries: '1', '1.2', '3.2', ..."""
    out = set()
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{2,4}\s+\.?\s*(\d+(?:\.\d+)*)\.", ln)
        if m:
            out.add(m.group(1))
    return out


def main():
    if not PLANS:
        print("FAILED: no subplans found under docs/plans -- a checker that finds")
        print("        nothing to check must not report success.")
        return 1

    have = {k: headings(v) for k, v in PLANS.items()}
    # A plan with no numbered sections is legitimate -- 01.5 is organised by cards --
    # and it simply cannot be cited by section, so citations into it get reported.
    # Drift is when NOTHING parses anywhere: then the heading pattern and the
    # documents have parted company and every citation would be called broken.
    if not any(have.values()):
        print("FAILED: not one numbered heading parsed out of any plan -- the heading")
        print("        pattern and the documents have drifted apart, and every")
        print("        citation would be reported as broken.")
        return 1

    bad, checked = [], 0
    for f in TARGETS:
        if not f.exists():
            continue
        for i, ln in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for plan, sec in RX.findall(ln):
                if plan not in have:
                    continue                   # a plan this project does not carry
                checked += 1
                if sec not in have[plan]:
                    bad.append(f"{f.relative_to(REPO)}:{i} cites {plan} §{sec} -- "
                               f"no such section (it has {len(have[plan])} numbered ones)")

    print(f"plans: {len(PLANS)}, citations checked: {checked}")
    print("CITATIONS:", "clean" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
