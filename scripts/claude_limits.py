#!/usr/bin/env python3
r"""claude-limits reference tool: usage limits of every Claude Code login on this machine.

Modes
  python scripts/claude_limits.py            one snapshot, then exit
  python scripts/claude_limits.py --daemon   a snapshot every interval (default 300 s)

Where the accounts come from, in order of precedence
  1. directories on the command line, or --parent DIR (every child of DIR);
  2. claude-limits.toml (see claude-limits.example.toml):
       accounts = [{ dir = "~/.claude", kind = "claude" },
                   { dir = "D:/accounts", kind = "claude", children = true },
                   { dir = "~/.kimi-code", kind = "kimi" }]
       interval_sec = 300
  3. with no config file: ~/.claude, $CLAUDE_CONFIG_DIR and ~/.kimi-code
     ($KIMI_CODE_HOME).

Every directory is scanned for the kind of login its entry names: claude
looks for .credentials.json with a token, kimi for credentials/*.json with
access tokens (one account per file, the layout of KIMI_CODE_HOME), auto
accepts either -- and a directory may hold one of each. `kind` is mandatory:
a bare path in the config is an error, so the choice is never guessed.

A directory counts as a login when it holds .credentials.json with a token.
The identity file .claude.json is looked up inside the directory and beside
it; when both exist, the FRESHEST profile wins (see identity_file for why
position alone labels a directory with a stale identity).

Several directories may hold the same account (same e-mail). They are shown
as ONE group with every directory in the label, and the server is asked once
per account, not once per directory: the usage endpoint rate-limits eager
callers with HTTP 429, and the daemon never polls more often than once a
minute for the same reason.

A Claude token is read into memory and sent only to api.anthropic.com. It is
never printed, never written: an expired Claude login is renewed by starting
Claude Code, which rewrites its own .credentials.json. A Kimi login has no
such binary guaranteed on the machine, so there the tool calls the OAuth
refresh grant itself and rewrites the credentials file atomically -- and the
forecast keeps the tool's own measurement history in
claude-limits-history.json next to the config (also atomic). Those two are
the only files the tool writes, and only with auto-refresh on / live polling.
In daemon mode the config and the token files are re-read on every cycle, so
a login refreshed by either tool is picked up without a restart.

Forecast (spec docs/plans/01.1 §2.7): with 30+ minutes of history the bar
grows a shaded ghost -- the percent expected AT THE RESET at the current
rate -- and a second line says the outcome: "-> 31% at reset" (lasts) or
"ends Tue ~12:30 (2d 17h)" (runs out first). The rate uses working hours
from [forecast] in the config (session windows count calendar time). Offline
mode disables the forecast so the phase-1 differential stays deterministic.

Kimi Code logins are reported too, after the Claude ones. Their accounts are
queried against the same /usages endpoint the CLI's /usage command uses
(api.kimi.com/coding/v1). Their access token lives 15 minutes; when it is
stale and auto-refresh is on, the tool renews it itself (OAuth refresh_token
grant against auth.kimi.com, credentials file rewritten atomically -- see
"Token lifetime" in the README). With auto-refresh off, an expired login is
reported with advice to start Kimi Code under that profile.
"""

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
import pathlib
from pathlib import Path

import refresh_token   # peer module, same directory

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
KIMI_USAGE_URL = "https://api.kimi.com/coding/v1/usages"
KIMI_OAUTH_URL = "https://auth.kimi.com/api/oauth/token"
KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"   # public client_id of the Kimi Code CLI
DEFAULT_INTERVAL = 300
MIN_INTERVAL = 60
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "claude-limits.toml"

KIMI_LIMIT_NAMES = [("limit_5h", "5h limit"), ("limit_7d", "weekly limit"),
                    ("limit_month_total", "month limit"), ("limit_month_code", "month limit (code)")]
DEFAULT_THRESHOLDS = (70, 90)   # the fill's: configurable via [thresholds]

# ---------------------------------------------------------------- accounts --

def identity_file(cfg_dir):
    """`.claude.json` inside the dir and beside it, the FRESHEST first.

    Both can exist when a config dir was re-logged under a different account:
    the file Claude Code wrote last (latest `profileFetchedAt`) is the one its
    current token belongs to -- picking by position alone labels the directory
    with a stale identity (seen 2026-09-23: a wsl dir holding Sofia García's
    file inside and Mohamed Benali's fresher file beside; the token followed
    the fresher one)."""
    cands = []
    for p in (cfg_dir / ".claude.json", cfg_dir.parent / ".claude.json"):
        if not p.is_file():
            continue
        try:
            acc = json.loads(p.read_text(encoding="utf-8")).get("oauthAccount") or {}
        except (json.JSONDecodeError, OSError):
            continue
        cands.append((acc.get("profileFetchedAt") or 0, p, acc))
    cands.sort(key=lambda c: -c[0])
    return cands


def env_dirs():
    dirs = [Path.home() / ".claude"]
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        dirs.append(Path(env))
    kimi_home = os.environ.get("KIMI_CODE_HOME")
    dirs.append(Path(kimi_home).expanduser() if kimi_home else Path.home() / ".kimi-code")
    return dirs


def children_of(parent):
    parent = Path(parent).expanduser()
    if not parent.is_dir():
        return []
    return [d for d in sorted(parent.iterdir()) if d.is_dir()]


def dedupe(entries):
    """(dir, kind) pairs, first kind wins, deduped by resolved path."""
    seen, out = set(), []
    for d, kind in entries:
        d = Path(d).expanduser()
        key = str(d.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append((d, kind))
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
    """One directory -> dict(dir, email, name, org, token, expired), or None without a login."""
    creds_file = cfg_dir / ".credentials.json"
    if not creds_file.is_file():
        return None
    creds = json.loads(creds_file.read_text(encoding="utf-8")).get("claudeAiOauth") or {}
    token = creds.get("accessToken")
    if not token:
        return None
    email = name = org = None
    candidates = identity_file(cfg_dir)
    if candidates:
        _fetched, _path, acc = candidates[0]
        email, name, org = acc.get("emailAddress"), acc.get("fullName") or acc.get("displayName"), acc.get("organizationName")
    expires_ms = creds.get("expiresAt") or 0
    return {
        "dir": cfg_dir,
        "email": email,
        "name": name,
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
        g = groups.setdefault(key, {"email": login["email"], "name": login["name"], "org": login["org"],
                                    "dirs": [], "expired_dirs": [], "expired_paths": [],
                                    "token": None})
        g["dirs"].append(short_name(cfg_dir))
        if login["expired"]:
            g["expired_dirs"].append(short_name(cfg_dir))
            # The path as well as the name: `short_name` is for reading, and the
            # refresher needs a directory it can actually start Claude Code in.
            g["expired_paths"].append(cfg_dir)
        elif g["token"] is None:
            g["token"] = login["token"]
    for g in groups.values():
        who = f"{g['email']} ({g['org'] or '-'})" if g["email"] else "unknown account"
        if g["name"]:
            # the provider may re-bind identities to pools (seen 2026-09-23:
            # a niceaiservice directory answering Mohamed Benali) -- the name
            # makes the mismatch visible right in the label
            who = f"{g['email']} ({g['name']}, {g['org'] or '-'})"
        g["label"] = f"{who}  [{', '.join(g['dirs'])}]"
    return list(groups.values())


# -------------------------------------------------------------- kimi code --

def kimi_login_of(f, home_label=None):
    """One credentials file -> login dict, or None without a usable token."""
    try:
        creds = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    token = creds.get("access_token")
    if not token:
        return None
    label = f"Kimi Code ({f.stem})"
    if home_label:
        label += f"  [{home_label}]"
    expires_at = creds.get("expires_at") or 0
    return {"name": f.stem, "label": label, "path": f,
            "token": token, "refresh": creds.get("refresh_token"),
            "expired": expires_at < time.time()}


def kimi_logins_of(dirs):
    """Kimi Code logins found in dirs, detected BY CONTENT: a dir is a Kimi
    home when its credentials/*.json files hold access tokens (the mcp/
    subdir holds MCP-server tokens, not logins). One account per file."""
    out = []
    multi = len(dirs) > 1
    for d in dirs:
        cred_dir = d / "credentials"
        if not cred_dir.is_dir():
            continue
        for f in sorted(cred_dir.glob("*.json")):
            login = kimi_login_of(f, short_name(d) if multi else None)
            if login:
                out.append(login)
    return out


def refresh_kimi_token(refresh_token, timeout=30):
    """The OAuth refresh_token grant, the same call the Kimi Code CLI makes.
    Returns the raw token response; raises on HTTP and network errors."""
    body = urllib.parse.urlencode({
        "client_id": KIMI_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    req = urllib.request.Request(
        KIMI_OAUTH_URL, data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def write_kimi_credentials(path, fresh):
    """Rewrites a credentials file with the refreshed token, atomically
    (tmp + os.replace) and preserving every other field. The Kimi Code CLI
    writes with the same discipline, so a racing writer cannot tear the file.

    Unlike Claude Code, there is no separate binary to make do the writing:
    the Kimi CLI is not necessarily installed where this tool runs, so the
    refresh grant is called directly. This is the one file the tool writes."""
    path = Path(path)
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        old = {}
    try:
        expires_in = int(fresh["expires_in"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("refresh response missing expires_in")
    data = dict(old)
    data.update({
        "access_token": fresh["access_token"],
        "refresh_token": fresh.get("refresh_token") or old.get("refresh_token"),
        "expires_in": expires_in,
        "expires_at": int(time.time()) + expires_in,
    })
    for key in ("scope", "token_type"):
        if fresh.get(key):
            data[key] = fresh[key]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass                        # Windows: no POSIX mode
    os.replace(tmp, path)


class KimiRefresher:
    """Auto-refresh for Kimi logins: one refresh grant per expired login,
    with an in-memory cooldown so a login that cannot be renewed (revoked,
    logged out) is not retried every cycle. Cooldown in memory only, same
    trade-off as refresh_token.Refresher."""

    # How long to wait for a racing writer before believing a rejection: the
    # Kimi desktop app/CLI refreshes the same file and writes its new token a
    # moment after the server rotated it, so the file can still look unchanged
    # right after our grant failed the rotation race.
    RACE_WINDOW_SEC = 8

    def __init__(self, timeout=30, cooldown=3600):
        self.timeout = timeout
        self.cooldown = cooldown
        self._last = {}
        self._note = {}          # key -> (attempt epoch, reason) for the report

    def note(self, login):
        """(attempt time, reason) of the last failed attempt, or None."""
        return self._note.get(str(login["path"]).lower())

    def run(self, login, report):
        """Attempts the refresh; reports one line; returns the re-read login
        on success, else None.

        The cooldown runs from the last FAILURE, not the last attempt: a
        successful refresh proves the login is renewable, so the next expiry
        (15 minutes later) must be allowed a fresh try immediately.

        A 400/401 is not automatically "log in again": the Kimi desktop app
        or CLI refreshes the same file and the server ROTATES the refresh
        token on every grant, so a racer that loses the race gets
        invalid_grant on a perfectly healthy login. When the file on disk now
        holds a DIFFERENT token than the one we tried, the race is what
        happened -- take the file as authoritative. A rejection with the file
        UNCHANGED gets a second look after RACE_WINDOW_SEC for the case
        where the winner has not written yet."""
        key = str(login["path"]).lower()
        if time.time() - self._last.get(key, 0) < self.cooldown:
            when, reason = self._note.get(key, (0, "cooldown running"))
            retry = datetime.fromtimestamp(self._last[key] + self.cooldown).strftime("%H:%M")
            report(f"  auto-refresh {login['name']}: waiting for cooldown, next attempt {retry}"
                   f" (last: {reason})")
            return None
        self._note.pop(key, None)
        if not login.get("refresh"):
            reason = "no refresh_token on disk"
            self._fail(key, reason)
            report(f"  auto-refresh {login['name']}: failed -- {reason}; log in again")
            return None
        tried = login["refresh"]

        def rotated_elsewhere():
            """The file now holds a different token: another Kimi tool won the
            rotation race. Adopt its file -- no cooldown, the login is fine."""
            current = kimi_login_of(login["path"])
            if current and current.get("refresh") and current["refresh"] != tried:
                report(f"  auto-refresh {login['name']}: token rotated by another Kimi tool; "
                       f"using its file")
                self._last.pop(key, None)
                return current
            return None

        try:
            fresh = refresh_kimi_token(tried, self.timeout)
            write_kimi_credentials(login["path"], fresh)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace").strip().replace("\n", " ")
            if e.code in (400, 401, 403) or "invalid_grant" in body:
                winner = rotated_elsewhere()
                if winner:
                    return winner
                # the winner may simply not have written yet -- wait for it
                time.sleep(self.RACE_WINDOW_SEC)
                winner = rotated_elsewhere()
                if winner:
                    return winner
                reason = "refresh token rejected"
                self._fail(key, reason)
                report(f"  auto-refresh {login['name']}: failed -- {reason}; log in again")
            else:
                reason = f"HTTP {e.code}: {body[:120]}"
                self._fail(key, reason)
                report(f"  auto-refresh {login['name']}: failed -- {reason}")
            return None
        except (OSError, ValueError, KeyError) as e:
            reason = str(e)
            self._fail(key, reason)
            report(f"  auto-refresh {login['name']}: failed -- {reason}")
            return None
        self._last.pop(key, None)
        report(f"  auto-refresh {login['name']}: refreshed")
        return kimi_login_of(login["path"]) or login

    def _fail(self, key, reason):
        """Record a failure: the cooldown and the skip-message reason start here."""
        self._last[key] = time.time()
        self._note[key] = (self._last[key], reason)


def fetch_kimi_usage(token):
    req = urllib.request.Request(
        KIMI_USAGE_URL,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def kimi_rows_of(usage):
    """One row per quota window the backend served; windows it omitted are
    skipped (new plans have no weekly window). Each row: (kind, percent,
    severity, reset label, reset epoch or None) -- the epoch feeds the forecast.

    The live 5h figure comes from `limits[]` (used/limit counts): the web
    console's 5h percentage tracks it, while `usages.limit_5h.used_ratio`
    can sit at 0 (seen 2026-09-21). The monthly rows only exist in `usages`."""
    seen_windows = set()
    for lim in usage.get("limits") or []:
        window = lim.get("window") or {}
        detail = lim.get("detail") or {}
        try:
            used, limit = float(detail["used"]), float(detail["limit"])
        except (KeyError, TypeError, ValueError):
            continue
        duration = window.get("duration")
        if window.get("timeUnit") == "TIME_UNIT_MINUTE" and isinstance(duration, (int, float)):
            name = f"{duration / 60:g}h limit" if duration % 60 == 0 else f"{duration:g}min limit"
        else:
            name = "rate limit"
        seen_windows.add(name)
        pct = used / limit * 100 if limit > 0 else None
        yield name, pct, None, local_time(detail.get("resetTime")), iso_epoch(detail.get("resetTime"))
    usages = usage.get("usages") or {}
    for key, name in KIMI_LIMIT_NAMES:
        if name in seen_windows:
            continue
        entry = usages.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("used_ratio"), (int, float)):
            continue
        pct = float(entry["used_ratio"]) * 100
        yield name, pct, None, local_time(entry.get("reset_time")), iso_epoch(entry.get("reset_time"))


def kimi_extra_usage_line(usage):
    """The Extra Usage (booster) wallet, when enabled: balance + monthly cap."""
    raw = usage.get("boosterWallet")
    if not isinstance(raw, dict):
        return None
    balance = raw.get("balance")
    if not isinstance(balance, dict) or balance.get("type") != "BOOSTER":
        return None

    def cents(value):
        try:
            cents = float(value) / 1_000_000
        except (TypeError, ValueError):
            return 0
        if 0 < cents < 1:
            return 1
        return round(cents)

    def money(field):
        m = raw.get(field)
        if not isinstance(m, dict):
            return None, ""
        return cents(m.get("priceInCents")), m.get("currency") or ""

    balance_cents = cents(balance.get("amountLeft"))
    limit_cents, currency = money("monthlyChargeLimit")
    if not currency:
        _, currency = money("monthlyUsed")
    currency = currency or "USD"
    line = f"extra usage balance: {balance_cents / 100:.2f} {currency}"
    if raw.get("monthlyChargeLimitEnabled") is True:
        line += f" (monthly cap {limit_cents / 100:.2f} {currency})"
    return line


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


LOGIN_KINDS = ("auto", "claude", "kimi")


def kinded(items):
    """Config entries -> (path, kind, children) triples. Every entry MUST be
    a table { dir = ..., kind = "auto"|"claude"|"kimi" }: a bare path is
    rejected so the kind of login is always a conscious choice, never
    guessed. children = true stands for every child directory of dir, each
    child keeping the entry's kind."""
    out = []
    for item in items:
        if isinstance(item, str):
            sys.exit(f"accounts entry {item!r} is a bare path; give it a kind: "
                     "{ dir = \"...\", kind = \"auto\"|\"claude\"|\"kimi\" }")
        if isinstance(item, dict) and isinstance(item.get("dir"), str):
            kind = item.get("kind")
            if kind is None:
                sys.exit(f"accounts entry for {item['dir']!r} has no kind; use "
                         "{ dir = \"...\", kind = \"auto\"|\"claude\"|\"kimi\" }")
            if kind not in LOGIN_KINDS:
                sys.exit(f"unknown kind {kind!r} for {item['dir']!r} in the config; "
                         f"use one of: {', '.join(LOGIN_KINDS)}")
            children = item.get("children", False)
            if not isinstance(children, bool):
                sys.exit(f"'children' for {item['dir']!r} must be true or false")
            out.append((item["dir"], kind, children))
        else:
            sys.exit(f"cannot read accounts entry {item!r}; use "
                     "{ dir = \"...\", kind = \"auto\"|\"claude\"|\"kimi\" }")
    return out


def dirs_from(args, config):
    """(dir, kind) pairs from the command line or the config file."""
    if args.parent:
        return dedupe((d, "auto") for d in children_of(args.parent))
    if args.dirs:
        return dedupe((d, "auto") for d in args.dirs)
    entries = []
    for path, kind, children in kinded(config.get("accounts") or []):
        entries += [(d, kind) for d in children_of(path)] if children else [(path, kind)]
    if not entries:
        entries = [(d, "auto") for d in env_dirs()]
    return dedupe(entries)


# ------------------------------------------------------------------- usage --

def fetch_usage(token):
    req = urllib.request.Request(
        USAGE_URL,
        headers={"Authorization": "Bearer " + token, "anthropic-beta": BETA_HEADER},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def duration_of(secs):
    """Time left in the widget's own shape: 2d 18h / 1h 52min / 7min."""
    secs = int(secs)
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


def remaining(iso):
    """Time left until the reset, in the widget's own shape."""
    left = datetime.fromisoformat(iso) - datetime.now(timezone.utc)
    return duration_of(left.total_seconds())


def forecast_suffix(fr, paint):
    """Строка 2 из спеки 01.1 §2.4: «→ 31% at reset» (dim) when the limit
    lasts; «→ 104% at reset, ends Tue ~12:30 (2d 17h)» when it does not --
    the overshoot percent plus the moment and time until exhaustion (amber)."""
    pct_at_reset, runs_out, rate_h, span_min = fr
    head = paint.empty(f"→ {pct_at_reset:.0f}% at reset")
    if runs_out is None:
        return head
    when = datetime.fromtimestamp(runs_out).astimezone()
    today = datetime.now().astimezone().date()
    if runs_out <= time.time():
        # the projection says exhaustion has ALREADY happened: no tilde, no
        # "time until" -- those are for the future; the moment is a fact
        day = "" if when.date() == today else when.strftime("%Y-%m-%d ")
        return head + ", " + paint.fill(f"ends {day}{when:%H:%M} (now)", "warning")
    day = "" if when.date() == today else when.strftime("%Y-%m-%d ")
    tail = paint.fill(f"ends {day}~{when:%H:%M} ({duration_of(runs_out - time.time())})", "warning")
    return head + ", " + tail


def print_limit_row(kind, pct, sev, reset_label, fr, paint, bar_style,
                    ghost_thresholds=(80, 95), thresholds=DEFAULT_THRESHOLDS):
    """One limit row; `fr` is a forecast tuple or None. The ghost shade of the
    bar runs from percent to percent_at_reset (spec 01.1 §2.2) and takes the
    ghost thresholds' colour (its own [forecast] warning/critical, not the
    fill's); the second line under the bar is the forecast per spec §2.4."""
    ghost, ghost_sev, suffix = None, None, ""
    if fr is not None:
        if fr[0] > pct:
            ghost = fr[0]
            ghost_sev = ghost_severity_of(min(fr[0], 100), *ghost_thresholds)
        # a zero row projecting zero is noise, not information; any other
        # flat forecast still prints its "-> N% at reset" per spec §2.7
        if fr[0] != pct or pct:
            suffix = "\n" + " " * 24 + forecast_suffix(fr, paint)
    pct_s = "-" if pct is None else f"{pct:>3.0f}%"
    sev_label = sev if sev in ("normal", "warning", "critical") else severity_of(sev, pct, thresholds)
    print(f"  {kind:<22} {bar_of(pct, sev, bar_style, paint, ghost, ghost_sev, thresholds)} {pct_s:>4}  "
          f"{sev_label:<8} resets {reset_label}" + suffix)


def print_stale_rows(stored, paint, bar_style):
    """The last good snapshot, dimmed, with its age -- shown when this cycle's
    request failed (429, network). Spec 01.1 §3.3: unknown shows the last good
    data, not nothing."""
    when, rows = stored
    age = duration_of(time.time() - when)
    stamp = datetime.fromtimestamp(when).strftime("%H:%M:%S")
    print(f"  last good data {stamp} ({age} ago):")
    for kind, pct, sev_label, reset_label in rows:
        pct_s = "-" if pct is None else f"{pct:>3.0f}%"
        bar = bar_of(pct, None, bar_style, Paint(False))
        print("  " + paint.empty(f"{kind:<22} {bar} {pct_s:>4}  {sev_label:<8} resets {reset_label}"))


def local_time(iso):
    if not iso:
        return "-"
    when = datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    return f"{when} ({remaining(iso)})"


def rows_of(usage):
    """One row per limit window; falls back to the two fixed windows. Each
    row: (kind, percent, severity, reset label, reset epoch or None)."""
    limits = usage.get("limits")
    if limits:
        for lim in limits:
            scope = (lim.get("scope") or {}).get("model") or {}
            kind = lim.get("kind", "?")
            if scope.get("display_name"):
                kind += ":" + scope["display_name"]
            yield (kind, lim.get("percent"), lim.get("severity", "-"),
                   local_time(lim.get("resets_at")), iso_epoch(lim.get("resets_at")))
        return
    for kind in ("five_hour", "seven_day"):
        w = usage.get(kind) or {}
        yield (kind, w.get("utilization"), w.get("locked_reason") or "-",
               local_time(w.get("resets_at")), iso_epoch(w.get("resets_at")))


def iso_epoch(iso):
    """Epoch seconds for an ISO-8601 moment with offset, or None."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


# ----------------------------------------------------------------- forecast --

HISTORY_DAYS = 7          # retention; the forecast needs at most 3 working days
HISTORY_BACKUPS_KEPT = 7  # daily copies kept alongside the live file
HISTORY_MIN_SPAN = 1800   # < 30 min of history -> forecast unavailable (spec 01.1 §2.7)

WORK_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def history_path_of(config_path):
    """The reference tool's own data: measurement history for the forecast.
    Lives next to the config file; the login directories are never touched."""
    return Path(config_path).with_name("claude-limits-history.json")


def sample_epoch(mark):
    """A sample's timestamp as epoch seconds: int/float (the old format) or a
    human-readable local ISO string (the format written since 2026-09-21)."""
    if isinstance(mark, (int, float)):
        return float(mark)
    try:
        return datetime.fromisoformat(str(mark)).timestamp()
    except ValueError:
        return None


def load_history(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_history(path, history, now):
    """Prune to HISTORY_DAYS and write atomically (tmp + replace) -- the same
    discipline as the Kimi credentials write."""
    cutoff = now - HISTORY_DAYS * 86400
    for key in list(history):
        pts = [p for p in history[key]
               if isinstance(p, list) and len(p) == 2 and isinstance(sample_epoch(p[0]), float)
               and cutoff <= sample_epoch(p[0]) <= now]
        if pts:
            history[key] = pts
        else:
            del history[key]
    tmp = Path(path).with_name(Path(path).name + ".tmp")
    tmp.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def backup_history(path, now):
    """A backup, not a rotation: the live file stays, and once a day it is
    copied to history-YYYYMMDD.json next to it, keeping the newest
    HISTORY_BACKUPS_KEPT copies. The history prunes itself to 7 days on every
    write, so a week of daily copies is a full backup horizon at a constant
    size -- the data never grows without bound."""
    path = Path(path)
    if not path.is_file():
        return
    stamp = datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%d")
    dest = path.with_name(f"{path.stem}-{stamp}{path.suffix}")
    if dest.exists():
        return                                  # today's copy already taken
    shutil.copy2(path, dest)
    backups = sorted(path.parent.glob(f"{path.stem}-????????{path.suffix}"))
    for old in backups[:-HISTORY_BACKUPS_KEPT]:
        try:
            old.unlink()
        except OSError:
            pass


def ghost_severity_of(pct, warning, critical):
    """The ghost's own thresholds, configurable via [forecast] warning/critical
    (default 80/95, owner word 2026-09-22): a projection below `warning` stays
    green -- the fill's stricter 70/90 is about NOW, the ghost is about LATER."""
    return "critical" if pct >= critical else "warning" if pct >= warning else "normal"


def forecast_config_of(config):
    """[forecast] table per spec 01.1 §5.3: enabled, working_hours, work_days,
    work_from, work_to, off_hours_rate, rate_window_days, warning, critical.
    Defaults match the spec."""
    raw = config.get("forecast")
    if not isinstance(raw, dict):
        raw = {}
    days = raw.get("work_days", ["mon", "tue", "wed", "thu", "fri"])
    if not isinstance(days, list):
        days = []
    def hhmm(value, default):
        try:
            h, m = str(value).split(":")
            return int(h) * 60 + int(m)
        except (ValueError, TypeError):
            return default
    def threshold(key, default):
        try:
            v = int(raw.get(key, default))
            return v if 0 < v <= 100 else default
        except (TypeError, ValueError):
            return default
    warning = threshold("warning", 80)
    critical = threshold("critical", 95)
    if warning >= critical:
        warning, critical = 80, 95
    try:
        off = min(max(int(raw.get("off_hours_rate", 0)), 0), 100)
    except (TypeError, ValueError):
        off = 0
    try:
        rate_window_days = max(int(raw.get("rate_window_days", 3)), 1)
    except (TypeError, ValueError):
        rate_window_days = 3
    return {
        "enabled": raw.get("enabled", True) is not False,
        "days": {d for d in days if d in WORK_DAY_NAMES},
        "from_min": hhmm(raw.get("work_from", "09:00"), 9 * 60),
        "to_min": hhmm(raw.get("work_to", "19:00"), 19 * 60),
        "off": off / 100,
        "rate_window_days": rate_window_days,
        # the schedule is optional and OFF by default (owner 2026-09-21):
        # without it every minute weighs 1 and windows count calendar time
        "working_hours": bool(raw.get("working_hours", False)),
        "warning": warning,
        "critical": critical,
    }


def schedule_weight(sched, epoch):
    """1.0 inside working hours, off_hours_rate outside. Session windows are
    calendar-based and never call this."""
    dt = datetime.fromtimestamp(epoch).astimezone()
    if WORK_DAY_NAMES[dt.weekday()] not in sched["days"]:
        return sched["off"]
    minutes = dt.hour * 60 + dt.minute
    start, end = sched["from_min"], sched["to_min"]
    inside = (start <= minutes < end) if start <= end else (minutes >= start or minutes < end)
    return 1.0 if inside else sched["off"]


def work_between(sched, t0, t1, calendar=False):
    """Weighted minutes between two epochs per the working schedule; plain
    calendar minutes when `calendar` (session windows) or the schedule is
    switched off ([forecast] working_hours = false, the default)."""
    if t1 <= t0:
        return 0.0
    if calendar or not sched.get("working_hours"):
        return (t1 - t0) / 60
    total, t = 0.0, t0
    while t < t1:
        total += schedule_weight(sched, t)
        t += 60
    return total


def kind_class_of(kind):
    """Which forecast window a row belongs to. The spec 01.1 §2.7 names
    session and weekly; the reference extends the same formula to monthly
    (recorded in 01.1 §2.7 as a 2026-09-21 amendment): rate over
    rate_window_days, extrapolated over the remaining ~30 days -- a rough
    but honest \"will the month last\" reading."""
    k = kind.lower()
    if k.startswith(("session", "5h", "five_hour")):
        return "session"
    if k.startswith(("weekly", "7d", "seven_day")):
        return "weekly"
    if k.startswith(("month", "30d", "limit_month")):
        return "monthly"
    return None


def record_sample(history, series, kind, pct, now):
    """One series per LIMIT ROW (weekly_all and weekly_scoped:Fable are different
    quotas and must not mix); the window class only picks the forecast mode.
    The timestamp is UTC ISO 8601 with Z per docs/conventions/database.md §1 --
    the file is opened by eyes, and one zone keeps moments from drifting."""
    if kind_class_of(kind) is None or pct is None:
        return
    mark = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    history.setdefault(f"{series}|{kind}", []).append([mark, round(float(pct), 4)])


def forecast_of(history, series, kind_class, pct, reset_epoch, now, sched):
    """The spec 01.1 §2.7 formula: rate over the recent window (last 60 min
    for session, last 3 days for weekly, from the reset when it sits inside),
    extrapolated over the REMAINING working time to the reset.

    Returns (percent_at_reset, runs_out_epoch | None, rate_per_hour, sample_min)
    or None when the forecast is unavailable: no reset time, reset already
    past, no samples, or less than 30 minutes of history."""
    if reset_epoch is None or reset_epoch <= now or pct is None:
        return None
    samples = []
    for s in history.get(series) or []:
        if isinstance(s, list) and len(s) == 2:
            ts = sample_epoch(s[0])
            if ts is not None:
                samples.append((ts, s[1]))
    samples = sorted(samples)
    samples = [s for s in samples if s[0] <= now]
    calendar = kind_class == "session"
    window = {"session": 5 * 3600, "weekly": 7 * 86400}.get(kind_class, 30 * 86400)
    limit_start = reset_epoch - window
    rate_start = max(now - (3600 if calendar else sched["rate_window_days"] * 86400), limit_start)
    reset_based = limit_start > rate_start
    if reset_based:
        # the current limit window began inside the rate window: percent
        # counts from the window start (0 right after the reset)
        rate_start = limit_start
    rate_start = int(rate_start)      # sample timestamps are whole seconds
    inside = [s for s in samples if s[0] >= rate_start]
    if not inside:
        return None
    base_pct = 0.0 if reset_based else inside[0][1]
    span = now - inside[0][0]
    if span < HISTORY_MIN_SPAN:
        return None
    used = float(pct) - float(base_pct)
    work = work_between(sched, inside[0][0], now, calendar)
    if work <= 0:
        # The whole sample window sits outside the working schedule (a fresh
        # history recorded in the evening): usage per WORKING minute is
        # undefined, and reporting a flat "-> N% at reset" would be a made-up
        # answer. Unavailable beats wrong.
        return None
    rate = used / work
    if rate <= 0:
        return (float(pct), None, rate * 60, span / 60)
    remaining_work = work_between(sched, now, reset_epoch, calendar)
    percent_at_reset = float(pct) + rate * remaining_work
    runs_out = None
    if percent_at_reset >= 100:
        acc, t = 0.0, now
        plain = calendar or not sched.get("working_hours")
        while t < reset_epoch:
            acc += rate * (1.0 if plain else schedule_weight(sched, t))
            if float(pct) + acc >= 100:
                runs_out = t
                break
            t += 60
    return (percent_at_reset, runs_out, rate * 60, span / 60)


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


def severity_of(sev, pct, thresholds=DEFAULT_THRESHOLDS):
    """The server's word when it gives one; otherwise derived from the percent
    by [thresholds] warning/critical (default 70/90, the product's keys)."""
    if sev in ("normal", "warning", "critical"):
        return sev
    if pct is None:
        return "normal"
    warning, critical = thresholds
    return "critical" if pct >= critical else "warning" if pct >= warning else "normal"


def thresholds_of(config):
    """[thresholds] warning/critical for the FILL's colour; invalid pairs and
    missing sections fall back to 70/90."""
    raw = config.get("thresholds")
    if not isinstance(raw, dict):
        return DEFAULT_THRESHOLDS
    def num(key, default):
        try:
            v = int(raw.get(key, default))
            return v if 0 < v <= 100 else default
        except (TypeError, ValueError):
            return default
    warning, critical = num("warning", 70), num("critical", 90)
    return (warning, critical) if warning < critical else DEFAULT_THRESHOLDS


BAR_GLYPHS = {"blocks": ("█", "░", "▒"), "ascii": ("#", ".", ":")}


def bar_of(pct, sev, style, paint, ghost=None, ghost_sev=None, thresholds=DEFAULT_THRESHOLDS):
    """A 30-cell bar between brackets. 'blocks' -> [████░░░░], 'ascii' -> [####....].
    Filled part coloured green/yellow/red by severity (the [thresholds]
    warning/critical), empty part dim.
    `ghost` (a larger percent) extends the bar with the shade glyph; the ghost
    keeps its own severity colour (ghost_sev) -- by the PROJECTED percent, so
    the bar shows not only where usage is but where it lands and how bad that
    is (spec 01.1 §2.2, owner word 2026-09-22)."""
    full, empty, shade = BAR_GLYPHS.get(style, BAR_GLYPHS["blocks"])
    if pct is None:
        return "[" + paint.empty(empty * BAR_WIDTH) + "]"
    filled = round(min(max(pct, 0), 100) / 100 * BAR_WIDTH)
    ghost_end = round(min(max(ghost, 0), 100) / 100 * BAR_WIDTH) if ghost is not None else filled
    ghost_end = min(max(ghost_end, filled), BAR_WIDTH)
    color = severity_of(sev, pct, thresholds)
    fill = paint.fill(full * filled, color) if filled else ""
    shade_color = severity_of(ghost_sev, ghost, thresholds) if ghost_sev else color
    shade_s = paint.fill(shade * (ghost_end - filled), shade_color) if ghost_end > filled else ""
    return "[" + fill + shade_s + paint.empty(empty * (BAR_WIDTH - ghost_end)) + "]"


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

def offline_usage(acc, offline_dir):
    """A recorded reply instead of a live one: `<offline_dir>/<email>.json`, else
    `<offline_dir>/normal.json`.

    Why this exists: the phase-1 acceptance diffs THIS tool against the Nova build,
    and if both sides called the endpoint, every acceptance run would spend two sets
    of requests on it. That is how this machine earned a 429 on 2026-09-07. Offline
    makes the diff deterministic and free — and it compares FORMATTING, which is what
    the differential is actually about."""
    d = pathlib.Path(offline_dir)
    email = (acc.get("email") or "").lower()
    for candidate in ([d / f"{email}.json"] if email else []) + [d / "normal.json"]:
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no fixture for {email or acc['label']} in {d}")


def last_good_from_history(history, thresholds=DEFAULT_THRESHOLDS):
    """Seed the stale-display from the measurement history: the newest sample
    of each series becomes that account's last good row (resets_at is not
    recorded in history, so the reset column shows '-'). Lets a restarted
    daemon keep showing yesterday's numbers through a 429 storm."""
    rows = {}
    for key, pts in (history or {}).items():
        if not pts:
            continue
        series, _sep, kind = key.rpartition("|")
        ts = sample_epoch(pts[-1][0])
        if not series or ts is None:
            continue
        stamp, acc = rows.setdefault(series, [0, []])
        rows[series][0] = max(stamp, ts)
        acc.append((kind, pts[-1][1], severity_of(None, pts[-1][1], thresholds), "-"))
    return {series: (stamp, acc) for series, (stamp, acc) in rows.items()}


def signature_note(sig, seen):
    """If an identical quota fingerprint was already reported by another live
    account this cycle, name it: same numbers, same reset minutes = one pool
    behind two logins. None otherwise."""
    if not sig:
        return None
    first = seen.get(sig)
    return f"same quota reported for {first} -- shared pool suspected" if first else None


def snapshot(dirs, paint, bar_style, offline_dir=None, refresher=None, kimi_refresher=None,
             history=None, history_path=None, sched=None, thresholds=DEFAULT_THRESHOLDS,
             last_good=None, next_try=None):
    """Prints every account found in dirs. Returns (accounts_found, seconds_to_back_off).

    With `offline_dir` set, no request leaves the machine: replies come from the
    recorded fixtures, and an expired token is still skipped so the two modes agree
    on which accounts are reportable. Offline also skips the forecast: its lines
    depend on wall time, and the differential (plan Ф.1) must stay deterministic.

    With `refresher` set, an expired login is renewed BEFORE the report rather
    than merely complained about, and the accounts are re-read so the numbers
    appear in THIS cycle instead of the next one. Offline excludes it: that mode
    promises no request leaves the machine, and a refresh is a request.

    Live cycles record samples into `history` (keyed per account and window
    class) and, with `sched` set, print the forecast per spec 01.1 §2.7: the
    shaded ghost in the bar and the second line under it. The history is the
    tool's own data, written to `history_path` at the end of the cycle.

    Live cycles also fingerprint every account's rows (kind, percent, reset
    minute). Two accounts reporting the IDENTICAL quota state -- same rows,
    same percents, same reset minutes -- are one pool behind two logins
    (org-level quota): the later one gets a note naming the first.

    `last_good` is the caller's dict series -> (epoch, rows) of the newest
    successful reading per account. On 429/network failure the stale rows are
    printed DIMMED with their age instead of nothing -- spec 01.1 §3.3's
    «unknown shows the last good snapshot» -- so a rate-limit storm does not
    blank the screen; the dict is updated in place on every success.

    `next_try` is the caller's dict series -> epoch of the earliest next
    allowed request. The server throttles per ACCOUNT, so one throttled login
    must not stretch the daemon's whole cycle: gating is per account and the
    loop keeps its interval for the healthy ones. A fresh 429 sets the gate
    from Retry-After; while gated, the account is skipped (stale rows shown)
    without a request."""
    now = time.time()
    claude_dirs = [d for d, kind in dirs if kind in ("auto", "claude")]
    kimi_dirs = [d for d, kind in dirs if kind in ("auto", "kimi")]
    accounts = accounts_of(claude_dirs)
    seen_signatures = {}
    if refresher is not None and not offline_dir:
        targets = refresher.targets(accounts)
        if next_try is not None:
            # refreshing spawns Claude Code, whose own calls land in the same
            # throttled pool: during a 429 gate the spawn only feeds the storm
            targets = [t for a in accounts
                       for t in ([t for t in targets if t in (a.get("expired_paths") or [])]
                                 if now >= next_try.get("claude:" + (a["email"] or a["label"]), 0)
                                 else [])]
        if targets:
            print("")
            refresher.run(targets, print)
            accounts = accounts_of(claude_dirs)   # a renewed login is live NOW
    backoff = 0
    for acc in accounts:
        expired_note = (f"  ({', '.join(acc['expired_dirs'])}: token expired on disk)"
                        if acc["expired_dirs"] and acc["token"] else None)
        series = "claude:" + (acc["email"] or acc["label"])
        if acc["token"] is None:
            # No request with a dead token: the server answers 401, then 429 on
            # repeats. Only Claude Code refreshes it (README, Token lifetime).
            print("\n" + paint.dead(acc["label"]))
            if refresher is None or offline_dir:
                print("  token expired on disk: start Claude Code under this directory to refresh it")
            else:
                # Auto-refresh ran above and the token is still dead, so saying
                # "start Claude Code" would be advice the reader has just watched
                # fail. What is left is a login that needs a human.
                print(f"  token expired on disk and auto-refresh did not renew it: "
                      f"log in again under {', '.join(acc['expired_dirs'])}")
            continue
        if offline_dir:
            try:
                usage = offline_usage(acc, offline_dir)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print("\n" + paint.unknown(acc["label"]))
                print(f"  offline: {e}")
                continue
            print("\n" + paint.live(acc["label"]))
            if expired_note:
                print(expired_note)
            for kind, pct, sev, reset, _reset_epoch in rows_of(usage):
                print_limit_row(kind, pct, sev, reset, None, paint, bar_style)
            continue
        if next_try is not None and now < next_try.get(series, 0):
            left = int(next_try[series] - now)
            print("\n" + paint.unknown(acc["label"]))
            if expired_note:
                print(expired_note)
            print(f"  still throttled by the server; next try in {left // 60} min {left % 60} s")
            if last_good is not None and series in last_good:
                print_stale_rows(last_good[series], paint, bar_style)
            continue
        try:
            usage = fetch_usage(acc["token"])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = retry_after_of(e)
                backoff = max(backoff, wait or MIN_INTERVAL)
                if next_try is not None:
                    next_try[series] = now + (wait or MIN_INTERVAL)
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
            if last_good is not None and series in last_good:
                print_stale_rows(last_good[series], paint, bar_style)
            continue
        except OSError as e:
            print("\n" + paint.unknown(acc["label"]))
            if expired_note:
                print(expired_note)
            print(f"  network error: {e}")
            if last_good is not None and series in last_good:
                print_stale_rows(last_good[series], paint, bar_style)
            continue
        print("\n" + paint.live(acc["label"]))
        if expired_note:
            print(expired_note)
        good_rows = []
        sig = []
        for kind, pct, sev, reset, reset_epoch in rows_of(usage):
            if history is not None:
                record_sample(history, series, kind, pct, now)
            cls = kind_class_of(kind)
            fr = (forecast_of(history, f"{series}|{kind}", cls, pct, reset_epoch, now, sched)
                  if history is not None and sched and sched["enabled"] and cls else None)
            print_limit_row(kind, pct, sev, reset, fr, paint, bar_style,
                          (sched["warning"], sched["critical"]) if sched else (80, 95),
                          thresholds=thresholds)
            sev_label = sev if sev in ("normal", "warning", "critical") else severity_of(sev, pct, thresholds)
            good_rows.append((kind, pct, sev_label, reset))
            sig.append((kind, round(pct, 1) if pct is not None else None,
                        int(reset_epoch // 60) if reset_epoch else None))
        if last_good is not None:
            last_good[series] = (now, good_rows)
        note = signature_note(tuple(sig), seen_signatures)
        if note:
            print("  " + note)
        else:
            seen_signatures[tuple(sig)] = acc["label"]
    kimi_found = kimi_backoff = 0
    for login in kimi_logins_of(kimi_dirs):
        kimi_found += 1
        if login["expired"] and kimi_refresher is not None and not offline_dir:
            print("")                                # the auto-refresh line is
            login = kimi_refresher.run(login, print) or login   # kimi's, not the
        if login["expired"]:                         # claude account's above
            print("\n" + paint.dead(login["label"]))
            if kimi_refresher is None or offline_dir:
                print("  access token expired on disk: start Kimi Code under this profile to refresh it")
            else:
                print("  access token expired on disk and auto-refresh did not renew it: "
                      "log in again under this profile")
            continue
        if offline_dir:
            fixture = Path(offline_dir) / f"kimi-{login['name']}.json"
            if not fixture.is_file():
                fixture = Path(offline_dir) / "kimi.json"
            try:
                usage = json.loads(fixture.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print("\n" + paint.unknown(login["label"]))
                print(f"  offline: {e}")
                continue
            print("\n" + paint.live(login["label"]))
            for kind, pct, sev, reset, _reset_epoch in kimi_rows_of(usage):
                print_limit_row(kind, pct, sev, reset, None, paint, bar_style)
            extra = kimi_extra_usage_line(usage)
            if extra:
                print(f"  {extra}")
            continue
        if next_try is not None and now < next_try.get(f"kimi:{login['name']}", 0):
            left = int(next_try[f"kimi:{login['name']}"] - now)
            print("\n" + paint.unknown(login["label"]))
            print(f"  still throttled by the server; next try in {left // 60} min {left % 60} s")
            if last_good is not None and f"kimi:{login['name']}" in last_good:
                print_stale_rows(last_good[f"kimi:{login['name']}"], paint, bar_style)
            continue
        try:
            usage = fetch_kimi_usage(login["token"])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = retry_after_of(e)
                kimi_backoff = max(kimi_backoff, wait or MIN_INTERVAL)
                if next_try is not None:
                    next_try[f"kimi:{login['name']}"] = now + (wait or MIN_INTERVAL)
                asked = f"server asks to wait {wait} s" if wait else "no Retry-After given"
                head, msg = paint.unknown(login["label"]), f"HTTP 429: too many requests; {asked}"
            elif e.code == 401:
                head, msg = paint.dead(login["label"]), "HTTP 401: token rejected"
            else:
                body = e.read().decode("utf-8", "replace").strip().replace("\n", " ")
                head, msg = paint.unknown(login["label"]), f"HTTP {e.code}: {body[:160]}"
            print("\n" + head)
            print("  " + msg)
            if last_good is not None and f"kimi:{login['name']}" in last_good:
                print_stale_rows(last_good[f"kimi:{login['name']}"], paint, bar_style)
            continue
        except OSError as e:
            print("\n" + paint.unknown(login["label"]))
            print(f"  network error: {e}")
            if last_good is not None and f"kimi:{login['name']}" in last_good:
                print_stale_rows(last_good[f"kimi:{login['name']}"], paint, bar_style)
            continue
        print("\n" + paint.live(login["label"]))
        series = "kimi:" + login["name"]
        good_rows = []
        sig = []
        for kind, pct, sev, reset, reset_epoch in kimi_rows_of(usage):
            if history is not None:
                record_sample(history, series, kind, pct, now)
            cls = kind_class_of(kind)
            fr = (forecast_of(history, f"{series}|{kind}", cls, pct, reset_epoch, now, sched)
                  if history is not None and sched and sched["enabled"] and cls else None)
            print_limit_row(kind, pct, sev, reset, fr, paint, bar_style,
                          (sched["warning"], sched["critical"]) if sched else (80, 95),
                          thresholds=thresholds)
            good_rows.append((kind, pct, severity_of(sev, pct, thresholds), reset))
            sig.append((kind, round(pct, 1) if pct is not None else None,
                        int(reset_epoch // 60) if reset_epoch else None))
        if last_good is not None:
            last_good[series] = (now, good_rows)
        extra = kimi_extra_usage_line(usage)
        if extra:
            print(f"  {extra}")
        note = signature_note(tuple(sig), seen_signatures)
        if note:
            print("  " + note)
        else:
            seen_signatures[tuple(sig)] = login["label"]
    if history is not None and history_path and not offline_dir:
        backup_history(history_path, now)
        save_history(history_path, history, now)
    if not accounts and not kimi_found:
        print("\nno Claude Code or Kimi Code logins found in:",
              ", ".join(str(d) for d, _ in dirs))
    # With per-account gating the throttled login sleeps in next_try, not in
    # the loop's interval -- a fresh 429 no longer stretches everyone else's
    # cycle. Without gating (one-shot), the server-asked backoff is returned.
    return len(accounts) + kimi_found, (0 if next_try is not None
                                        else max(backoff, kimi_backoff))


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
    p.add_argument("--offline", metavar="DIR",
                   help="read recorded replies from DIR instead of calling the endpoint "
                        "(fixtures/usage); makes the differential deterministic and free")
    p.add_argument("--no-auto-refresh", action="store_true",
                   help="do not renew an expired login; just report it (also 'auto_refresh' in the config). "
                        "A refresh costs one small request on that account's own limits. Claude: Claude Code "
                        "is started and rewrites its own token; Kimi: the OAuth refresh grant is called and "
                        "the credentials file rewritten")
    p.add_argument("--refresh-all-expired", action="store_true",
                   help="renew every expired directory, not only the ones that block a reading "
                        "(also 'refresh_all_expired' in the config)")
    p.add_argument("--refresh-claude-model", metavar="ID",
                   help=f"model for the Claude throwaway refresh request only (default: "
                        f"{refresh_token.DEFAULT_MODEL}); Kimi renews by an OAuth grant and "
                        f"spends no quota, so no model applies")
    p.add_argument("--refresh-timeout", type=int, metavar="SEC",
                   help=f"limit per refresh (default: {refresh_token.DEFAULT_TIMEOUT})")
    p.add_argument("--refresh-cooldown", type=int, metavar="SEC",
                   help=f"floor between two attempts on ONE directory (default: {refresh_token.DEFAULT_COOLDOWN}); "
                        "a login that cannot be renewed would otherwise cost a request every cycle")
    p.add_argument("--bar-style", choices=["blocks", "ascii"],
                   help="progress bar glyphs: ascii [####....] (default) or blocks [████░░░░] "
                        "for fonts that have the block glyphs; also 'bar_style' in the config")
    return p.parse_args(argv)


def refresher_of(args, config):
    """The auto-refresher, or None when it is switched off.

    The flag wins over the config, and the config over the default, so a daemon
    can be started once with `--no-auto-refresh` without editing anything."""
    if args.no_auto_refresh or not config.get("auto_refresh", True):
        return None
    return refresh_token.Refresher(
        model=args.refresh_claude_model or config.get("refresh_claude_model") or refresh_token.DEFAULT_MODEL,
        timeout=args.refresh_timeout or config.get("refresh_timeout_sec") or refresh_token.DEFAULT_TIMEOUT,
        cooldown=args.refresh_cooldown or config.get("refresh_cooldown_sec") or refresh_token.DEFAULT_COOLDOWN,
        all_expired=args.refresh_all_expired or bool(config.get("refresh_all_expired")),
    )


def kimi_refresher_of(args, config):
    """The Kimi auto-refresher, or None when auto-refresh is switched off.
    Shares the Claude refresher's gate and knobs: refresh_timeout_sec and
    refresh_cooldown_sec apply to both."""
    if args.no_auto_refresh or not config.get("auto_refresh", True):
        return None
    return KimiRefresher(
        timeout=args.refresh_timeout or config.get("refresh_timeout_sec") or 30,
        cooldown=args.refresh_cooldown or config.get("refresh_cooldown_sec") or 3600,
    )


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
    # An organisation name outside the console code page must never crash the
    # daemon -- or --help, which prints before anything else runs.
    sys.stdout.reconfigure(errors="replace")
    args = parse_args(argv)
    config = load_config(args.config)
    paint = Paint(colours_enabled(args.color))
    refresher = refresher_of(args, config)
    kimi_refresher = kimi_refresher_of(args, config)
    hist_path = history_path_of(args.config)
    last_good = {}                                   # survives across daemon cycles:
    next_try = {}                                    # per-account server gates:
    if not args.daemon:                              # the last reading per account,
        sched = None if args.offline else forecast_config_of(config)   # shown dimmed on 429
        history = {} if args.offline else load_history(hist_path)
        thr = thresholds_of(config)
        for series, stored in last_good_from_history(history, thr).items():
            last_good.setdefault(series, stored)
        found, _ = snapshot(dirs_from(args, config), paint, bar_style_of(args, config),
                            args.offline, refresher, kimi_refresher,
                            history=history, history_path=hist_path, sched=sched,
                            thresholds=thr, last_good=last_good, next_try=next_try)
        return 0 if found else 1

    interval = interval_of(args, config)
    print(f"claude-limits daemon: every {interval} s, config {args.config}; Ctrl+C to stop")
    try:
        while True:
            config = load_config(args.config)          # edits apply without a restart
            interval = interval_of(args, config, quiet=True)
            print(f"\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            sched = None if args.offline else forecast_config_of(config)
            history = {} if args.offline else load_history(hist_path)
            thr = thresholds_of(config)
            for series, stored in last_good_from_history(history, thr).items():
                last_good.setdefault(series, stored)   # seed missing series from history
            _, backoff = snapshot(dirs_from(args, config), paint, bar_style_of(args, config),
                                  args.offline, refresher, kimi_refresher,
                                  history=history, history_path=hist_path, sched=sched,
                                  thresholds=thr, last_good=last_good, next_try=next_try)
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
