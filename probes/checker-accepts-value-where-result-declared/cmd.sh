#!/usr/bin/env bash
# The finding is that this prints "ok". Both functions in probe.nv are ill-typed:
# `f` throws with no Fail in its signature, `g` returns a bare int where the
# signature declares Result. The checker reports neither.
#
# Run from a package that can resolve std (the probe is a module file, so it needs
# a package around it). Verified 2026-09-08 in nova-duckdb:
#
#   cp probe.nv <pkg>/src/probe_chk.nv && cd <pkg> && ./nova.sh check src/probe_chk.nv
#
# Observed:  ok: src/probe_chk.nv   PASS: 1  FAIL: 0
# Expected:  two errors -- E_* for the missing Fail, E_* for the type mismatch.
set -euo pipefail
echo "see the comment above: this probe is run inside a package checkout"
