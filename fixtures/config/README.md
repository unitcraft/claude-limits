# fixtures/config — configuration files the validator is judged by

Inputs for `config.nv` (task T1.2, plan 01.5). One file per case; each header says
what it pins and what the validator must answer.

| file | what it pins | expected answer |
|---|---|---|
| `full-valid.toml` | every key from the inventory with its default | loads, no errors, no warnings |
| `interval-too-low.toml` | a poll interval below the floor | RAISED to 60 with one warning — not an error |
| `lan-before-phase6.toml` | `allow_lan = true` before phase 6 | `422` on `server.allow_lan`, listener stays on loopback |
| `unknown-key.toml` | a typo in a key name | `422` `extra_forbidden` naming the exact path |
| `two-errors.toml` | two faults in one file | TWO entries in `errors[]`, in file order |

**All five are syntactically valid TOML on purpose.** The faults are semantic —
values and names the validator must judge — because a file that fails to parse
tests the TOML library, not our rules. Verified: `tomllib` loads all five.

`full-valid.toml` is generated, not hand-written: `scripts/check-config-fixture.py`
compares it against `docs/reports/T1.2-config-inventory.md` in both directions —
every inventory key present (nothing lost) and no key absent from the inventory
(nothing invented). Currently 35 keys, 29 with a default and 6 without; the six
without are written as commented lines so their order is still visible.

**When the inventory changes, this file has to be regenerated and the check re-run**
— otherwise the "complete" fixture quietly stops being complete, which is the same
failure the inventory itself uncovered in the plan: a section that called itself the
full list of keys while missing two.
