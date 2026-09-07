# fixtures/transport — what the endpoint does other than answer

Inputs for `usage/fetch.nv` (task T1.5). Each file describes a whole HTTP outcome —
status, headers, body — for the mock `Http` handler to replay, so the error paths
are exercised without a network and without a real token.

| file | outcome | the state it must produce |
|---|---|---|
| `rate-limited-with-retry-after.json` | 429 + `Retry-After: 120` | `unknown`, next poll in 120 s — the server's number, not our floor |
| `rate-limited-no-header.json` | 429, no header | `unknown`, next poll in 60 s — the floor, and the message says no header was given |
| `unauthorized.json` | 401 | `stale`, reason "token rejected"; the next cycle must not retry faster |
| `server-error.json` | 500 | `unknown` — never `stale`: the fault is the server's and the user has nothing to fix |
| `malformed-body.json` | 200, truncated JSON | `unknown`, no panic, and the other accounts in the cycle still report |

**Why these are not in `fixtures/usage/`.** Those files are reply BODIES — what the
endpoint says when it answers. These are what happens when it answers with something
else, or does not answer at all: status and headers carry the meaning, and the body
is often empty or broken on purpose. Splitting them keeps each fixture readable as
one thing, and it keeps the body parser's tests from pretending to test transport.

Plan 01 §7 lists all of these under "Фикстуры" together with the body cases; the
split into two directories is a refinement made while writing them, and the plan
now points here for the transport half.

**The two hardest expectations are recorded on purpose, because they are easy to get
backwards:**

- a 500 must NOT mark the account stale. Stale means "your token needs attention";
  a server fault needs none, and telling the user to re-login because Anthropic had
  a bad minute is a lie the interface would keep repeating.
- a malformed body must not blank the page. The endpoint is undocumented and may
  change shape at any time; the previous reading with its age is more useful than an
  empty panel, and far more useful than a crash.

Nothing real is in here: no token, no e-mail, no path.
