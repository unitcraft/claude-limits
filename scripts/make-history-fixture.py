"""Generate fixtures/api/history-7d.json -- the reply of GET /api/history?range=7d&by=account.

Run:  python scripts/make-history-fixture.py

WHY A GENERATOR AND NOT A HAND-WRITTEN FILE. A week of hourly samples is 168 points
per series and eight series; typed by hand it would be both unreadable and quietly
inconsistent -- a lock band that does not line up with the 100 % samples under it, a
gap whose edges do not match the missing points. Here the shape is stated once, in
code, and the file is derived from it. THIS SCRIPT is the readable source; the JSON is
compact on purpose and is not meant to be read.

The shape follows subplan 01.3 section 3.6 exactly: range, accounts[] with a summary,
FLAT series[] joined to accounts by account_id, and tiles. Three accounts, chosen so
every case the page must draw is present:

  main@example.com  a quiet week: a session sawtooth, a weekly line rising to 74 %
                    with a pace warning, no locks and no gaps.
  work@example.org  two locks, one of them STILL RUNNING (to: null) -- the case that
                    is dropped by any renderer treating `to` as required.
  qa@example.org    a five-hour gap from a 429, and no per-model limit at all: the
                    plan simply has none, which the page must say rather than draw an
                    empty chart.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

OUT = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "api" / "history-7d.json"

# A FIXED "now", so the file is byte-identical on every run and a diff means a real
# change. Saturday 2026-09-05 19:47 UTC -- the moment the artboards are drawn at.
NOW = datetime(2026, 9, 5, 19, 47, tzinfo=timezone.utc)
FROM = NOW - timedelta(days=7)
STEP = 3600  # seconds; one of the four values the endpoint accepts

ID_MAIN = "0192a7f0-0000-7000-8000-000000000001"
ID_WORK = "0192a7f0-0000-7000-8000-000000000002"
ID_QA = "0192a7f0-0000-7000-8000-000000000003"


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def grid():
    """Every sample moment in the range, oldest first."""
    t = FROM
    out = []
    while t <= NOW:
        out.append(t)
        t += timedelta(seconds=STEP)
    return out


def session_points(times, peak, locked_spans=(), skip=()):
    """A five-hour session window: rises through the window, resets to near zero.

    `peak` is the highest percent reached in a window; the sawtooth is deterministic
    (no randomness at all) so the numbers in the tiles can be asserted.
    """
    points = []
    resets = []
    for t in times:
        if any(a <= t < b for a, b in skip):
            continue
        # Windows are anchored to 00:00 UTC and last five hours.
        hours = (t - t.replace(hour=0, minute=0, second=0)).total_seconds() / 3600
        into = hours % 5
        end = t + timedelta(hours=5 - into)
        pct = round(peak * (into / 5.0))
        locked = any(a <= t < b for a, b in locked_spans)
        if locked:
            pct = 100
        points.append({"at": iso(t), "percent": pct, "resets_at": iso(end), "locked": locked})
        if into < 1 and (not resets or resets[-1] != iso(t)):
            resets.append(iso(t))
    return points, resets[1:]  # the first "reset" is just the start of the range


def weekly_points(times, start, end_pct, skip=()):
    """A weekly window: a line rising from `start` to `end_pct` across the range."""
    span = (times[-1] - times[0]).total_seconds()
    out = []
    for t in times:
        if any(a <= t < b for a, b in skip):
            continue
        share = (t - times[0]).total_seconds() / span
        out.append({
            "at": iso(t),
            "percent": round(start + (end_pct - start) * share),
            "resets_at": iso(NOW + timedelta(days=2, hours=17)),
            "locked": False,
        })
    return out


def summarize(session, locks):
    """Summary numbers DERIVED from the points, never typed in beside them.

    The first version of this file stated peak_session = 62 next to a sawtooth whose
    highest sample was 59, because the samples land on whole hours and never touch
    the top of the window. A fixture that contradicts itself is worse than no fixture:
    a page reading the summary and a page reading the points would BOTH look correct
    against it, and the disagreement would only surface against a real backend.
    """
    pcts = [p["percent"] for p in session]
    peak = max(pcts) if pcts else 0
    avg = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
    locked = 0
    for lk in locks:
        a = datetime.strptime(lk["from"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        b = (datetime.strptime(lk["to"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
             if lk["to"] else NOW)
        locked += int((b - a).total_seconds())
    # How many separate times the window sat at 100 %, not how many samples did.
    runs, was = 0, False
    for p in pcts:
        if p >= 100 and not was:
            runs += 1
        was = p >= 100
    return peak, avg, locked, runs


times = grid()

# ------------------------------------------------------------------ main --
main_session, main_resets = session_points(times, peak=62)
main_all = weekly_points(times, 4, 22)
main_fable = weekly_points(times, 9, 74)

# ------------------------------------------------------------------ work --
# Two locks: one closed on Tuesday, one that is STILL RUNNING at `now`.
lock1 = (NOW - timedelta(days=3, hours=5), NOW - timedelta(days=3, hours=3, minutes=20))
lock2 = (NOW - timedelta(hours=1), None)
spans = [lock1, (lock2[0], NOW + timedelta(hours=1))]
work_session, work_resets = session_points(times, peak=100, locked_spans=spans)
work_all = weekly_points(times, 30, 61)
work_opus = weekly_points(times, 20, 58)

# -------------------------------------------------------------------- qa --
# A five-hour hole from a 429: the samples are ABSENT, not zero. A renderer that
# fills them with zero draws a canyon that never happened.
gap = (NOW - timedelta(hours=9), NOW - timedelta(hours=4))
qa_session, qa_resets = session_points(times, peak=41, skip=[gap])
qa_all = weekly_points(times, 44, 58, skip=[gap])

work_locks = [
    {"from": iso(lock1[0]), "to": iso(lock1[1]), "reason": "server",
     "server_reason": "session_limit"},
    {"from": iso(lock2[0]), "to": None, "reason": "server", "server_reason": "session_limit"},
]

main_peak, main_avg, main_locked, _ = summarize(main_session, [])
work_peak, work_avg, work_locked, work_runs = summarize(work_session, work_locks)
qa_peak, qa_avg, qa_locked, _ = summarize(qa_session, [])

# `pace_per_hour` and `runs_out_at` are a FORECAST, not a fact about the samples: the
# backend computes them from the working-hours model (01.1 sec.2.7), so they are
# declared here rather than derived, and only for the account the tile names.
doc = {
    "range": {"from": iso(FROM), "to": iso(NOW), "step_sec": STEP},
    "accounts": [
        {
            "id": ID_MAIN, "email": "main@example.com", "color_slot": 0,
            "summary": {
                "peak_session": main_peak, "avg_session": main_avg, "locked_sec": main_locked,
                "pace_per_hour": 2.06, "runs_out_at": iso(NOW + timedelta(days=2, hours=16)),
            },
        },
        {
            "id": ID_WORK, "email": "work@example.org", "color_slot": 1,
            "summary": {
                "peak_session": work_peak, "avg_session": work_avg, "locked_sec": work_locked,
                "pace_per_hour": 0.9, "runs_out_at": None,
            },
        },
        {
            "id": ID_QA, "email": "qa@example.org", "color_slot": 2,
            "summary": {
                "peak_session": qa_peak, "avg_session": qa_avg, "locked_sec": qa_locked,
                "pace_per_hour": 0.4, "runs_out_at": None,
            },
        },
    ],
    "series": [
        {"account_id": ID_MAIN, "kind": "session", "model": None,
         "points": main_session, "resets": main_resets, "locks": [], "gaps": []},
        {"account_id": ID_MAIN, "kind": "weekly_all", "model": None,
         "points": main_all, "resets": [], "locks": [], "gaps": []},
        {"account_id": ID_MAIN, "kind": "weekly_scoped", "model": "Fable",
         "points": main_fable, "resets": [], "locks": [], "gaps": []},

        {"account_id": ID_WORK, "kind": "session", "model": None,
         "points": work_session, "resets": work_resets, "locks": work_locks, "gaps": []},
        {"account_id": ID_WORK, "kind": "weekly_all", "model": None,
         "points": work_all, "resets": [], "locks": [], "gaps": []},
        {"account_id": ID_WORK, "kind": "weekly_scoped", "model": "Opus",
         "points": work_opus, "resets": [], "locks": [], "gaps": []},

        {"account_id": ID_QA, "kind": "session", "model": None,
         "points": qa_session, "resets": qa_resets, "locks": [],
         "gaps": [{"from": iso(gap[0]), "to": iso(gap[1]), "cause": "http_429"}]},
        {"account_id": ID_QA, "kind": "weekly_all", "model": None,
         "points": qa_all, "resets": [], "locks": [],
         "gaps": [{"from": iso(gap[0]), "to": iso(gap[1]), "cause": "http_429"}]},
    ],
    "tiles": {
        "locked": {"seconds": main_locked + work_locked + qa_locked, "account_id": ID_WORK,
                   "email": "work@example.org", "when": ["Wed 14:47-16:27", "Sat 18:47-now"]},
        "peak_session": {"percent": max(main_peak, work_peak, qa_peak), "account_id": ID_WORK,
                         "email": "work@example.org", "times": work_runs},
        "avg_session": {"percent": round((main_avg + work_avg + qa_avg) / 3), "accounts": 3},
        "pace": {"rate_per_hour": 2.06, "account_id": ID_MAIN, "email": "main@example.com",
                 "model": "Fable", "runs_out_at": iso(NOW + timedelta(days=2, hours=16)),
                 "label": "Fable ends Tue ~12:30, 30 m before reset"},
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

points = sum(len(s["points"]) for s in doc["series"])
print(f"wrote {OUT.relative_to(OUT.parent.parent.parent)}")
print(f"  range   {doc['range']['from']} .. {doc['range']['to']} step {STEP}s")
print(f"  series  {len(doc['series'])}, points {points}, bytes {OUT.stat().st_size}")
print(f"  locks   {sum(len(s['locks']) for s in doc['series'])} "
      f"(one open), gaps {sum(len(s['gaps']) for s in doc['series'])}")
