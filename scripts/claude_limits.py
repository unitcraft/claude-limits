#!/usr/bin/env python3
"""claude-limits reference tool: usage limits of every Claude Code login on this machine.

Modes
  python scripts/claude_limits.py            one snapshot, then exit
  python scripts/claude_limits.py --daemon   a snapshot every interval (default 300 s)

Where the accounts come from, in order of precedence
  1. directories on the command line, or --parent DIR (every child of DIR);
  2. claude-limits.toml (see claude-limits.example.toml):
       accounts_parent = "C:/accounts"   # every child dir holding a login
       accounts        = ["~/.claude"]                    # individual dirs
       interval_sec    = 300
  3. with no config file: ~/.claude and $CLAUDE_CONFIG_DIR.

A directory counts as a login when it holds .credentials.json with a token.
The identity file .claude.json is looked up inside the directory first and
beside it second (the default layout keeps it beside ~/.claude).

Several directories may hold the same account (same e-mail). They are shown
as ONE group with every directory in the label, and the server is asked once
per account, not once per directory: the usage endpoint rate-limits eager
callers with HTTP 429, and the daemon never polls more often than once a
minute for the same reason.

A token is read into memory and sent only to api.anthropic.com. It is never
printed, never written. In daemon mode the config and the token files are
re-read on every cycle, so a login refreshed by Claude Code is picked up
without a restart.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
DEFAULT_INTERVAL = 300
MIN_INTERVAL = 60
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "claude-limits.toml"


# ---------------------------------------------------------------- accounts --

def identity_file(cfg_dir):
    """`.claude.json` inside the dir, else beside it (default layout of ~/.claude)."""
    inside = cfg_dir / ".claude.json"
    return inside if inside.is_file() else cfg_dir.parent / ".claude.json"


def env_dirs():
    dirs = [Path.home() / ".claude"]
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        dirs.append(Path(env))
    return dirs


def children_of(parent):
    parent = Path(parent).expanduser()
    if not parent.is_dir():
        return []
    return [d for d in sorted(parent.iterdir()) if d.is_dir()]


def dedupe(dirs):
    seen, out = set(), []
    for d in dirs:
        d = Path(d).expanduser()
        key = str(d.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def short_name(cfg_dir):
    """Directory name for the label. Every default login is called `.claude`, so
    those get a hint instead: `home/.claude` for the home one (spelled out: the
    owner's terminal does not draw `~`), `wsl:<distro>` for a WSL one reached
    through \\\\wsl.localhost or \\\\wsl$."""
    if cfg_dir.name != ".claude":
        return cfg_dir.name
    parts = cfg_dir.parts
    if parts and parts[0].lower().startswith(("\\\\wsl.localhost\\", "\\\\wsl$\\")):
        return "wsl:" + parts[0].split("\\")[3]
    try:
        cfg_dir.relative_to(Path.home())
        return "home/.claude"
    except ValueError:
        return str(cfg_dir)


def read_login(cfg_dir):
    """One directory -> dict(dir, email, org, token, expired), or None without a login."""
    creds_file = cfg_dir / ".credentials.json"
    if not creds_file.is_file():
        return None
    creds = json.loads(creds_file.read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    token = creds.get("accessToken")
    if not token:
        return None
    email = org = None
    ident = identity_file(cfg_dir)
    if ident.is_file():
        acc = json.loads(ident.read_text(encoding="utf-8")).get("oauthAccount") or {}
        email, org = acc.get("emailAddress"), acc.get("organizationName")
    expires_ms = creds.get("expiresAt") or 0
    return {
        "dir": cfg_dir,
        "email": email,
        "org": org,
        "token": token,
        "expired": expires_ms / 1000 < datetime.now(timezone.utc).timestamp(),
    }


def accounts_of(dirs):
    """Groups logins by e-mail. One entry per account: label, live token (if any), dirs."""
    groups = {}
    for cfg_dir in dirs:
        login = read_login(cfg_dir)
        if login is None:
            continue
        key = (login["email"] or str(cfg_dir)).lower()
        g = groups.setdefault(key, {"email": login["email"], "org": login["org"],
                                    "dirs": [], "expired_dirs": [], "token": None})
        g["dirs"].append(short_name(cfg_dir))
        if login["expired"]:
            g["expired_dirs"].append(short_name(cfg_dir))
        elif g["token"] is None:
            g["token"] = login["token"]
    for g in groups.values():
        who = f"{g['email']} ({g['org'] or '-'})" if g["email"] else "unknown account"
        g["label"] = f"{who}  [{', '.join(g['dirs'])}]"
    return list(groups.values())


# ------------------------------------------------------------------ config --

def load_config(path):
    """Returns the parsed TOML table, or {} when the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        import tomllib
    except ImportError:
        sys.exit("claude-limits.toml needs Python 3.11+ (tomllib); run with directories on the command line instead")
    with open(path, "rb") as f:
        return tomllib.load(f)


def dirs_from(args, config):
    if args.parent:
        return dedupe(children_of(args.parent))
    if args.dirs:
        return dedupe(args.dirs)
    dirs = []
    if config.get("accounts_parent"):
        dirs += children_of(config["accounts_parent"])
    dirs += config.get("accounts") or []
    if not dirs:
        dirs = env_dirs()
    return dedupe(dirs)


# ------------------------------------------------------------------- usage --

def fetch_usage(token):
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": "Bearer " + token, "anthropic-beta": BETA_HEADER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def remaining(iso):
    """Time left until the reset, in the widget's own shape: 2d 18h / 1h 52min / 7min."""
    left = datetime.fromisoformat(iso) - datetime.now(timezone.utc)
    secs = int(left.total_seconds())
    if secs <= 0:
        return "now"
    days, rest = divmod(secs, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def local_time(iso):
    if not iso:
        return "-"
    when = datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    return f"{when} ({remaining(iso)})"


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


def retry_after_of(err):
    """Seconds the server asked us to wait, from Retry-After; None when absent."""
    value = err.headers.get("Retry-After") if err.headers else None
    return int(value) if value and value.isdigit() else None


# ----------------------------------------------------------------- colours --

class Paint:
    """ANSI colours for the terminal. Off when stdout is not a terminal (the
    -Detached log file), when NO_COLOR is set, or with --color never.

    The progress bar is drawn with block glyphs in the severity FOREGROUND
    colour: filled cells green / yellow / red, empty cells dim grey. A colour
    header marker sits in front of each account. If the block glyphs come out
    blank, the terminal font has no block characters — switch the font (see the
    README) or pass --bar-style ascii for a `#`/`.` bar."""

    FG = {"normal": "32", "warning": "33", "critical": "31"}    # green / yellow / red foreground
    HEADER_WIDTH = 64                                           # the account header highlight bar

    def __init__(self, enabled):
        self.enabled = enabled
        if enabled and os.name == "nt":
            enable_windows_vt()

    def _wrap(self, code, text):
        return f"\x1b[{code}m{text}\x1b[0m" if self.enabled else text

    def _line(self, code, text):
        """The whole account header as one highlight bar: padded text on a colour
        background, so the entire line is lit, not just a marker."""
        if not self.enabled:
            return text
        padded = text.ljust(max(self.HEADER_WIDTH, len(text) + 1))
        return self._wrap(code, padded)

    def live(self, text):     return self._line("30;42", text)  # black on green: token works, data fresh
    def dead(self, text):     return self._line("97;41", text)  # white on red: token expired or rejected
    def unknown(self, text):  return self._line("30;43", text)  # black on yellow: server or network said no

    def fill(self, text, severity):     return self._wrap(self.FG.get(severity, "32"), text)
    def empty(self, text):              return self._wrap("90", text)


BAR_WIDTH = 30


def severity_of(sev, pct):
    """The server's word when it gives one; otherwise derived from the percent."""
    if sev in ("normal", "warning", "critical"):
        return sev
    if pct is None:
        return "normal"
    return "critical" if pct >= 90 else "warning" if pct >= 70 else "normal"


BAR_GLYPHS = {"blocks": ("█", "░"), "ascii": ("#", ".")}


def bar_of(pct, sev, style, paint):
    """A 30-cell bar between brackets. 'blocks' -> [████░░░░], 'ascii' -> [####....].
    Filled part coloured green/yellow/red by severity, empty part dim."""
    full, empty = BAR_GLYPHS.get(style, BAR_GLYPHS["blocks"])
    if pct is None:
        return "[" + paint.empty(empty * BAR_WIDTH) + "]"
    filled = round(min(max(pct, 0), 100) / 100 * BAR_WIDTH)
    fill = paint.fill(full * filled, severity_of(sev, pct)) if filled else ""
    return "[" + fill + paint.empty(empty * (BAR_WIDTH - filled)) + "]"


def enable_windows_vt():
    """Lets the classic Windows console interpret ANSI escapes (Windows Terminal already does)."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)                 # STD_OUTPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)   # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def colours_enabled(choice):
    if choice == "always":
        return True
    if choice == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


# ---------------------------------------------------------------- printing --

def snapshot(dirs, paint, bar_style):
    """Prints every account found in dirs. Returns (accounts_found, seconds_to_back_off)."""
    accounts = accounts_of(dirs)
    backoff = 0
    for acc in accounts:
        expired_note = (f"  ({', '.join(acc['expired_dirs'])}: token expired on disk)"
                        if acc["expired_dirs"] and acc["token"] else None)
        if acc["token"] is None:
            # No request with a dead token: the server answers 401, then 429 on
            # repeats. Only Claude Code refreshes it (README, Token lifetime).
            print("\n" + paint.dead(acc["label"]))
            print("  token expired on disk: start Claude Code under this directory to refresh it")
            continue
        try:
            usage = fetch_usage(acc["token"])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = retry_after_of(e)
                backoff = max(backoff, wait or MIN_INTERVAL)
                asked = f"server asks to wait {wait} s" if wait else "no Retry-After given"
                head, msg = paint.unknown(acc["label"]), f"HTTP 429: too many requests from this machine; {asked}"
            elif e.code == 401:
                head, msg = paint.dead(acc["label"]), "HTTP 401: token rejected"
            else:
                body = e.read().decode("utf-8", "replace").strip().replace("\n", " ")
                head, msg = paint.unknown(acc["label"]), f"HTTP {e.code}: {body[:160]}"
            print("\n" + head)
            if expired_note:
                print(expired_note)
            print("  " + msg)
            continue
        except OSError as e:
            print("\n" + paint.unknown(acc["label"]))
            if expired_note:
                print(expired_note)
            print(f"  network error: {e}")
            continue
        print("\n" + paint.live(acc["label"]))
        if expired_note:
            print(expired_note)
        for kind, pct, sev, reset in rows_of(usage):
            pct_s = "-" if pct is None else f"{pct:>3.0f}%"
            print(f"  {kind:<22} {bar_of(pct, sev, bar_style, paint)} {pct_s:>4}  {sev:<8} resets {reset}")
    if not accounts:
        print("\nno Claude Code logins found in:", ", ".join(str(d) for d in dirs))
    return len(accounts), backoff


def parse_args(argv):
    p = argparse.ArgumentParser(description="usage limits of every Claude Code login on this machine")
    p.add_argument("dirs", nargs="*", help="config directories to read (override the config file)")
    p.add_argument("--parent", metavar="DIR", help="read every child directory of DIR")
    p.add_argument("--config", metavar="PATH", default=str(DEFAULT_CONFIG),
                   help=f"TOML config (default: {DEFAULT_CONFIG})")
    p.add_argument("--daemon", action="store_true", help="repeat every interval instead of exiting")
    p.add_argument("--interval", type=int, metavar="SEC",
                   help=f"seconds between snapshots in --daemon mode (default: config or {DEFAULT_INTERVAL}, "
                        f"never below {MIN_INTERVAL})")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto",
                   help="account headers green (live), red (token dead), yellow (server or network failed); "
                        "auto = only on a terminal")
    p.add_argument("--bar-style", choices=["blocks", "ascii"],
                   help="progress bar glyphs: ascii [####....] (default) or blocks [████░░░░] "
                        "for fonts that have the block glyphs; also 'bar_style' in the config")
    return p.parse_args(argv)


def bar_style_of(args, config):
    return args.bar_style or config.get("bar_style") or "blocks"


def interval_of(args, config, quiet=False):
    wanted = args.interval or config.get("interval_sec") or DEFAULT_INTERVAL
    if wanted < MIN_INTERVAL:
        if not quiet:
            print(f"interval {wanted} s is below the floor; using {MIN_INTERVAL} s (the server rate-limits eager polling)")
        return MIN_INTERVAL
    return wanted


def main(argv):
    args = parse_args(argv)
    config = load_config(args.config)
    paint = Paint(colours_enabled(args.color))
    # An organisation name outside the console code page must never crash the daemon.
    sys.stdout.reconfigure(errors="replace")
    if not args.daemon:
        found, _ = snapshot(dirs_from(args, config), paint, bar_style_of(args, config))
        return 0 if found else 1

    interval = interval_of(args, config)
    print(f"claude-limits daemon: every {interval} s, config {args.config}; Ctrl+C to stop")
    try:
        while True:
            config = load_config(args.config)          # edits apply without a restart
            interval = interval_of(args, config, quiet=True)
            print(f"\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            _, backoff = snapshot(dirs_from(args, config), paint, bar_style_of(args, config))
            wait = max(interval, backoff)
            if wait > interval:
                print(f"\nbacking off: next snapshot in {wait} s")
            sys.stdout.flush()
            time.sleep(wait)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
