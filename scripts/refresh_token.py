"""Refreshing a Claude Code login by making Claude Code itself refresh it.

THIS MODULE NEVER TOUCHES `.credentials.json`. Not the `refreshToken`, not any
other value in it -- it reads the file's mtime and nothing else. That is not
caution, it is the rule the tool is built on (README, "Token lifetime"):
`refreshToken` belongs to Claude Code, and a second refresher racing it would be
a second writer of one file. What happens here instead is that Claude Code is
started with its config directory pointed at the account and asked for one tiny
answer; IT rewrites the file.

Two kinds of directory, dispatched by the path, because the refresh must happen
inside the system that owns the login:

    Windows   <accounts parent>\<name>, %USERPROFILE%\.claude
              -> `claude` on this machine with CLAUDE_CONFIG_DIR set.
    WSL       \\\\wsl.localhost\\<distro>\\home\\<user>\\.claude  (also \\\\wsl$\\...)
              -> `claude` INSIDE that distro, as that user. Reaching the file
                 across the UNC share would write it, but it would be the
                 Windows install's idea of that home; the login belongs to the
                 distro, so the refresh is done there.

THE VERDICT IS THE FILE'S mtime, NOT THE EXIT CODE. A `claude` that answered
happily on a token that was still valid rewrites nothing, and that is reported
as `unchanged` rather than as success -- two different facts, and only one of
them means a refresh happened.

Every refresh costs one small request on that account's own limits -- the very
resource this repository measures. Nothing here runs by itself: the caller names
the directories.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT = 120

# A directory whose refresh fails keeps failing -- a revoked login, a logged-out
# account -- and without a floor the daemon would spend a request on it every
# cycle, forever, on the limits it exists to protect.
DEFAULT_COOLDOWN = 3600

WSL_UNC = re.compile(r"^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\(.+)$")


def wsl_parts(cfg_dir):
    """(distro, user, posix path) for a WSL UNC path, else None.

    The user is taken from the path rather than left to `wsl -u`'s default,
    because the default user would refresh a DIFFERENT login and report success.
    """
    m = WSL_UNC.match(str(cfg_dir))
    if not m:
        return None
    distro, rest = m.group(1), m.group(2).replace("\\", "/")
    posix = "/" + rest
    home = re.match(r"^/home/([^/]+)(?:/|$)", posix)
    if not home:
        return None
    return distro, home.group(1), posix


def creds_mtime(cfg_dir):
    """The credentials file's mtime, or None when there is no login here.

    The only thing ever read from that file in this module.
    """
    f = Path(cfg_dir) / ".credentials.json"
    try:
        return f.stat().st_mtime
    except OSError:
        return None


def claude_exe():
    """The Claude Code launcher for THIS machine, or None.

    `claude.cmd` before `claude` on Windows: the bare name resolves to the
    PowerShell shim, which cannot be started as a process.
    """
    return shutil.which("claude.cmd") or shutil.which("claude")


def refresh(cfg_dir, model=DEFAULT_MODEL, timeout=DEFAULT_TIMEOUT):
    """Makes Claude Code refresh the login in `cfg_dir`.

    Returns (verdict, note) where verdict is one of:
      `refreshed`  the credentials file was rewritten -- the only success
      `unchanged`  the run succeeded and rewrote nothing: the token was valid
      `failed`     the run failed, timed out, or there is nothing to run
    """
    cfg_dir = Path(cfg_dir)
    if not cfg_dir.is_dir():
        return "failed", "no such directory"
    before = creds_mtime(cfg_dir)
    if before is None:
        return "failed", "no .credentials.json: never logged in here"

    wsl = wsl_parts(cfg_dir)
    if wsl:
        distro, user, posix = wsl
        exe = shutil.which("wsl.exe") or shutil.which("wsl")
        if not exe:
            return "failed", "wsl.exe not found"
        inner = f"cd ~ && CLAUDE_CONFIG_DIR='{posix}' claude -p ok --model {model}"
        cmd, env = [exe, "-d", distro, "-u", user, "--", "bash", "-lc", inner], None
    else:
        exe = claude_exe()
        if not exe:
            return "failed", "claude not found on this machine"
        cmd = [exe, "-p", "ok", "--model", model]
        # A copy, not this process's environment: the daemon may itself be
        # running under a CLAUDE_CONFIG_DIR, and pointing it at another account
        # for the rest of its life would be a silent account switch.
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg_dir))

    try:
        p = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "failed", f"timed out after {timeout}s"
    except OSError as e:
        return "failed", str(e)

    after = creds_mtime(cfg_dir)
    if after is not None and before is not None and after > before:
        return "refreshed", ""
    if p.returncode == 0:
        return "unchanged", "token was still valid"
    # The last line of stderr names the failure. No token travels this channel:
    # Claude Code does not print one.
    tail = (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    return "failed", (tail[-1][:200] if tail else f"exit {p.returncode}")


class Refresher:
    """The daemon's auto-refresh: which directories, how often, and the floor.

    The cooldown lives in memory only. A restart therefore retries a hopeless
    directory once, which is the cheaper mistake: a state file would be a second
    thing to keep correct, and getting it wrong would suppress a refresh that
    was needed rather than repeat one that was not.
    """

    def __init__(self, model=DEFAULT_MODEL, timeout=DEFAULT_TIMEOUT,
                 cooldown=DEFAULT_COOLDOWN, all_expired=False):
        self.model = model
        self.timeout = timeout
        self.cooldown = cooldown
        self.all_expired = all_expired
        self._last = {}

    def targets(self, accounts):
        """The directories worth a refresh this cycle.

        BY DEFAULT ONLY WHAT BLOCKS A READING -- an account with no live token
        anywhere. An account that still reports numbers through another
        directory is left alone: silencing its parenthetical note would spend a
        request on limits that are not in anybody's way. `all_expired` takes the
        other choice.
        """
        now = time.time()
        out = []
        for acc in accounts:
            if acc["token"] is not None and not self.all_expired:
                continue
            for path in acc.get("expired_paths") or []:
                key = str(path).lower()
                if now - self._last.get(key, 0) < self.cooldown:
                    continue
                out.append(path)
        return out

    def run(self, targets, report):
        """Refreshes each target, reporting one line per attempt.

        `report(text)` is the caller's printer, so this module never decides how
        the daemon's output looks.
        """
        for path in targets:
            self._last[str(path).lower()] = time.time()
            verdict, note = refresh(path, self.model, self.timeout)
            tail = f" -- {note}" if note else ""
            report(f"  auto-refresh {short(path)}: {verdict}{tail}")


def short(path):
    """A directory's last component, enough to tell one login from another."""
    p = Path(path)
    return p.name if p.name != ".claude" else str(p)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(
        description="Refresh a Claude Code login by making Claude Code refresh it.")
    ap.add_argument("dirs", nargs="*", help="config directories to refresh")
    ap.add_argument("--all", action="store_true",
                    help="every directory the daemon watches, discovered by ITS code")
    ap.add_argument("--config", metavar="PATH", help="TOML config used by --all")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="model for the throwaway request")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC")
    args = ap.parse_args(argv)

    dirs = list(args.dirs)
    if args.all:
        # Imported here, not at module scope: `claude_limits` imports THIS
        # module, and a cycle at import time would break the daemon rather than
        # this one command. The discovery is reused rather than rewritten -- a
        # second reader of one config drifts from the first on its first edit.
        import types
        import claude_limits as cl
        cfg = cl.load_config(args.config or cl.DEFAULT_CONFIG)
        ns = types.SimpleNamespace(parent=None, dirs=None)
        dirs += [str(d) for d in cl.dirs_from(ns, cfg)]
    if not dirs:
        ap.error("name a directory, or ask for --all. Nothing is refreshed by default: "
                 "each refresh spends a request on that account's own limits")

    worst = 0
    for d in dirs:
        verdict, note = refresh(d, args.model, args.timeout)
        tail = f" -- {note}" if note else ""
        print(f"{d}\n  {verdict}{tail}")
        if verdict == "failed":
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
