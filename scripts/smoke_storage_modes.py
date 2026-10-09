"""Release-binary storage policy smoke on private synthetic data only.

python scripts/smoke_storage_modes.py target/cl13.exe
The Nova startup suite separately opens DBs/backups through the engine and checks
every per-call failure path. This probe verifies real CLI/API and restart behavior.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from smoke_server import database_health_ok, free_port, get, put_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_mode(exe, root, encrypted):
    root.mkdir()
    cfg = root / 'settings.toml'
    data = root / 'data'
    key = root / 'keys' / 'db.key'
    key.parent.mkdir()
    port = free_port()
    base = f'http://127.0.0.1:{port}'
    # No accounts, no real CLI, no credentials or network poll; import is synthetic.
    fake = root / 'bin'
    fake.mkdir()
    (fake / 'claude.cmd').write_text('@exit /b 99\n')
    (fake / 'codex.cmd').write_text('@exit /b 99\n')
    env = dict(os.environ, CLAUDE_LIMITS_DATA=str(data),
               CLAUDE_LIMITS_CONFIG=str(cfg), CLAUDE_LIMITS_DB_KEY_FILE=str(key),
               APPDATA=str(root / 'roaming'), LOCALAPPDATA=str(root / 'local'),
               XDG_CONFIG_HOME=str(root / 'xdg-config'), XDG_DATA_HOME=str(root / 'xdg-data'),
               XDG_STATE_HOME=str(root / 'xdg-state'),
               PATH=str(fake) + os.pathsep + os.environ.get('PATH', ''))

    def settings(mode):
        # Missing storage is the default-policy probe, not an explicit false.
        storage = '\n[storage]\nencrypted = true\n' if mode else ''
        cfg.write_text(f'[server]\nport = {port}\n[refresh]\nenabled = false\n{storage}')

    def command(*args):
        return subprocess.run([exe, *args, '--config', str(cfg)], env=env,
                              capture_output=True, text=True, timeout=30)

    def start():
        server = subprocess.Popen([exe, '--serve', '--config', str(cfg)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                status, _, body = get(base + '/api/health', timeout=2)
                if status == 200:
                    assert database_health_ok(json.loads(body), encrypted=encrypted), body
                    return server
                assert server.poll() is None, 'server exited before health'
                time.sleep(.2)
            raise AssertionError('health timed out')
        except BaseException:
            stop(server)
            raise

    def stop(server):
        if server.poll() is None:
            server.terminate()
        server.wait(timeout=15)

    settings(encrypted)
    server = start()
    try:
        assert key.exists() is encrypted
        status, _, body = get(base + '/api/config')
        state = json.loads(body)
        assert status == 200 and state['config']['storage']['encrypted'] is encrypted
        # Persist the opposite mode. The open runtime must still read/write using
        # its startup mode, including config_history on a second save.
        status, body = put_json(base + '/api/config',
                                {'storage': {'encrypted': not encrypted}}, state['etag'])
        assert status == 200, body
        changed = json.loads(body)
        assert changed['applied']['restart_required'] is True
        assert changed['config']['storage']['encrypted'] is (not encrypted)
        status, body = put_json(base + '/api/config', {'ui': {'time_bar': False}}, changed['etag'])
        assert status == 200, body
        status, _, body = get(base + '/api/health')
        assert status == 200 and database_health_ok(json.loads(body), encrypted=encrypted), body
        assert get(base + '/api/history?range=7d')[0] == 200
        assert key.exists() is encrypted
    finally:
        stop(server)

    db = data / 'claude-limits.duckdb'
    before = digest(db)
    original_key = key.read_bytes() if encrypted else None
    # Restart with saved opposite mode refuses; no conversion and no replacement.
    refused = command('--serve')
    assert refused.returncode != 0, refused.stdout
    assert 'storage.encrypted' in refused.stdout + refused.stderr
    assert digest(db) == before
    if encrypted:
        assert key.read_bytes() == original_key
    # Enabling encryption on a plain existing DB must not create a key either.
    else:
        assert not key.exists()
        # Also reach the engine: an unrelated existing key must not turn a plain
        # database into ciphertext (or allow a false encrypted health claim).
        key.write_text('synthetic-unrelated-key')
        refused = command('--serve')
        assert refused.returncode != 0
        assert digest(db) == before
        assert key.read_text() == 'synthetic-unrelated-key'
        key.unlink()

    settings(encrypted)
    history = root / 'history.json'
    history.write_text(json.dumps({'claude:mode@example.org|weekly_all':
                                  [['2026-10-08T12:00:00Z', 12], ['2026-10-08T12:05:00Z', 13]]}))
    imported = command('import-history', str(history))
    assert imported.returncode == 0, imported.stdout + imported.stderr
    assert '2 of 2 readings written' in imported.stdout, imported.stdout
    assert list((data / 'backup').glob('*.duckdb'))
    forgotten = command('forget', 'mode@example.org')
    assert forgotten.returncode == 0 and 'account is forgotten' in forgotten.stdout, forgotten.stdout
    assert not Path(str(db) + '.fresh').exists()

    if encrypted:
        key.unlink()
        before = digest(db)
        entries = sorted(p.name for p in key.parent.iterdir())
        for args in [('--serve',), ('import-history', str(history)), ('forget', 'mode@example.org')]:
            refused = command(*args)
            assert refused.returncode != 0
            assert 'original key' in refused.stdout + refused.stderr
            assert not key.exists() and digest(db) == before
            assert sorted(p.name for p in key.parent.iterdir()) == entries
        settings(False)
        refused = command('--serve')
        assert refused.returncode != 0 and digest(db) == before and not key.exists()
        settings(True)
        key.write_bytes(original_key)
    else:
        assert not key.exists()
    server = start()
    stop(server)
    print(f'PASS: {"encrypted" if encrypted else "default plain"} CLI/API lifecycle, pinned runtime, refusal integrity')


def main():
    exe = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix='cl13-storage-modes-') as tmp:
        for encrypted in (False, True):
            run_mode(exe, Path(tmp) / str(encrypted), encrypted)
    print('STORAGE MODES: 2 of 2 passed')


if __name__ == '__main__':
    main()
