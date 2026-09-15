<#
.SYNOPSIS
  Starts the claude-limits reference daemon: a snapshot of every login's
  usage limits every interval (default 300 s, from claude-limits.toml).

.DESCRIPTION
  Foreground by default: output goes to this console, Ctrl+C stops it.
  -Detached starts a hidden python process and returns; its output goes to
  claude-limits.log (stderr to claude-limits.err.log) in the repository root.
  The PID is printed; stop it with `Stop-Process -Id <pid>`.

.PARAMETER Config
  Path to the TOML config. Default: claude-limits.toml in the repository root.

.PARAMETER Interval
  Seconds between snapshots. Overrides interval_sec from the config.

.PARAMETER BarStyle
  Progress bar glyphs: "blocks" [████░░░░] or "ascii" [####....].

.PARAMETER Color
  Colour output: "auto" (default), "always" or "never".

.PARAMETER NoAutoRefresh
  Do not renew an expired login, just report it. The daemon renews one by
  starting Claude Code under it (owner's decision 2026-09-16), and that costs a
  small request on THAT account's own limits -- so a run that must spend nothing
  but its own readings turns this on. The same switch lives in the config as
  `auto_refresh = false`; this flag wins over it.

.PARAMETER Detached
  Run hidden in the background, logging to files.

.EXAMPLE
  .\scripts\start-daemon.ps1
  .\scripts\start-daemon.ps1 -Interval 60
  .\scripts\start-daemon.ps1 -BarStyle ascii
  .\scripts\start-daemon.ps1 -Detached
  .\scripts\start-daemon.ps1 -NoAutoRefresh
#>
param(
    [string]$Config,
    [int]$Interval,
    [ValidateSet("blocks", "ascii")]
    [string]$BarStyle,
    [ValidateSet("auto", "always", "never")]
    [string]$Color,
    [switch]$NoAutoRefresh,
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "claude_limits.py"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { Write-Error "python not found in PATH (3.11+ needed for the TOML config)"; exit 1 }
$python = $pythonCmd.Source

$argList = @($script, "--daemon")
if ($Config)   { $argList += @("--config", $Config) }
if ($Interval) { $argList += @("--interval", "$Interval") }
if ($BarStyle) { $argList += @("--bar-style", $BarStyle) }
if ($Color)    { $argList += @("--color", $Color) }
if ($NoAutoRefresh) { $argList += "--no-auto-refresh" }

if ($Detached) {
    $log = Join-Path $root "claude-limits.log"
    $err = Join-Path $root "claude-limits.err.log"
    $p = Start-Process -FilePath $python -ArgumentList $argList -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    Write-Host "claude-limits daemon started, pid $($p.Id); log: $log"
    Write-Host "stop: Stop-Process -Id $($p.Id)"
} else {
    & $python @argList
    exit $LASTEXITCODE
}
