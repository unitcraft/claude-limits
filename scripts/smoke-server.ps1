<#
.SYNOPSIS
  Smoke test of `claude-limits --serve` (task T2.26).

.DESCRIPTION
  A thin wrapper on purpose, the twin of smoke-server.sh: the checks live in
  scripts/smoke_server.py so that the two entry points cannot drift into two
  different smoke tests. The binary runs against a fixture made on the spot, with
  its data directories redirected under a temporary directory -- the real profile
  of whoever runs it is not touched.

  Exit codes:
    0  every check passed
    1  a check failed
    2  could not run (no binary). Never 0.

.EXAMPLE
  .\scripts\smoke-server.ps1
  .\scripts\smoke-server.ps1 target\claude-limits.exe
#>
$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "smoke_server.py"
& python $script @args
exit $LASTEXITCODE
