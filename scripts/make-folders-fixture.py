"""Generate fixtures/api/history-folders.json -- GET /api/history?range=30d&by=folder.

Run:  python scripts/make-folders-fixture.py

Same reasoning as make-history-fixture.py: a month of samples across three folders
cannot be typed by hand without the occupancy journal and the series drifting apart.
The shape follows subplan 01.3 section 3.6 (`by=folder`) -- folders[], a FLAT
occupancy[] and a FLAT series[], every one of them joined by login_dir_id, and each
series a SEGMENT of one account with its own from/to. Subplan 01.1 section 7.4 sketched
these nested inside the folder; that sketch is amended there, in favour of 01.3.

Three folders, chosen so the view has to handle every case section 7 names:

  dev       three logins in a month, one switch mid-month and one at the end. The
            line must BREAK at each switch: the jump in percent afterwards is a
            different account, not a spike in usage.
  nv-lang   one login the whole month, no drama -- the control case.
  ops       a login that expired two weeks ago and was never replaced: an open
            `no login` stretch that must be grey to the right edge, not absent.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

OUT = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "api" / "history-folders.json"

NOW = datetime(2026, 9, 5, 19, 47, tzinfo=timezone.utc)
FROM = NOW - timedelta(days=30)
STEP = 900  # the endpoint's default for a 30-day range

DIR_DEV = "0192a7f0-0000-7000-8000-000000001001"
DIR_NV = "0192a7f0-0000-7000-8000-000000001002"
DIR_OPS = "0192a7f0-0000-7000-8000-000000001003"

ACC_MAIN = "0192a7f0-0000-7000-8000-000000000001"
ACC_WORK = "0192a7f0-0000-7000-8000-000000000002"
ACC_QA = "0192a7f0-0000-7000-8000-000000000003"


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def daily(start, end, base, slope, peak_at_noon=True):
    """One point a day at noon -- what a 30-day range shows (01.1 section 7.3).

    Hourly samples over a month are 2880 points a folder and read as noise; the spec
    says the session column shows DAILY PEAKS at 30 d, so the fixture carries what
    the page will actually draw.
    """
    points = []
    day = start.replace(hour=12, minute=0, second=0, microsecond=0)
    if day < start:
        day += timedelta(days=1)
    i = 0
    while day <= end:
        points.append({
            "at": iso(day),
            "percent": max(0, min(100, round(base + slope * i))),
            "peak": max(0, min(100, round(base + slope * i))),
            "avg": max(0, min(100, round((base + slope * i) * 0.6))),
            "locked_sec": 0,
            "resets_at": iso(day + timedelta(hours=5)),
            "locked": False,
        })
        day += timedelta(days=1)
        i += 1
    return points


# ------------------------------------------------------- occupancy journal --
# dev changes hands twice; nv-lang never; ops loses its login and never regains it.
dev_1 = (FROM, NOW - timedelta(days=18))
dev_2 = (NOW - timedelta(days=18), NOW - timedelta(days=4))
dev_3 = (NOW - timedelta(days=4), None)
nv_1 = (FROM, None)
ops_1 = (FROM, NOW - timedelta(days=14))          # then nothing: no login since

occupancy = [
    {"login_dir_id": DIR_DEV, "account_id": ACC_MAIN, "email": "main@example.com",
     "token_state": "ok", "from": iso(dev_1[0]), "to": iso(dev_1[1])},
    {"login_dir_id": DIR_DEV, "account_id": ACC_WORK, "email": "work@example.org",
     "token_state": "ok", "from": iso(dev_2[0]), "to": iso(dev_2[1])},
    {"login_dir_id": DIR_DEV, "account_id": ACC_QA, "email": "qa@example.org",
     "token_state": "ok", "from": iso(dev_3[0]), "to": None},
    {"login_dir_id": DIR_NV, "account_id": ACC_MAIN, "email": "main@example.com",
     "token_state": "ok", "from": iso(nv_1[0]), "to": None},
    {"login_dir_id": DIR_OPS, "account_id": ACC_QA, "email": "qa@example.org",
     "token_state": "stale", "from": iso(ops_1[0]), "to": iso(ops_1[1])},
]


def segment(dir_id, acc_id, email, span, kind, model, base, slope):
    a, b = span
    return {
        "login_dir_id": dir_id, "account_id": acc_id, "email": email,
        "kind": kind, "model": model,
        "from": iso(a), "to": iso(b) if b else None,
        "points": daily(a, b or NOW, base, slope),
    }


series = [
    # dev: three segments per window, so the line breaks twice on its own.
    segment(DIR_DEV, ACC_MAIN, "main@example.com", dev_1, "session", None, 20, 1.5),
    segment(DIR_DEV, ACC_WORK, "work@example.org", dev_2, "session", None, 70, -1.0),
    segment(DIR_DEV, ACC_QA, "qa@example.org", dev_3, "session", None, 12, 4.0),
    segment(DIR_DEV, ACC_MAIN, "main@example.com", dev_1, "weekly_all", None, 30, 1.0),
    segment(DIR_DEV, ACC_WORK, "work@example.org", dev_2, "weekly_all", None, 55, 0.5),
    segment(DIR_DEV, ACC_QA, "qa@example.org", dev_3, "weekly_all", None, 18, 3.0),
    segment(DIR_DEV, ACC_MAIN, "main@example.com", dev_1, "weekly_scoped", "Fable", 25, 1.2),
    segment(DIR_DEV, ACC_QA, "qa@example.org", dev_3, "weekly_scoped", "Opus", 10, 2.5),

    # nv-lang: one unbroken segment, the control case.
    segment(DIR_NV, ACC_MAIN, "main@example.com", nv_1, "session", None, 15, 1.1),
    segment(DIR_NV, ACC_MAIN, "main@example.com", nv_1, "weekly_all", None, 22, 0.8),
    segment(DIR_NV, ACC_MAIN, "main@example.com", nv_1, "weekly_scoped", "Fable", 30, 1.4),

    # ops: samples stop when the login expires. Nothing after -- not zeroes.
    segment(DIR_OPS, ACC_QA, "qa@example.org", ops_1, "session", None, 40, -0.8),
    segment(DIR_OPS, ACC_QA, "qa@example.org", ops_1, "weekly_all", None, 50, -0.5),
]

doc = {
    "range": {"from": iso(FROM), "to": iso(NOW), "step_sec": STEP},
    "folders": [
        {"id": DIR_DEV, "path": "C:/accounts/dev", "name": "dev",
         "now": {"account_id": ACC_QA, "email": "qa@example.org", "since": iso(dev_3[0])}},
        {"id": DIR_NV, "path": "C:/accounts/nv-lang", "name": "nv-lang",
         "now": {"account_id": ACC_MAIN, "email": "main@example.com", "since": iso(nv_1[0])}},
        {"id": DIR_OPS, "path": "C:/accounts/ops", "name": "ops",
         "now": None},
    ],
    "occupancy": occupancy,
    "series": series,
    "tiles": {
        "switches": 2,
        "locked_seconds": 0,
        "busiest_folder": {"id": DIR_DEV, "name": "dev",
                           "chain": ["main@example.com", "work@example.org", "qa@example.org"]},
        "days_without_login": {"days": 14, "folder": {"id": DIR_OPS, "name": "ops"},
                               "reason": "token_expired"},
    },
    "note": "the endpoint counts per login: folders sharing one login show the same curve",
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

pts = sum(len(s["points"]) for s in series)
print(f"wrote {OUT.name}")
print(f"  range     {doc['range']['from']} .. {doc['range']['to']} step {STEP}s")
print(f"  folders   {len(doc['folders'])}, occupancy {len(occupancy)}, series {len(series)}")
print(f"  points    {pts}, bytes {OUT.stat().st_size}")
print(f"  dev holds {sum(1 for o in occupancy if o['login_dir_id'] == DIR_DEV)} logins "
      f"-> {sum(1 for o in occupancy if o['login_dir_id'] == DIR_DEV) - 1} switches")
