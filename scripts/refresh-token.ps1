<#
.SYNOPSIS
  Refreshes the stored token of one or more Claude Code logins, by hand.

.DESCRIPTION
  A WRAPPER, NOT AN IMPLEMENTATION. The refresh itself lives in
  `scripts/refresh_token.py`, because the daemon calls it too (owner's decision,
  2026-09-16) and two implementations of one operation drift apart on the first
  edit. This file exists so the operation keeps a PowerShell door beside
  `start-daemon.ps1`; everything it does, `python scripts/refresh_token.py`
  does.

  What the refresh does and why it is shaped that way -- never touching
  `.credentials.json`, dispatching Windows and WSL directories differently,
  judging by the file's mtime rather than by an exit code -- is documented at
  the top of that module, in one place.

.PARAMETER Dir
  One or more config directories to refresh.

.PARAMETER All
  Every directory the daemon watches.

.PARAMETER Config
  TOML config used by -All. Default: claude-limits.toml in the repository root.

.PARAMETER Model
  Model for the throwaway request.

.PARAMETER TimeoutSec
  Limit per directory.

.EXAMPLE
  .\scriptsefresh-token.ps1 -All
  .\scriptsefresh-token.ps1 -Dir '\wsl.localhost\MGTS-KARKAS\home\karkas\.claude'
  .\scriptsefresh-token.ps1 -Dir C:\accountspx -TimeoutSec 60
#>
param(
    [string[]]$Dir,
    [switch]$All,
    [string]$Config,
    [string]$Model,
    [int]$TimeoutSec
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "refresh_token.py"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { Write-Error "python not found in PATH (3.11+ needed for the TOML config)"; exit 1 }

$argList = @($script)
if ($Dir)        { $argList += $Dir }
if ($All)        { $argList += "--all" }
if ($Config)     { $argList += @("--config", $Config) }
if ($Model)      { $argList += @("--model", $Model) }
if ($TimeoutSec) { $argList += @("--timeout", "$TimeoutSec") }

& $pythonCmd.Source @argList
exit $LASTEXITCODE
