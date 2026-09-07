# fixtures/usage — recorded endpoint replies

Inputs for `usage/parse.nv` and `usage/fetch.nv` (tasks T1.5, plan 01.5). Every file
is a reply of `GET https://api.anthropic.com/api/oauth/usage` with the shape kept and
the values replaced. **No real token, no real e-mail, no real account is in here** —
these fixtures are committed, and a fixture carrying a secret leaks it on every clone.

The shape is not invented: it is the live reply the reference tool receives
(`scripts/claude_limits.py`), with numbers and dates rewritten. Where a field's
meaning matters for the test, the file carries a `_comment` saying what the fixture
is FOR — a fixture whose point nobody remembers gets "fixed" by the next reader.

| file | what it pins | the mistake it catches |
|---|---|---|
| `normal.json` | the ordinary reply: three windows, `limits[]` present, nothing locked | — (the baseline every other file is read against) |
| `empty-limits-fallback.json` | `limits[]` empty; the numbers live only in `five_hour`/`seven_day` | a reader that trusts `limits[]` to be non-empty shows an account with no bars at all |
| `locked.json` | `locked_reason` filled, session at 100 %, severity `critical` | showing a bare 100 % instead of the reason, and treating a blocked account as a normal reading |
| `two-scoped-models.json` | TWO `weekly_scoped` rows, one of them with `resets_at: null` | drawing a fixed three bars: the count comes from `limits[]`, never from a constant |

The transport outcomes plan 01 §7 also asks for — 401, 500, a malformed body and
both shapes of 429 — live in [`fixtures/transport/`](../transport/README.md).
They are not reply bodies: status and headers carry their meaning, and the body is
empty or broken on purpose, so keeping them apart lets each fixture read as one
thing.

**`resets_at` can be `null`** even on a healthy window — it is absent until something
is spent in that window. Measured on a live account 2026-09-06, not assumed;
`two-scoped-models.json` carries the case so the formatter is forced to handle it.
