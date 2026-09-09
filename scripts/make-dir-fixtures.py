"""Build fixtures/dirs/* for task T1.3 (account discovery).

Every case the plan names in §7 "Каталоги", as real directories a test can point
at. Nothing real: e-mails are @example.com/@example.org, tokens carry the
deliberate `sk-ant-fixture-` prefix, home paths use the user `me`.
"""
import json, pathlib, time

base = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "dirs"  # derived, never written out: an absolute default means a copy of the
  # repository acts on the ORIGINAL (same reasoning as check-plan-trees.py)

HOUR = 3600 * 1000

# A fixture pinning "not expired" must use a moment that will NEVER arrive, and one
# pinning "expired" a moment long past. My first version took a fixed stamp that was
# in the future WHEN I WROTE IT — and it had already gone by, so every fixture read
# as expired and the two live cases failed their own check. Fixed timestamps do not
# stop a fixture drifting; only extremes do.
LIVE_MS = 4_102_444_800_000     # 2100-01-01, comfortably beyond any test run
DEAD_MS = 1_577_836_800_000     # 2020-01-01, comfortably behind one


def creds(token_tail, expires_ms, sub="team", tier="default_claude_max_5x"):
    return {
        "claudeAiOauth": {
            "accessToken": f"sk-ant-fixture-{token_tail}",
            "refreshToken": f"sk-ant-fixture-refresh-{token_tail}",
            "expiresAt": expires_ms,
            "refreshTokenExpiresAt": expires_ms + 30 * 24 * HOUR,
            "scopes": ["user:inference", "user:profile"],
            "subscriptionType": sub,
            "rateLimitTier": tier,
        }
    }


def ident(email, org):
    return {"oauthAccount": {"emailAddress": email, "organizationName": org}}


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


made = []

# 1. Default layout: .claude.json sits BESIDE the .claude directory.
d = base / "default-layout"
made.append(write(d / ".claude.json", ident("solo@example.com", "Example Org")))
made.append(write(d / ".claude" / ".credentials.json", creds("default01", LIVE_MS)))

# 2. CLAUDE_CONFIG_DIR layout: both files INSIDE the named directory.
d = base / "config-dir-layout" / "work"
made.append(write(d / ".claude.json", ident("work@example.org", "Work Org")))
made.append(write(d / ".credentials.json", creds("work01", LIVE_MS)))

# 3. A directory with no login at all: discovery must skip it silently.
d = base / "no-login"
d.mkdir(parents=True, exist_ok=True)
(d / "README.txt").write_text(
    "No .credentials.json here on purpose: discovery must skip this directory\n"
    "without an error and without counting it as an account.\n", encoding="utf-8")
made.append(d / "README.txt")

# 4. Expired token: expiresAt in the past. The poller must NOT send it.
d = base / "expired"
made.append(write(d / ".claude.json", ident("stale@example.com", "Example Org")))
made.append(write(d / ".credentials.json", creds("expired01", DEAD_MS)))

# 5. Two directories, ONE account: grouped into one, both dirs listed, asked once.
for name, tail in (("same-email-a", "dupa01"), ("same-email-b", "dupb01")):
    d = base / "two-dirs-one-account" / name
    made.append(write(d / ".claude.json", ident("shared@example.com", "Example Org")))
    made.append(write(d / ".credentials.json", creds(tail, LIVE_MS)))

print(f"created {len(made)} files")
for m in sorted(made):
    print("  ", m.relative_to(base.parent.parent).as_posix())
