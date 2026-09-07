# fixtures

Synthetic inputs for the tests. **Nothing real goes in here** — no live token, no
real e-mail, no real machine path. A fixture that carries a real secret turns
every test run and every commit into a leak.

Conventions (executor brief §2.4):

- e-mail addresses use `@example.com` and `@example.org`;
- home paths use the user `me`;
- tokens look like `sk-ant-fixture-…` — tests search the program's output for
  exactly that shape to prove no token escaped into JSON, a log or the page.

Layout, filled in by the tasks that need each kind:

| directory | what | filled by |
|---|---|---|
| `usage/` | recorded endpoint replies with fields cleaned: normal, `locked_reason` set, empty `limits` (falls back to `five_hour`/`seven_day`), two `weekly_scoped` models, invalid JSON, HTTP 401, HTTP 500 | T1.5 |
| `dirs/` | Claude Code login directories in both layouts (`.claude.json` beside `~/.claude`, and both files inside a `CLAUDE_CONFIG_DIR`), a directory with no login, an expired `expiresAt`, two directories sharing one e-mail, a WSL UNC path | T1.3 |
| `config/` | `claude-limits.toml` variants: full and valid, `interval_sec = 10` (raised to 60 with a warning), `allow_lan = true` (rejected until Ф.6), an unknown key, two errors at once | T1.2 |

Reference for what the real data looks like: `scripts/claude_limits.py` and the
README section "How it gets the data".
