#!/usr/bin/env bash
# Smoke test of `claude-limits --serve` (task T2.26, the part that exists).
#
# A thin wrapper, like diff-with-probe.sh: the checks live in scripts/smoke_server.py
# so that a shell and a PowerShell entry point cannot drift into two different smoke
# tests. Exit codes: 0 all passed, 1 a check failed, 2 could not run -- never 0 for
# an unbuilt binary.
#
# Usage:
#   ./scripts/smoke-server.sh                        # target/claude-limits.exe
#   ./scripts/smoke-server.sh path/to/claude-limits.exe
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$HERE/smoke_server.py" "$@"
