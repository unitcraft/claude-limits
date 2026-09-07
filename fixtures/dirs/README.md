# fixtures/dirs — Claude Code login directories

Inputs for `accounts/discover.nv`, `accounts/login.nv` and `accounts/group.nv`
(task T1.3, plan 01.5). Each directory is a login the discovery code must handle,
laid out exactly as Claude Code lays one out.

Regenerate with `python scripts/make-dir-fixtures.py`; check with
`python scripts/check-dir-fixtures.py`, which runs the REFERENCE tool's discovery
(`scripts/claude_limits.py`) over them and asserts the property each one pins.

| directory | what it pins | the mistake it catches |
|---|---|---|
| `default-layout/` | `.claude.json` sits BESIDE `.claude/`, credentials inside it | reading the identity from inside the directory and finding no e-mail, so the account shows as a bare path |
| `config-dir-layout/work/` | both files INSIDE one directory, the `CLAUDE_CONFIG_DIR` shape | handling only the home layout |
| `no-login/` | a directory with no `.credentials.json` | erroring on it, or counting it as an account |
| `expired/` | `expiresAt` long past | sending the token anyway — the server answers 401 and then 429 to the whole machine |
| `two-dirs-one-account/` | two directories, one e-mail | asking the endpoint twice for one account, or showing it twice |

**Nothing real is in here.** E-mails are `@example.com` / `@example.org`, and every
token carries the deliberate `sk-ant-fixture-` prefix — `scripts/check-fixtures.py`
allows exactly that prefix and flags anything else shaped like a live token.

**The timestamps are extremes on purpose: 2100 for live, 2020 for expired.** The
first version used a fixed stamp that was in the future *when it was written*; by
the time the fixtures ran, it had passed, so every token read as expired and the two
live cases quietly failed. A fixed timestamp does not stop a fixture drifting — only
a date that will never arrive does.

**Not a directory, so not here:** the WSL UNC path (`\\wsl.localhost\<distro>\home\
<user>\.claude`). It is a path *shape* the discovery must normalise, not a directory
that can be committed; it belongs in a unit test over `discover.nv` with the string
as input. Recorded here so its absence reads as a decision.
