"""Prove the directory fixtures work by running the REFERENCE tool's discovery on them.

Only the pure half is exercised — read_login / accounts_of. fetch_usage is never
called: the fixtures carry deliberately fake tokens, and firing them at the endpoint
would earn 401s and then a 429 for the whole machine, which is how today's rate
limiting started.
"""
import pathlib, sys

repo = pathlib.Path(r"<repos>\claude-limits")
sys.path.insert(0, str(repo / "scripts"))
import claude_limits as ref

ref.fetch_usage = lambda tok: (_ for _ in ()).throw(
    AssertionError("network must not be touched by this verification"))

dirs = repo / "fixtures" / "dirs"
cases = {
    "default layout (.claude.json BESIDE .claude/)": [dirs / "default-layout" / ".claude"],
    "CLAUDE_CONFIG_DIR layout (both files inside)": [dirs / "config-dir-layout" / "work"],
    "no login at all": [dirs / "no-login"],
    "expired token": [dirs / "expired"],
    "two dirs, one account": [dirs / "two-dirs-one-account" / "same-email-a",
                              dirs / "two-dirs-one-account" / "same-email-b"],
}

fail = 0
for title, paths in cases.items():
    accounts = ref.accounts_of(paths)
    print(f"\n{title}")
    print(f"  dirs given: {len(paths)}  ->  accounts found: {len(accounts)}")
    for a in accounts:
        state = "stale (no live token)" if a["token"] is None else "has a live token"
        print(f"    label : {a['label']}")
        print(f"    dirs  : {a['dirs']}   expired dirs: {a['expired_dirs']}   {state}")

    # The properties each fixture exists to pin.
    if title.startswith("no login"):
        if accounts:
            print("  FAIL: a directory without .credentials.json produced an account"); fail += 1
    elif title.startswith("expired"):
        if len(accounts) != 1 or accounts[0]["token"] is not None:
            print("  FAIL: an expired token must yield an account with NO live token"); fail += 1
    elif title.startswith("two dirs"):
        if len(accounts) != 1:
            print(f"  FAIL: two dirs with one e-mail must group into ONE account, got {len(accounts)}"); fail += 1
        elif len(accounts[0]["dirs"]) != 2:
            print("  FAIL: the single account must list BOTH directories"); fail += 1
    else:
        if len(accounts) != 1 or accounts[0]["token"] is None:
            print("  FAIL: expected exactly one account with a live token"); fail += 1

print("\nRESULT:", "all directory fixtures behave as the plan says" if not fail else f"{fail} FAILURE(S)")
sys.exit(1 if fail else 0)
