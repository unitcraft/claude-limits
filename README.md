# claude-limits

Usage limits of several Claude accounts on one page: a small local backend you
open in the browser. Windows and Linux.

For every Claude Code login on the machine it shows the same numbers that
`/usage` shows inside Claude Code: the 5-hour session window, the 7-day window
(all models and per model), when each resets, and whether the account is
currently locked. All accounts side by side, without switching logins.

## Why

Claude Code keeps one login per config directory. With several accounts
(`CLAUDE_CONFIG_DIR=...` per account) the only way to see remaining quota is to
open a session under each of them and type `/usage`.

The reference for this project is
[claude-usage-widget](https://github.com/niccolo-sabato/claude-usage-widget).
It differs in three ways: it reads Claude Code's own OAuth tokens instead of a
browser session key, it shows several accounts at once instead of switching
between them, and it runs on Linux as well as Windows.

## How it gets the data

### Accounts

A Claude Code login is a config directory with two files:

| file | what is read | notes |
|---|---|---|
| `.claude.json` | `oauthAccount.emailAddress`, `oauthAccount.organizationName` | identity, shown as the row label |
| `.credentials.json` | `claudeAiOauth.accessToken`, `expiresAt`, `subscriptionType`, `rateLimitTier` | `expiresAt` is milliseconds since the epoch |

Two layouts exist:

- **default**: the directory is `~/.claude` (`%USERPROFILE%\.claude` on
  Windows) and `.claude.json` sits *beside* it, not inside;
- **`CLAUDE_CONFIG_DIR`**: both files live *inside* the named directory. Several
  such directories under one parent are a multi-account setup.

Discovery: the default directory, `CLAUDE_CONFIG_DIR` if set, and every
directory the user lists in the tool's own config (or every child of a
parent directory). macOS keeps tokens in the Keychain and is out of scope.

### Endpoint

```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <accessToken>
anthropic-beta: oauth-2025-04-20
```

Both headers are required: the OAuth token goes in `Authorization: Bearer`,
never in `x-api-key`. The response is JSON; the useful part is `limits[]`:

| field | meaning |
|---|---|
| `kind` | `session` (5 h), `weekly_all` (7 d, all models), `weekly_scoped` (7 d, one model) |
| `percent` | utilization, 0-100 |
| `severity` | `normal`, `warning`, ... |
| `resets_at` | ISO-8601 with offset |
| `is_active` | whether this window is the one currently limiting |
| `scope.model.display_name` | model name for `weekly_scoped` |

`five_hour` and `seven_day` carry the same numbers as `utilization` +
`resets_at` plus a `locked_reason` when the account is blocked. `extra_usage`
and `spend` describe paid usage above the plan.

This endpoint is the one Claude Code's `/usage` command uses. It is not in the
public platform documentation and may change without notice. The documented
Admin API (`GET /v1/organizations/rate_limits`) needs an organization admin
key and does not apply to a subscription login.

### Token lifetime

`accessToken` lives for hours. Claude Code refreshes it while a session runs
and rewrites `.credentials.json`. The tool therefore re-reads the file before
every request and never caches a token. An expired token with no Claude Code
session to refresh it is shown as a stale login and is not sent at all (the
server would answer 401, then 429 to the whole machine). The tool never
refreshes a token itself: `refreshToken` is Claude Code's, and stays untouched.

## Rules

- A token leaves the machine only towards `api.anthropic.com`. It is never
  logged, never displayed, never written anywhere.
- Read-only: the tool never writes into Claude Code's directories.
- The local HTTP server listens on `127.0.0.1` only unless you bind it to the
  network on purpose, and then only with an access token: the page shows
  e-mails and organisation names. Tokens never appear in any response.
- Polling is slow (a minute by default); the numbers change slowly and the
  endpoint is not ours.

## Status

Design stage. `scripts/claude_limits.py` is a stdlib-only reference for the data path:
it discovers config directories and prints one row per account and window, once
or as a daemon (a snapshot every five minutes by default).

Accounts are listed in `claude-limits.toml` in the repository root (gitignored,
it names your logins); copy `claude-limits.example.toml` and edit:

```toml
interval_sec = 300
accounts_parent = "C:/accounts"   # every child dir holding a login
accounts = ["~/.claude"]                           # individual dirs
```

Without a config file the tool falls back to `~/.claude` and `CLAUDE_CONFIG_DIR`.
Directories on the command line override the config. Python 3.11+.

Every limit row carries a progress bar, `[████░░░░]`, the filled part
coloured green, yellow or red by severity. The whole account header line is
highlighted: green when the token works and the numbers are fresh, red when
the token is expired or rejected, yellow when the server or network failed.
`--color always|never` overrides colour; `NO_COLOR` is honoured; a log file
gets no escape codes.

**If the bar looks empty** (`[            ]`), the terminal is not drawing the
block characters `█`/`░`. Two fixes, in order:

1. In VS Code, set `"terminal.integrated.gpuAcceleration": "off"` (Settings ->
   search "terminal gpu"), or pick a terminal font that has block glyphs
   (`"terminal.integrated.fontFamily": "Cascadia Code"` / `Consolas`). This is
   a rendering issue in the terminal, not in the tool.
2. Or keep the terminal as is and use `--bar-style ascii` (or `bar_style =
   "ascii"` in the config) for a `[####....]` bar, which any font draws.

Directories holding the same account (same e-mail) are shown as one group
and asked for once: the endpoint answers HTTP 429 to eager callers, so the
tool also never polls more often than once a minute and, on a 429, waits the
`Retry-After` the server names before the next snapshot.
The real tool is written in [Nova](https://nv-lang.org): one binary that runs
a local backend — it polls the endpoint, serves a page with the bars at
`http://127.0.0.1:7391`, and pushes updates over Server-Sent Events. It can
also install itself to start at login (`--install-autostart`, undone with
`--uninstall-autostart`).

A desktop widget — an always-on-top window with a tray icon, built on SDL3 —
is designed and NOT in the first release: it costs a vendored C dependency and
a topmost matrix across four desktop environments, and the page in the browser
does the same job. The design is kept rather than dropped; see phase Ф.3 of the
plan. The Python script stays as the reference the Nova build is diffed
against. The plan, with phases and acceptance criteria, is
[docs/plans/01-widget-on-nova.md](docs/plans/01-widget-on-nova.md) (Russian).

```
python scripts/claude_limits.py                                      # one snapshot, accounts from the config
python scripts/claude_limits.py --daemon                             # every interval_sec, Ctrl+C to stop
python scripts/claude_limits.py --daemon --interval 60
python scripts/claude_limits.py C:/accounts/nv-lang  # explicit dirs instead of the config
python scripts/claude_limits.py --parent C:/accounts # every child dir instead of the config

.\scripts\start-daemon.ps1              # Windows: daemon in this console
.\scripts\start-daemon.ps1 -Detached    # hidden, output to claude-limits.log; prints the PID to stop
```

## Roadmap

- [x] reference script: discovery (default dir, `CLAUDE_CONFIG_DIR`, configured list, parent dir), same-account grouping, 429 backoff, daemon mode
- [ ] Nova core: same table as the script, byte-for-byte (`--once`)
- [ ] local backend: `/api/snapshot`, `/api/events` (SSE), embedded page with one bar per account per window
- [ ] threshold notifications, history
- [ ] after the first release: optional widget (`--widget`) — always-on-top window and tray icon on Windows and Linux (StatusNotifier)

## License

MIT OR Apache-2.0, at your option. See [LICENSE](LICENSE).
