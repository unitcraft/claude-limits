# -*- coding: utf-8 -*-
"""Draw docs/img/limits-demo.png: the page over INVENTED accounts, for the README.

    python scripts/readme_shot.py

Every address, name and number here is made up; no real login is read. The snapshot is
built relative to "now" so the reset times and the hatching look as they do live, then
served through `preview.py`'s handler and photographed by headless Edge or Chrome.
"""
import datetime as dt
import http.server
import json
import pathlib
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import preview  # noqa: E402

ROOT = preview.ROOT
OUT = ROOT / "docs" / "img" / "limits-demo.png"
PORT = 7393
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "chrome", "google-chrome", "chromium",
]


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def left_label(sec):
    h, m = divmod(sec // 60, 60)
    d, h = divmod(h, 24)
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}min")


def limit(acc, kind, label, pct, window_sec, left_sec, sev="normal", model=None,
          locked=False, reason=None, active=False, forecast=None):
    at = NOW + dt.timedelta(seconds=left_sec)
    return {
        "account_id": acc, "kind": kind, "model": model, "label": label, "percent": pct,
        "severity": sev, "server_severity": sev if sev != "normal" else "normal",
        "locked": locked, "locked_reason": reason, "active": active,
        "resets_at": iso(at), "seconds_left": left_sec,
        "reset_label": f"resets {at.strftime('%a %H:%M')} ({left_label(left_sec)})",
        "window_sec": window_sec, "elapsed_share": round(1 - left_sec / window_sec, 2),
        "forecast": forecast,
    }


def fc(pct, label, sev="normal", ends_in=None, rate=2.0):
    return {
        "percent_at_reset": pct, "runs_out_at": iso(NOW + dt.timedelta(seconds=ends_in)) if ends_in else None,
        "rate_per_hour": rate, "basis": "clock", "sample_minutes": 120, "label": label,
        "warning": pct >= 100, "severity": sev,
    }


def acc(n, provider, email, name, state="ok", message=None, locked=False, at_100=False):
    return {
        "id": f"0192a7f0-0000-7000-8000-00000000000{n}", "provider": provider, "email": email,
        "org": "Example Org" if provider == "claude" and email else None, "display_name": name,
        "dirs": [{"id": f"0192a7f0-0000-7000-8000-00000000100{n}", "path": f"~/demo/{name}", "name": name}],
        "state": state, "message": message, "polled_at": iso(NOW), "next_poll_at": iso(NOW + dt.timedelta(minutes=5)),
        "locked": locked, "at_100": at_100, "same_quota_as": None,
    }


H, D = 3600, 86400
A = [
    acc(1, "claude", "calm@example.com", "calm"),
    acc(2, "claude", "pace@example.com", "pace"),
    acc(3, "claude", "locked@example.com", "locked", locked=True, at_100=True),
    acc(4, "claude", "expired@example.com", "expired", state="stale",
        message="token expired · start Claude Code under this login"),
    acc(5, "claude", "retry@example.com", "retry", state="unknown",
        message=f"HTTP 429 · retry {(NOW + dt.timedelta(minutes=9)).strftime('%H:%M')} · data {(NOW - dt.timedelta(minutes=4)).strftime('%H:%M')}"),
    acc(6, "kimi", None, "kimi-code-demo"),
    acc(7, "codex", None, "codex@example.com"),
]
i = lambda n: A[n - 1]["id"]
L = [
    # calm: everything low, the forecast lands well below 100%
    limit(i(1), "session", "session 5h", 9, 5 * H, 1 * H, active=True, forecast=fc(11, "→ 11% at reset")),
    limit(i(1), "weekly_all", "all 7d", 14, 7 * D, 5 * D, forecast=fc(46, "→ 46% at reset")),
    limit(i(1), "weekly_scoped", "Opus 7d", 0, 7 * D, 5 * D, model="Opus", forecast=fc(0, "→ 0% at reset")),
    # pace: above the warning line, and at this pace the quota ends before the window does
    limit(i(2), "session", "session 5h", 78, 5 * H, 2 * H, sev="warning", active=True,
          forecast=fc(130, "→ 130% at reset, ends in 1h 10m", "critical", ends_in=4200, rate=26.0)),
    limit(i(2), "weekly_all", "all 7d", 52, 7 * D, 4 * D, forecast=fc(88, "→ 88% at reset", "warning")),
    # locked: the limit is reached, the account waits for the reset
    limit(i(3), "session", "session 5h", 100, 5 * H, int(1.5 * H), sev="critical", locked=True,
          reason="usage_limit_reached", active=True),
    limit(i(3), "weekly_all", "all 7d", 96, 7 * D, 3 * D, sev="critical"),
    # last good reading kept while the server asks to wait
    limit(i(5), "session", "session 5h", 40, 5 * H, 3 * H, active=True, forecast=fc(62, "→ 62% at reset")),
    # Kimi Code and Codex
    limit(i(6), "session", "session 5h", 35, 5 * H, 2 * H, active=True, forecast=fc(55, "→ 55% at reset")),
    limit(i(6), "monthly", "month", 78, 30 * D, 12 * D, sev="warning", forecast=fc(95, "→ 95% at reset", "warning")),
    limit(i(7), "session", "session 5h", 61, 5 * H, 2 * H, active=True, forecast=fc(85, "→ 85% at reset", "warning")),
    limit(i(7), "weekly_all", "all 7d", 33, 7 * D, 2 * D, forecast=fc(46, "→ 46% at reset")),
]
SNAP = {
    "fetched_at": iso(NOW), "next_poll_at": iso(NOW + dt.timedelta(minutes=5)), "tz": "UTC",
    "restored": False,
    "worst": {"account_id": i(3), "kind": "session", "percent": 100, "severity": "critical"},
    "accounts": A, "limits": L,
}


def find_browser():
    for b in BROWSERS:
        if pathlib.Path(b).exists() or shutil.which(b):
            return b
    raise SystemExit("no Edge or Chrome found")


def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    snap = tmp / "snapshot.json"
    snap.write_text(json.dumps(SNAP), encoding="utf-8")
    preview.ROUTES["/api/snapshot"] = snap
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), preview.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([
            find_browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--user-data-dir={tmp / 'profile'}", "--window-size=1100,1260",
            "--virtual-time-budget=6000", f"--screenshot={OUT}", f"http://127.0.0.1:{PORT}/",
        ], check=True, timeout=120)
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
