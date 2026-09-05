#!/usr/bin/env python3
"""Reference probe for the claude-limits data path.

Discovers Claude Code config directories, reads each login's OAuth token,
asks the usage endpoint and prints one row per account and limit window.

A token is read into memory and sent only to api.anthropic.com. Nothing
else is done with it: it is never printed, never written.

Usage:
  python scripts/probe.py                    # default dir + $CLAUDE_CONFIG_DIR
  python scripts/probe.py DIR [DIR ...]      # explicit config dirs
  python scripts/probe.py --parent DIR       # every child dir of DIR
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"


def default_dirs():
    """The default layout keeps .claude.json BESIDE ~/.claude, not inside it."""
    home = Path.home()
    dirs = [(home / ".claude", home / ".claude.json")]
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        d = Path(env)
        dirs.append((d, d / ".claude.json"))
    return dirs


def explicit_dirs(paths):
    return [(Path(p), Path(p) / ".claude.json") for p in paths]


def children_of(parent):
    return [(d, d / ".claude.json") for d in sorted(Path(parent).iterdir()) if d.is_dir()]


def read_account(cfg_dir, cfg_file):
    """Returns (label, token, expired) or None when the dir holds no login."""
    creds_file = cfg_dir / ".credentials.json"
    if not creds_file.is_file():
        return None
    creds = json.loads(creds_file.read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    token = creds.get("accessToken")
    if not token:
        return None
    # The directory name stays in the label: two directories may hold the
    # same login, and the rows must stay tellable apart.
    label = str(cfg_dir)
    if cfg_file.is_file():
        acc = json.loads(cfg_file.read_text(encoding="utf-8")).get("oauthAccount") or {}
        email = acc.get("emailAddress")
        if email:
            label = f"{email} ({acc.get('organizationName') or '-'})  [{cfg_dir.name}]"
    expires_ms = creds.get("expiresAt") or 0
    expired = expires_ms / 1000 < datetime.now(timezone.utc).timestamp()
    return label, token, expired


def fetch_usage(token):
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": "Bearer " + token, "anthropic-beta": BETA_HEADER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def local_time(iso):
    if not iso:
        return "-"
    return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")


def rows_of(usage):
    """One row per limit window; falls back to the two fixed windows."""
    limits = usage.get("limits")
    if limits:
        for lim in limits:
            scope = (lim.get("scope") or {}).get("model") or {}
            kind = lim.get("kind", "?")
            if scope.get("display_name"):
                kind += ":" + scope["display_name"]
            yield kind, lim.get("percent"), lim.get("severity", "-"), local_time(lim.get("resets_at"))
        return
    for kind in ("five_hour", "seven_day"):
        w = usage.get(kind) or {}
        yield kind, w.get("utilization"), w.get("locked_reason") or "-", local_time(w.get("resets_at"))


def main(argv):
    if argv[:1] == ["--parent"] and len(argv) == 2:
        dirs = children_of(argv[1])
    elif argv:
        dirs = explicit_dirs(argv)
    else:
        dirs = default_dirs()

    found = 0
    for cfg_dir, cfg_file in dirs:
        acc = read_account(cfg_dir, cfg_file)
        if acc is None:
            continue
        found += 1
        label, token, expired = acc
        print(f"\n{label}" + ("   [token expired on disk]" if expired else ""))
        try:
            usage = fetch_usage(token)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: token rejected" if e.code == 401 else f"  HTTP {e.code}")
            continue
        except OSError as e:
            print(f"  network error: {e}")
            continue
        for kind, pct, sev, reset in rows_of(usage):
            pct_s = "-" if pct is None else f"{pct:>3.0f}%"
            print(f"  {kind:<22} {pct_s:>5}  {sev:<8} resets {reset}")
    if not found:
        print("no Claude Code logins found in:", ", ".join(str(d) for d, _ in dirs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
