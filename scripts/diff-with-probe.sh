#!/usr/bin/env bash
# Differential: the Nova build against the Python reference (task T1.8).
#
# A thin wrapper on purpose. The parsing and normalisation live in
# scripts/diff_with_probe.py so that the shell and PowerShell entry points cannot
# drift into two different comparisons — the class this project keeps meeting is
# two copies of one rule ageing apart.
#
# Exit codes, and the middle one is the point:
#   0  the two tables agree
#   1  they differ — the finding this script exists for
#   2  could not compare (Nova side unbuilt or not implemented). NEVER 0: an
#      unbuilt side must not read as agreement.
#
# Usage:
#   ./scripts/diff-with-probe.sh fixtures/dirs/two-dirs-one-account/same-email-a
#   ./scripts/diff-with-probe.sh --live ~/.claude          # calls the endpoint, twice
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python "$HERE/diff_with_probe.py" "$@"
