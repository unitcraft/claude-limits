# -*- coding: utf-8 -*-
"""The config resource is described twice. The two descriptions must agree.

    python scripts/check-config-shape.py

WHY. `GET /api/config` renders a document and `PUT /api/config` accepts one, and both
shapes are hand-written lists in the same file -- sixty `field_*` calls and forty-one
`k == "name"` branches. Nothing compares them. A settable key added to one and not the
other is invisible: rendered-but-not-accepted turns a legitimate edit into
`422 extra_forbidden`, and accepted-but-not-rendered means a person cannot see what
they just set.

WHAT THIS IS NOT SAYING, because the hunt report that led here said it and it is
wrong. The two shapes are NOT supposed to be identical:

  * the PUT body is PARTIAL by contract (01.3 line 437 -- "тело — частичное дерево
    config, сервер сливает его с текущим"), so no client ever PUTs a GET document
    back, and the pair does not have to round-trip;
  * SECRETS are write-only on purpose. `access_token` and `tls_key` are accepted and
    never rendered; GET answers `access_token_set` and `tls_key_set` instead. That is
    the correct shape for a secret, not a discrepancy;
  * DISCOVERED and DERIVED state is read-only on purpose. Found accounts, their
    e-mails, the etag, `restart_required` -- none of those are settings.

So the check is not "the sets are equal". It is "every difference is one somebody
named", which is the only version that can stay green without being useless.
"""
import io
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "server" / "handlers" / "config.nv"

# Rendered but deliberately NOT accepted, each with the reason it is read-only.
READ_ONLY = {
    "access_token_set": "derived from a write-only secret",
    "tls_key_set": "derived from a write-only secret",
    "accounts_found": "discovered, not configured",
    "dirs": "discovered login directories",
    "login_dirs": "discovered login directories",
    "email": "a discovered account's address",
    "org": "a discovered account's organisation",
    "id": "assigned by the server",
    "name": "derived from the path",
    "kind": "classified by the server",
    "source": "where a value came from, not a value",
    "hidden": "a property of a discovered account, set through hidden_accounts",
    "portable": "a fact about the installation, detected not chosen",
    "etag": "the version of the resource",
    "current": "the response's echo of the stored document",
    "applied": "what the write actually changed",
    "problem": "an error envelope",
    "restart_required": "a consequence of the write",
    "listener_reopened": "a consequence of the write",
    "new_base_url": "a consequence of the write",
    "config": "the wrapper key around the tree",
}

# Accepted but deliberately NOT rendered.
WRITE_ONLY = {
    "access_token": "a secret: settable, never readable back (GET gives access_token_set)",
    "tls_key": "a secret: settable, never readable back (GET gives tls_key_set)",
}

if not SRC.exists():
    print("CONFIG SHAPE: FAILED")
    print("   config.nv not found -- nothing was compared")
    sys.exit(1)

text = SRC.read_text(encoding="utf-8")
rendered = set(re.findall(r'field_[a-z0-9_]+\(\s*"([a-z0-9_]+)"', text))
accepted = set(re.findall(r'k\s*==\s*"([a-z0-9_]+)"', text))

print(f"rendered by GET: {len(rendered)}, accepted by PUT: {len(accepted)}")

# A comparison of two empty sets is agreement about nothing.
if not rendered or not accepted:
    print("CONFIG SHAPE: FAILED")
    print(f"   rendered={len(rendered)} accepted={len(accepted)} -- one of the "
          f"patterns stopped matching, so this check compared nothing")
    sys.exit(1)

bad = []

for name in sorted(rendered - accepted):
    if name not in READ_ONLY:
        bad.append(f"`{name}` is rendered by GET and NOT accepted by PUT, and is not "
                   f"listed as read-only. Either accept it, or add it to READ_ONLY in "
                   f"this file with the reason -- a person who can see a value and "
                   f"cannot set it needs to know that is deliberate.")

for name in sorted(accepted - rendered):
    if name not in WRITE_ONLY:
        bad.append(f"`{name}` is accepted by PUT and NEVER rendered, and is not listed "
                   f"as write-only. Either render it, or add it to WRITE_ONLY here -- "
                   f"a value one can set and never read back is a secret or a bug, and "
                   f"the file should say which.")

# A stale exception is worse than none: it licenses a difference that is already gone.
for name in sorted(READ_ONLY):
    if name not in rendered:
        bad.append(f"stale exception: `{name}` is listed as read-only but GET no "
                   f"longer renders it -- remove the entry")
for name in sorted(WRITE_ONLY):
    if name not in accepted:
        bad.append(f"stale exception: `{name}` is listed as write-only but PUT no "
                   f"longer accepts it -- remove the entry")

print("CONFIG SHAPE:", "clean" if not bad else "FAILED")
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
