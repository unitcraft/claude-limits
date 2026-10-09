"""Explicit isolated recovery stand; never use an owner's data directory.

Requires approved binary/union SHA256, a fresh private stand (only tooling venv
may already exist), and DuckDB installed in that private venv. Every child has
isolated homes, explicit empty folders, no refresh, and fake-only CLI PATH.
SQL opens COPY files read-only after stopping only our verified process.
Printed results are aggregate only; full child output stays in the private stand.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import tomllib
import urllib.request

import recover_history as recovery


class VerificationFailure(RuntimeError):
    """Only fixed, non-personal labels may be used here."""


def require(condition, label):
    if not condition:
        raise VerificationFailure(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def child_env(stand, inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    for key in list(env):
        if key.upper().startswith(("CLAUDE_", "KIMI_", "CODEX_", "XDG_")) or key.upper() in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH"):
            del env[key]
    for key, folder in {"HOME": "home", "USERPROFILE": "home", "APPDATA": "roaming",
                        "LOCALAPPDATA": "local", "XDG_DATA_HOME": "xdg-data",
                        "XDG_CONFIG_HOME": "xdg-config", "XDG_STATE_HOME": "xdg-state",
                        "TEMP": "tmp", "TMP": "tmp"}.items():
        env[key] = str(stand / folder)
    # Scrub the inherited override, then explicitly supply this approved stand.
    # import-history resolves paths before reading storage.data_dir from TOML.
    env["CLAUDE_LIMITS_DATA"] = str(stand / "data")
    system = Path(env.get("SystemRoot", "C:/Windows")) / "System32"
    env["PATH"] = str(stand / "fake-bin") + os.pathsep + str(system)
    return env


def expected_rows(document):
    out = {}
    for name, rows in document.items():
        account, _, raw = name.rpartition("|")
        provider, _, login = account.partition(":")
        if provider in ("claude", "codex"):
            account = provider + ":" + login.strip().lower()
        if raw in ("session", "5h limit"):
            kind, model = "session", ""
        elif raw in ("weekly_all", "weekly limit"):
            kind, model = "weekly_all", ""
        elif raw.startswith("weekly_scoped:"):
            kind, model = "weekly_scoped", raw.partition(":")[2]
        elif raw in ("month limit", "month limit (code)"):
            kind, model = "monthly", "code" if raw.endswith("(code)") else ""
        else:
            raise VerificationFailure("unsupported importer kind")
        for at, percent in rows:
            hundredths = int(percent * 100.0)
            whole, rest = divmod(hundredths, 100)
            rounded = whole + (rest > 50 or (rest == 50 and whole % 2 == 1))
            key = (account, kind, model, int(recovery.instant(at) * 1000))
            require(key not in out, "normalized importer identity collision")
            out[key] = rounded
    return out


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    require(port != 7391, "production port forbidden")
    return port


def process_path(process):
    require(os.name == "nt", "this controlled stand requires Windows process verification")
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.QueryFullProcessImageNameW.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x1000, False, process.pid)
    require(bool(handle), "cannot verify own child PID")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        require(api.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)), "cannot verify child executable")
        return Path(buffer.value)
    finally:
        api.CloseHandle(handle)


def stop(process, binary):
    if process.poll() is None:
        require(process_path(process).samefile(binary), "child executable mismatch; no termination attempted")
        process.terminate()
        process.wait(timeout=30)


def get_json(base, route):
    # Do not forward private loopback requests through inherited proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + route, timeout=30) as response:
        require(response.status == 200, "API status not 200")
        return json.loads(response.read())


def check_health(health, stand):
    storage = health.get("storage", {})
    require(health.get("ok") is True and not health.get("config_error"), "health/config failure")
    require(storage.get("schema_version") == 3 and storage.get("encrypted") is False
            and storage.get("key_store") == "none", "not schema3 plain/keynone")
    require(Path(storage["db_path"]).resolve() == (stand / "data" / "claude-limits.duckdb").resolve(), "DB outside approved data directory")
    require(Path(storage["config_path"]).resolve() == (stand / "config" / "import.toml").resolve(), "config outside stand")
    require(not list(stand.rglob("*.key")), "unexpected key file")
    require(not list((stand / "fake-bin").glob("*.called")), "fake CLI was invoked")


def check_config(config, file_config, stand):
    # The existing API exposes retention but not the refresh settings tree.
    require(config["history"]["keep_days"] == 30, "API retention mismatch")
    require(file_config["refresh"]["enabled"] is False, "refresh not explicitly disabled")
    folders = config["folders"]
    require(len(folders) == 1 and Path(folders[0]["path"]).resolve() == (stand / "empty-folder").resolve(),
            "API folder is not the explicit empty fixture")


def serve(binary, stand, env, port, label, expected_windows=None):
    base = f"http://127.0.0.1:{port}"
    with (stand / f"{label}.stdout").open("xb") as log:
        process = subprocess.Popen([str(binary), "--serve", "--config", str(stand / "config" / "import.toml")],
                                   env=env, cwd=stand, stdout=log, stderr=subprocess.STDOUT)
        try:
            require(process_path(process).samefile(binary), "started executable mismatch")
            deadline = time.monotonic() + 90
            health = None
            while time.monotonic() < deadline:
                require(process.poll() is None, "stand server exited before health")
                try:
                    health = get_json(base, "/api/health")
                    break
                except (OSError, ValueError):
                    time.sleep(0.2)
            require(health is not None, "stand health timed out")
            check_health(health, stand)
            # health.storage.history_days is observed coverage, NOT retention.
            config = get_json(base, "/api/config")["config"]
            file_config = tomllib.loads((stand / "config" / "import.toml").read_text(encoding="utf-8"))
            check_config(config, file_config, stand)
            if expected_windows is None:
                require(get_json(base, "/api/snapshot").get("accounts") == [], "fresh stand discovered accounts")
                result = {"ok": True, "schema": 3, "encrypted": False, "key_store": "none", "snapshot_accounts": 0,
                          "history_days": health["storage"]["history_days"], "keep_days": 30, "refresh_enabled": False}
            else:
                history = get_json(base, "/api/history?range=30d&by=account&step=300")
                series = history.get("series", [])
                points = [point for row in series for point in row.get("points", [])]
                require(len(series) == expected_windows and len(points) > 0, "history API missing windows/points")
                for row in series:
                    times = [recovery.instant(point["at"]) for point in row["points"]]
                    require(times == sorted(times), "history API not chronological")
                result = {"ok": True, "schema": 3, "encrypted": False, "key_store": "none",
                          "history_series": len(series), "history_bucket_points": len(points),
                          "history_from_utc": min(point["at"] for point in points),
                          "history_to_utc": max(point["at"] for point in points)}
        finally:
            stop(process, binary)
    return result


def sql_copy(stand, label, expected):
    import duckdb  # Approved private tooling venv only; not a runtime dependency.
    source = stand / "data" / "claude-limits.duckdb"
    copy = stand / f"{label}.duckdb"
    require(not copy.exists(), "verification copy already exists")
    shutil.copy2(source, copy)
    wal = Path(str(source) + ".wal")
    if wal.exists():
        shutil.copy2(wal, Path(str(copy) + ".wal"))
    connection = duckdb.connect(str(copy), read_only=True)
    try:
        rows = connection.execute("SELECT CASE WHEN a.provider='claude' THEN 'claude:'||a.email WHEN a.provider='kimi' THEN 'kimi:'||a.cred_key ELSE a.cred_key END, w.kind, coalesce(w.model,''), epoch_ms(s.sampled_at), s.percent FROM sample s JOIN limit_window w ON w.id=s.window_id JOIN account a ON a.id=w.account_id").fetchall()
        actual = {tuple(row[:4]): row[4] for row in rows}
        require(len(rows) == len(actual) and actual == expected, "SQL samples/percent/timestamps differ from normalized union")
        providers = connection.execute("SELECT a.provider, count(s.id), count(DISTINCT w.id) FROM account a JOIN limit_window w ON w.account_id=a.id JOIN sample s ON s.window_id=w.id GROUP BY a.provider ORDER BY a.provider").fetchall()
        require(all(provider in ("claude", "kimi", "codex") for provider, _, _ in providers), "unexpected provider")
        counts = connection.execute("SELECT (SELECT count(*) FROM account), (SELECT count(*) FROM limit_window), (SELECT count(*) FROM window_cycle), (SELECT count(*) FROM sample), (SELECT count(*) FROM poll)").fetchone()
        bounds = connection.execute("SELECT epoch_ms(min(sampled_at)), epoch_ms(max(sampled_at)) FROM sample").fetchone()
        kinds = connection.execute("SELECT w.kind,count(DISTINCT w.id),count(s.id) FROM limit_window w JOIN sample s ON s.window_id=w.id GROUP BY w.kind ORDER BY w.kind").fetchall()
        return {"duckdb_version": duckdb.__version__, "accounts": counts[0], "windows": counts[1],
                "inferred_cycles": counts[2], "samples": counts[3], "polls": counts[4],
                "from_utc": recovery.utc(bounds[0] / 1000) if bounds[0] else None,
                "to_utc": recovery.utc(bounds[1] / 1000) if bounds[1] else None,
                "provider_points": {p: n for p, n, _ in providers},
                "provider_windows": {p: n for p, _, n in providers},
                "kind_points": {kind: n for kind, _, n in kinds},
                "kind_windows": {kind: n for kind, n, _ in kinds}, "exact_sample_comparison": True}
    finally:
        connection.close()


def import_once(binary, union, stand, env, label):
    result = subprocess.run([str(binary), "import-history", str(union), "--config", str(stand / "config" / "import.toml")],
                            env=env, cwd=stand, capture_output=True, timeout=180)
    (stand / f"{label}.stdout").write_bytes(result.stdout + result.stderr)
    require(result.returncode == 0, "import command failed; see private log")
    text = result.stdout.decode("utf-8", "replace")
    match = re.search(r"(\d+) of (\d+) readings written", text)
    require(match is not None and "entries of the file were not readings" not in text, "missing counts or skipped input")
    return {"written": int(match[1]), "read": int(match[2])}


def run(args):
    binary, union, stand = Path(args.binary).resolve(), Path(args.union).resolve(), Path(args.stand).resolve()
    require(sha(binary) == args.binary_sha256, "approved binary hash mismatch")
    require(sha(union) == args.union_sha256, "approved union hash mismatch")
    require(not binary.is_relative_to(stand) and not union.is_relative_to(stand), "stand must not contain approved inputs")
    # A pre-created tooling venv is permitted, but no previous config/data/fixture.
    stand.mkdir(parents=True, exist_ok=True)
    require(all(p.name == "tooling" for p in stand.iterdir()), "stand is not fresh; choose a new private child")
    document = recovery.decode(union.read_bytes())
    expected = expected_rows(document)
    for folder in ("data", "config", "empty-folder", "home", "roaming", "local", "xdg-data", "xdg-config", "xdg-state", "tmp", "fake-bin"):
        (stand / folder).mkdir()
    for cli in ("claude", "kimi", "codex"):
        (stand / "fake-bin" / f"{cli}.cmd").write_text(f'@echo off\necho called > "{stand / "fake-bin" / (cli + ".called")}"\nexit /b 97\n')
    env = child_env(stand)
    port = free_port()
    config = ('[[folders]]\npath = ' + json.dumps((stand / "empty-folder").as_posix(), ensure_ascii=False)
              + f'\n[server]\nbind = "127.0.0.1"\nport = {port}\nallow_lan = false\n'
              + '[refresh]\nenabled = false\n[history]\nkeep_days = 30\n[storage]\nencrypted = false\ndata_dir = '
              + json.dumps((stand / "data").as_posix(), ensure_ascii=False) + '\n')
    (stand / "config" / "import.toml").write_text(config, encoding="utf-8")
    results = {"fresh_health": serve(binary, stand, env, port, "fresh"),
               "fresh_sql": sql_copy(stand, "verify-fresh", {})}
    require(sha(binary) == args.binary_sha256 and sha(union) == args.union_sha256, "approved inputs changed before import")
    results["first_import"] = import_once(binary, union, stand, env, "first-import")
    require(results["first_import"] == {"written": len(expected), "read": len(expected)}, "not all union readings imported")
    results["first_sql"] = sql_copy(stand, "verify-first", expected)
    results["second_import"] = import_once(binary, union, stand, env, "second-import")
    require(results["second_import"] == {"written": 0, "read": len(expected)}, "repeat import is not idempotent")
    results["second_sql"] = sql_copy(stand, "verify-second", expected)
    require(results["first_sql"] == results["second_sql"], "repeat import changed coverage")
    results["restored_health_api"] = serve(binary, stand, env, port, "restored", results["first_sql"]["windows"])
    results["final_sql"] = sql_copy(stand, "verify-final", expected)
    require(results["final_sql"] == results["first_sql"], "stand restart changed samples")
    require(sha(binary) == args.binary_sha256 and sha(union) == args.union_sha256, "approved inputs changed")
    require(not list(stand.rglob("*.key")), "key file created")
    require(not list((stand / "fake-bin").glob("*.called")), "CLI invoked")
    require(not list((stand / "empty-folder").iterdir()), "explicit empty login folder changed")
    results.update({"approved_inputs_unchanged": True, "key_files": 0, "fake_cli_calls": 0})
    recovery.atomic_write(stand / "verification.json", recovery.encoded(results))
    print(json.dumps(results, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "binary-sha256", "union", "union-sha256", "stand"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        # No exception repr: SQL/HTTP/filesystem errors may contain private values.
        print("FAIL: isolated verification; details remain in private stand. Error type: " + type(error).__name__)
        if isinstance(error, VerificationFailure):
            print(str(error))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
