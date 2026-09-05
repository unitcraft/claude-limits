# claude-limits

Usage limits of several Claude accounts in one tray widget. Windows and Linux.

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
directory the user lists in the widget's own config (or every child of a
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
and rewrites `.credentials.json`. The widget therefore re-reads the file before
every request and never caches a token. An expired token with no Claude Code
session to refresh it is shown as a stale login; whether the widget should
refresh it itself is an open question (see Roadmap).

## Rules

- A token leaves the machine only towards `api.anthropic.com`. It is never
  logged, never displayed, never written anywhere.
- Read-only: the widget never writes into Claude Code's directories.
- Polling is slow (a minute by default); the numbers change slowly and the
  endpoint is not ours.

## Status

Design stage. `scripts/probe.py` is a stdlib-only reference for the data path:
it discovers config directories and prints one row per account and window.
The stack for the widget itself is not decided yet.

```
python scripts/probe.py                                    # default dir + CLAUDE_CONFIG_DIR
python scripts/probe.py C:/accounts/nv-lang  # explicit dirs
python scripts/probe.py --parent C:/accounts # every child dir
```

## Roadmap

- [ ] account discovery: default dir, `CLAUDE_CONFIG_DIR`, configured list, parent dir
- [ ] tray icon showing the worst percentage across accounts; popup with one bar per account per window
- [ ] Windows tray and Linux StatusNotifier/AppIndicator
- [ ] threshold notifications
- [ ] decide whether to refresh an expired token outside Claude Code

## License

MIT OR Apache-2.0, at your option. See [LICENSE](LICENSE).
