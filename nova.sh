#!/usr/bin/env bash
# Build wrapper for claude-limits: the acceptance of every task runs `./nova.sh …`.
# The work -- a COPY of the compiler, never the one in the nova tree, and the
# environment it needs -- is in scripts/nova_run.py, one door in Python.
exec python "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/nova_run.py" "$@"
