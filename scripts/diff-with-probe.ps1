<#
.SYNOPSIS
  Differential: the Nova build against the Python reference (task T1.8).

.DESCRIPTION
  A thin wrapper on purpose. The parsing and normalisation live in
  scripts/diff_with_probe.py so that this and diff-with-probe.sh cannot drift into
  two different comparisons.

  Exit codes:
    0  the two tables agree
    1  they differ — the finding this script exists for
    2  could not compare (Nova side unbuilt or not implemented). Never 0.

.EXAMPLE
  .\scripts\diff-with-probe.ps1 fixtures\dirs\two-dirs-one-account\same-email-a
  .\scripts\diff-with-probe.ps1 --live $HOME\.claude
#>
$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "diff_with_probe.py"
& python $script @args
exit $LASTEXITCODE
