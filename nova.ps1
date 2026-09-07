<#
.SYNOPSIS
  Build wrapper for claude-limits: supplies the environment `nova` needs to find
  std and the runtime, then forwards every argument to the compiler.

.DESCRIPTION
  The main nova repository is located relative to THIS script (sibling directory
  `nova`), so the wrapper works on any checkout that keeps the siblings together.
  Override with the NOVA_MAIN_REPO environment variable if your layout differs.

  PowerShell twin of nova.sh — same variables, same forwarding.

.EXAMPLE
  .\nova.ps1 build --mode release bin/claude_limits.nv -o target/claude-limits.exe
  .\nova.ps1 test bin/
  .\nova.ps1 check bin/claude_limits.nv
#>
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
if ($env:NOVA_MAIN_REPO) { $M = $env:NOVA_MAIN_REPO } else { $M = Join-Path $here "..\nova" }
if (-not (Test-Path $M)) {
    Write-Error "nova.ps1: nova checkout not found at '$M' - set NOVA_MAIN_REPO"
    exit 1
}
$M = (Resolve-Path $M).Path

$novaBin = Join-Path $M "nova-cli\target\release\nova.exe"
if (-not (Test-Path $novaBin)) {
    Write-Error "nova.ps1: nova.exe not found at '$novaBin' - build it with: cd $M\nova-cli; cargo build --release"
    exit 1
}

$env:NOVA_STD_PATH       = Join-Path $M "std\src"
$env:NOVA_RT_DIR         = Join-Path $M "compiler-codegen\nova_rt"
$env:NOVA_CG_INCLUDE     = Join-Path $M "compiler-codegen"
$env:NOVA_GC_LIB_DIR     = Join-Path $M "compiler-codegen\vcpkg_installed\x64-windows-static\lib"
$env:NOVA_INCLUDE_DIR    = Join-Path $M "compiler-codegen\vcpkg_installed\x64-windows-static\include"
$env:NOVA_GC_INCLUDE_DIR = $env:NOVA_INCLUDE_DIR

& $novaBin @args
exit $LASTEXITCODE
