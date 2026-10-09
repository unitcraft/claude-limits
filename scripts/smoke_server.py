"""Smoke test of `claude-limits --serve` (plan 01.5, T2.26 -- the part that exists).

Raises the BUILT binary on a free port against a fixture made on the spot, and asks
it what a person and a browser would ask. No network, no real credentials: the
fixture's token expired in 1970, so the account is `stale` and the endpoint is never
called -- a smoke test that needed the owner's token would be a smoke test nobody
else can run.

Checks, one line each:
  health       GET /api/health is 200 and says "ok": true
  page         GET / is 200 text/html
  snapshot     GET /api/snapshot lists the fixture's one account as `stale`,
               with the 01.1 text and no rows
  moment       the snapshot's `fetched_at` is NOW, to the minute -- the whole binary
               formats a moment right (2026-10-02: a free fn `sec` in one module made
               std's `to_zoned` lose the time of day, every moment read 00:00:00Z, and
               no unit test saw it: none holds both)
  refresh      (Windows) the stale login's renewal IS launched -- a fake `claude.cmd`
               first on PATH marks its directory and then sleeps -- and the server
               answers while it sleeps: the round must not wait for Claude Code
               (CI went red on exactly that, 2026-10-02). No network: the fake is all
               that runs.
  settings     GET /api/config carries the configured folder INSIDE `config`, as the
               page reads it, with the login the round found there
  save         PUT /api/config of `ui` is 200, written to the file, and the folder
               list survives it -- the save that once replaced every folder
  busy port    a second copy on the same port exits 1 and says "address already in use"
  lan          `allow_lan = true` refuses the start with exit 2 and names the field

Exit codes:
  0  every check passed
  1  a check failed -- the finding this script exists for
  2  could not run (no binary). NEVER 0: an unbuilt binary must not read as a pass.

Usage:
  ./scripts/smoke-server.sh [path/to/claude-limits.exe]
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def database_health_ok(health, *, encrypted=False):
    """Require schema 3, the exact requested mode/key store and a real file."""
    if not isinstance(health, dict):
        return False
    storage = health.get("storage")
    if not isinstance(storage, dict):
        return False
    schema = storage.get("schema_version")
    size = storage.get("db_size_bytes")
    # src/storage/db.nv KNOWN_SCHEMA / migrations/0003_codex_accounts.sql.
    return (type(encrypted) is bool and storage.get("encrypted") is encrypted
            and storage.get("key_store") == ("file" if encrypted else "none")
            and type(schema) is int and schema == 3
            and type(size) is int and size > 0)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url, timeout=5):
    """(status, content_type, body) -- or (0, "", error text) when nothing answered."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 -- any failure to answer is the same finding
        return 0, "", str(e)


def put_json(url, body, if_match, timeout=10):
    """(status, body) of a JSON PUT with `If-Match`; (0, error text) when nothing answered."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PUT",
                                 headers={"Content-Type": "application/json", "If-Match": if_match})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def fixture(tmp, port):
    """One login in the CLAUDE_CONFIG_DIR layout, token long expired; two settings files."""
    login = os.path.join(tmp, "acc", "work")
    write(os.path.join(login, ".claude.json"),
          '{"oauthAccount":{"emailAddress":"smoke@example.org","organizationName":"Example Inc"}}')
    write(os.path.join(login, ".credentials.json"),
          '{"claudeAiOauth":{"accessToken":"sk-ant-smoke-FIXTURE","expiresAt":1000}}')
    folder = os.path.join(tmp, "acc").replace("\\", "/")
    ok = os.path.join(tmp, "ok.toml")
    write(ok, f'[[folders]]\npath = "{folder}"\n\n[server]\nport = {port}\n')
    lan = os.path.join(tmp, "lan.toml")
    write(lan, f"[server]\nport = {port}\nallow_lan = true\n")
    # The fake Claude Code: it marks the login it was started for, then sleeps far
    # longer than any request below may take.
    write(os.path.join(tmp, "bin", "claude.cmd"),
          '@echo off\r\necho %* > "%CLAUDE_CONFIG_DIR%\\fake-claude-ran.txt"\r\n'
          'ping -n 30 127.0.0.1 >nul\r\n')
    return ok, lan


def main(argv):
    exe = argv[1] if len(argv) > 1 else os.path.join(ROOT, "target", "claude-limits.exe")
    if not os.path.exists(exe):
        alt = os.path.join(ROOT, "target", "claude-limits")
        exe = alt if os.path.exists(alt) else exe
    if not os.path.exists(exe):
        print(f"CANNOT RUN: no binary at {exe} -- build it first (./nova.sh build src/claude_limits.nv -o target/claude-limits.exe)")
        return 2

    # CreateProcess does not reliably resolve a relative forward-slash path on Windows.
    exe = os.path.abspath(exe)
    tmp = tempfile.mkdtemp(prefix="claude-limits-smoke-")
    port = free_port()
    ok_cfg, lan_cfg = fixture(tmp, port)
    # The server opens its DATABASE at the start (since 2026-09-30), under the user's
    # data directory. Without this the smoke would create a key and an encrypted file
    # in the real profile of whoever runs it. Every launch below gets `env`.
    env = dict(os.environ,
               CLAUDE_LIMITS_DATA=os.path.join(tmp, "data"),
               CLAUDE_LIMITS_CONFIG=ok_cfg,
               CLAUDE_LIMITS_DB_KEY_FILE=os.path.join(tmp, "claude-limits.key"),
               LOCALAPPDATA=os.path.join(tmp, "local"), APPDATA=os.path.join(tmp, "roaming"),
               XDG_DATA_HOME=os.path.join(tmp, "xdg-data"), XDG_CONFIG_HOME=os.path.join(tmp, "xdg-config"),
               XDG_STATE_HOME=os.path.join(tmp, "xdg-state"),
               PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ.get("PATH", ""))
    base = f"http://127.0.0.1:{port}"
    results = []

    def check(name, passed, detail=""):
        results.append(passed)
        print(("PASS" if passed else "FAIL") + f": {name}" + (f" -- {detail}" if detail and not passed else ""))

    server = subprocess.Popen([exe, "--serve", "--config", ok_cfg],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        status = 0
        deadline = time.time() + 60
        while time.time() < deadline:
            status, _, body = get(base + "/api/health", timeout=2)
            if status:
                break
            if server.poll() is not None:
                break
            time.sleep(0.5)

        status, _, body = get(base + "/api/health")
        check("health", status == 200 and '"ok":true' in body, f"{status} {body[:120]}")
        # The default database is plain, with exact current schema and a real file.
        try:
            health = json.loads(body)
            st = health.get("storage", {}) if isinstance(health, dict) else {}
            db_ok = database_health_ok(health)
        except ValueError:
            st, db_ok = {}, False
        check("database", db_ok, f"storage {st}")

        status, ctype, _ = get(base + "/")
        check("page", status == 200 and ctype.startswith("text/html"), f"{status} {ctype}")
        # 01.3: the page carries its CSP -- without it an antivirus injected a script
        # into the owner's page (2026-10-02). The header itself, not its consequences.
        try:
            with urllib.request.urlopen(base + "/", timeout=5) as r:
                csp = r.headers.get("Content-Security-Policy", "")
        except Exception as e:  # noqa: BLE001
            csp = f"<{e}>"
        check("page CSP", "script-src 'self'" in csp and "default-src 'none'" in csp, csp)

        status, _, body = get(base + "/api/snapshot")
        try:
            snap = json.loads(body)
            accounts = snap.get("accounts", [])
            one = accounts[0] if len(accounts) == 1 else {}
            fine = (status == 200 and len(accounts) == 1 and one.get("state") == "stale"
                    and (one.get("message") or "").startswith("token expired")
                    and len(snap.get("limits", [])) == 0)
            check("snapshot", fine, f"{status} {body[:200]}")
            at = snap.get("fetched_at") or ""
            try:
                from datetime import datetime, timezone
                when = datetime.fromisoformat(at.replace("Z", "+00:00"))
                off = abs((datetime.now(timezone.utc) - when).total_seconds())
            except ValueError:
                off = None
            check("moment", off is not None and off < 120, f"fetched_at {at!r}, {off} s from now")
        except ValueError:
            check("snapshot", False, f"{status} not JSON: {body[:120]}")

        if os.name == "nt":
            marker = os.path.join(tmp, "acc", "work", "fake-claude-ran.txt")
            until = time.time() + 20
            while time.time() < until and not os.path.exists(marker):
                time.sleep(0.5)
            launched = os.path.exists(marker)
            t0 = time.time()
            status, _, body = get(base + "/api/snapshot", timeout=5)
            took = time.time() - t0
            check("refresh", launched and status == 200 and took < 3,
                  f"launched={launched} snapshot {status} in {took:.1f}s while the fake claude sleeps")

        # THE HISTORY (T2.15), read back from the database this start wrote. The fixture's
        # login is expired, so no tick is written -- but the round's DISCOVERY is: the
        # directory, and a journal row saying its token is stale with nobody valid in it.
        # That row is the only live proof that discovery reaches the file at all.
        status, _, body = get(base + "/api/history?range=24h")
        try:
            h = json.loads(body)
            fine = status == 200 and all(k in h for k in ("range", "accounts", "series", "tiles"))
            check("history", fine, f"{status} {body[:200]}")
        except ValueError:
            check("history", False, f"{status} not JSON: {body[:120]}")

        status, _, body = get(base + "/api/history?account_id=0192a7f0-0000-7000-8000-000000000001")
        check("history refuses an account id in the URL", status == 400 and "invalid_parameter" in body,
              f"{status} {body[:160]}")

        status, _, body = get(base + "/api/history?range=7d&by=folder")
        try:
            f = json.loads(body)
            folders = f.get("folders", [])
            occ = f.get("occupancy", [])
            dry = (f.get("tiles") or {}).get("days_without_login") or {}
            fine = (status == 200 and len(folders) == 1 and folders[0].get("name") == "work"
                    and folders[0].get("now") is None and len(occ) == 1
                    and occ[0].get("token_state") == "stale" and occ[0].get("account_id") is None
                    and dry.get("reason") == "token_expired")
            check("history by folder: discovery reached the database", fine, f"{status} {body[:300]}")
        except ValueError:
            check("history by folder: discovery reached the database", False, f"{status} not JSON: {body[:120]}")

        # THE SETTINGS, in the shape the PAGE reads (01.3 section 3.7): `config.folders`.
        # The server put them beside `config` until 2026-10-02 -- every handler test
        # passed, the page found no folders, and its first save replaced the list.
        status, _, body = get(base + "/api/config")
        try:
            c = json.loads(body)
            fs = (c.get("config") or {}).get("folders") or []
            one = fs[0] if len(fs) == 1 else {}
            dirs = [d.get("name") for d in one.get("login_dirs") or []]
            fine = (status == 200 and "folders" not in c and one.get("kind") == "parent" and dirs == ["work"]
                    and [a.get("email") for a in c.get("accounts_found") or []] == ["smoke@example.org"])
            check("settings", fine, f"{status} {body[:300]}")
            etag = c.get("etag", "")
        except ValueError:
            check("settings", False, f"{status} not JSON: {body[:120]}")
            etag = ""

        status, body = put_json(base + "/api/config", {"ui": {"accounts_order": ["smoke@example.org"]}}, etag)
        _, _, after = get(base + "/api/config")
        try:
            kept = len(((json.loads(after).get("config") or {}).get("folders")) or [])
        except ValueError:
            kept = -1
        with open(ok_cfg, encoding="utf-8") as fh:
            on_disk = fh.read()
        fine = (status == 200 and kept == 1 and 'accounts_order = ["smoke@example.org"]' in on_disk
                and "[[folders]]" in on_disk)
        check("save", fine, f"{status} folders after={kept} {body[:160]}")

        second = subprocess.run([exe, "--serve", "--config", ok_cfg], capture_output=True, text=True, timeout=60, env=env)
        # The server's own lines go to stderr (they are a log; stdout is buffered when it
        # is not a console -- claude_limits.nv `say`), so both streams are read.
        said = second.stdout + second.stderr
        check("busy port", second.returncode == 1 and "address already in use" in said,
              f"exit {second.returncode}: {said.strip()[:160]}")
    finally:
        server.kill()
        server.wait(timeout=10)

    lan = subprocess.run([exe, "--serve", "--config", lan_cfg], capture_output=True, text=True, timeout=60, env=env)
    lan_said = lan.stdout + lan.stderr
    check("lan", lan.returncode == 2 and "server.allow_lan" in lan_said,
          f"exit {lan.returncode}: {lan_said.strip()[:160]}")

    shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(1 for r in results if r)
    print(f"smoke: {passed} of {len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
