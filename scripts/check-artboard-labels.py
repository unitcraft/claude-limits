# -*- coding: utf-8 -*-
"""Every label the artboards show must be accounted for.

    python scripts/check-artboard-labels.py

WHY. Three defects today came from one manual act: extract the labels an artboard
shows and read them beside the page. The footer was missing `. next 19:52` and its
whole legend; a `429` account had its numbers blanked instead of dimmed. Each was a
label the design shows and the page could not produce, and each passed every test we
had. Doing that by hand once is a lucky afternoon; this makes it repeatable.

WHAT IT LOOKS AT. Only labels with NO DIGIT in them. The first run reported 106
unaccounted labels and that was noise, not a gate: almost all were rendered output
(`19:47 . 15 s ago`, `74%`, `Tue 13:00`), which no literal search in the sources can
find and which the fixtures hold only as raw numbers. Dropping anything with a digit
leaves the chrome -- the words a designer wrote and a renderer must reproduce.

The cost of that filter, stated rather than hidden: a chrome label that CONTAINS a
number is invisible to this check. `samples every 5 min . kept 30 days` is exactly
such a label and exactly such a gap; it was found by hand and is in the exceptions
file with that note.

WHAT IT CAN AND CANNOT DECIDE. It cannot tell whether a label is right -- only
whether it is ACCOUNTED FOR. A label is accounted for when it is

  * produced by the page: found in `src/web/*.{js,html}`, or
  * sample DATA rather than chrome: found in the fixtures the page renders, or
  * listed in `docs/design/artboard-exceptions.txt` with a reason on the same line.

Anything else is reported. The exceptions file is the honest half: a design detail
deliberately not built is a DECISION, and a decision belongs in writing next to the
thing it is about, not in the memory of whoever skipped it.

The exceptions file is checked too. An entry that no longer matches any artboard
label is stale, and a stale exception hides the next gap instead of naming one --
the same failure the phase-6 list in lint-openapi.py is guarded against.
"""
import pathlib
import re
import sys

# The console here is cp1251 and the findings carry arrows, middots and Cyrillic.
# Without this the report dies halfway through with a UnicodeEncodeError, which reads
# like a crash in the thing being checked rather than in the checker.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "docs" / "design" / "browser-page"
WEB = ROOT / "src" / "web"
FIXTURES = ROOT / "fixtures"
EXCEPTIONS = ROOT / "docs" / "design" / "artboard-exceptions.txt"

# The PAGE designs, named rather than globbed. `archive/` holds superseded ones, and
# `ApiMap`/`DbSchema` in this same folder are documentation drawings -- their labels
# are architecture notes, not chrome the page owes anybody.
#
# Named explicitly so a rename fails loudly instead of quietly shrinking the check:
# a glob would have kept passing while covering less, which is the failure this whole
# family of checkers exists to refuse.
PAGE_ARTBOARDS = [
    "Main.dc.html", "MainBlocks.dc.html", "CardsView.dc.html",
    "StatsView.dc.html", "StatsFolders.dc.html", "SettingsPanel.dc.html",
]
ARTBOARDS = [ART / name for name in PAGE_ARTBOARDS]


def labels_of(path):
    t = path.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    out = []
    for m in re.finditer(r">([^<>]+)<", t):
        s = " ".join(m.group(1).split())
        if s and not s.startswith("&") and len(s) <= 60:
            out.append(s)
    return list(dict.fromkeys(out))


def haystack():
    """The strings the page can put ON SCREEN -- not every byte of its source.

    THIS USED TO BE THE WHOLE SOURCE, CONCATENATED, and a label counted as "produced
    by the page" if its letters appeared anywhere in it. Measured 2026-09-09: four
    labels of the settings panel were accepted by rubbish, and every one of them is a
    control a person clicks:

        Bar style   from the identifier   bar.style.width
        Rounded     from a comment        "in a rounded panel"
        Blocks      from a comment        "Only a 429 blocks it."
        Layout      from the identifier   layoutCells

    The normaliser strips punctuation, so `bar.style.width` becomes `bar style width`
    and contains `bar style`. A guard whose whole job is "the mock shows a control the
    page does not have" was answering yes on a variable name.

    So: string literals and HTML text, with comments removed first. A label the page
    genuinely renders lives in one of those. An identifier does not, and neither does
    prose about the code.
    """
    out = []
    for f in sorted(WEB.glob("*.js")) + sorted(WEB.glob("*.html")) + sorted(WEB.glob("*.css")):
        t = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix == ".html":
            t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
            out.append(re.sub(r"<[^>]+>", " ", t))          # the text between tags
            out.extend(re.findall(r'"([^"]*)"', t))          # attribute values
        else:
            t = re.sub(r"//[^\n]*", " ", t)
            t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)
            out.extend(re.findall(r"'([^'\n]*)'", t))
            out.extend(re.findall(r'"([^"\n]*)"', t))
            out.extend(re.findall(r"`([^`]*)`", t))
    # Joined with a separator that cannot occur inside a literal, so a label can never
    # be matched across the seam between two unrelated strings.
    return "\n\x00\n".join(x for x in out if x.strip())


def fixture_text():
    parts = []
    for f in sorted(FIXTURES.rglob("*.json")):
        parts.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def read_exceptions():
    """`<label>  # <reason>` per line. A reason is required, and that is the point."""
    out = {}
    if not EXCEPTIONS.exists():
        return out
    for i, line in enumerate(EXCEPTIONS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        if "#" not in line:
            out[line.strip()] = None          # no reason: reported below
            continue
        label, reason = line.split("#", 1)
        out[label.strip()] = reason.strip() or None
    return out


def normalise(s):
    """Compare on the words, not on the punctuation a design tool inserts."""
    return re.sub(r"[\s·→–—.,:;()\[\]]+", " ", s).strip().lower()


def main():
    absent = [a.name for a in ARTBOARDS if not a.exists()]
    if absent:
        print(f"FAILED: named page artboards are missing: {absent}")
        print("  A renamed artboard must be renamed here too -- otherwise the check")
        print("  keeps passing while covering less.")
        return 1

    page = haystack()
    page_n = normalise(page)
    data_n = normalise(fixture_text())
    exceptions = read_exceptions()

    bad, unaccounted, used_exceptions = [], [], set()

    for art in ARTBOARDS:
        for label in labels_of(art):
            if re.search(r"\d", label):
                continue                       # rendered data, not chrome -- see the header
            n = normalise(label)
            if not n:
                continue
            if n in page_n:
                continue                       # the page produces it
            if n in data_n:
                continue                       # sample data, not chrome
            if label in exceptions:
                used_exceptions.add(label)
                if exceptions[label] is None:
                    bad.append(f"{EXCEPTIONS.name}: `{label}` is excepted with NO reason "
                               f"-- an unexplained exception is just a hidden gap")
                continue
            unaccounted.append((art.name, label))

    stale = [l for l in exceptions if l not in used_exceptions]
    for l in stale:
        bad.append(f"{EXCEPTIONS.name}: `{l}` matches no artboard label any more "
                   f"-- a stale exception hides the next gap instead of naming one")

    print(f"artboards: {len(ARTBOARDS)}, chrome labels unaccounted: {len(unaccounted)}, "
          f"exceptions: {len(exceptions)} ({len(used_exceptions)} in use)")
    for name, label in unaccounted:
        bad.append(f"{name}: `{label}` is shown by the design and produced by nothing. "
                   f"Build it, or add it to {EXCEPTIONS.name} with a reason.")

    print("ARTBOARD LABELS:", "clean" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
