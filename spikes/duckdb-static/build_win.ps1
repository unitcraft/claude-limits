# DuckDB static build + spike on Windows (clang-cl /MT, lld-link), as run on 2026-09-06.
# Prereqs: LLVM (clang-cl, llvm-lib, lld-link), Visual Studio 2022 Build Tools (vcvars64.bat),
# libduckdb-src.zip from https://github.com/duckdb/duckdb/releases (v1.5.5, 4.97 MB) unpacked here.
param(
  [string]$VcVars = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
  [string]$Llvm = "C:\Program Files\LLVM\bin"
)
$dir = $PSScriptRoot
$sw = [Diagnostics.Stopwatch]::StartNew()
# 1. the amalgamation as one static library. WIN32_LEAN_AND_MEAN/NOMINMAX are mandatory: windows.h
#    otherwise defines `interface`, which DuckDB uses as an identifier. ~11 min, ~3.5 GB RAM.
cmd /c "call ""$VcVars"" >nul 2>&1 && cd /d ""$dir"" && ""$Llvm\clang-cl.exe"" /c /O2 /MT /EHsc /std:c++17 /bigobj /DNDEBUG /DDUCKDB_STATIC_BUILD /DWIN32_LEAN_AND_MEAN /DNOMINMAX /D_CRT_SECURE_NO_WARNINGS /w duckdb.cpp /Foduckdb.obj && ""$Llvm\llvm-lib.exe"" /out:duckdb_static.lib duckdb.obj"
"library: exit=$LASTEXITCODE, $([int]$sw.Elapsed.TotalSeconds) s"
# 2. the C spike. DuckDB pulls in the Restart Manager (rstrtmgr) and Winsock on Windows.
cmd /c "call ""$VcVars"" >nul 2>&1 && cd /d ""$dir"" && ""$Llvm\clang-cl.exe"" /O2 /MT /DDUCKDB_STATIC_BUILD /I. spike.c duckdb_static.lib ws2_32.lib bcrypt.lib advapi32.lib shell32.lib ole32.lib rstrtmgr.lib -fuse-ld=lld /Fespike.exe"
"spike.exe {0:N2} MB" -f ((Get-Item "$dir\spike.exe").Length/1MB)
foreach ($f in Get-ChildItem $dir -Filter "spike.duckdb*") { [IO.File]::Delete($f.FullName) }
foreach ($label in "cold","warm") {
  $t = Measure-Command { $script:out = cmd /c """$dir\spike.exe"" ""$dir\spike.duckdb"" 2>&1" }
  "--- $label : process wall {0:N0} ms" -f $t.TotalMilliseconds; $out
}
# 3. CRT check: no vcruntime/msvcp/ucrtbase among the imports means the CRT is fully static.
& "$Llvm\llvm-readobj.exe" --coff-imports "$dir\spike.exe" | Select-String "^\s*Name:" | ForEach-Object { $_.ToString().Trim() }
# 4. Nova link check: novapkg\ with [ffi] libs = ["duckdb_static"]; needs NOVA_STD_PATH, NOVA_CG_INCLUDE, NOVA_RT_DIR
#    (see nova-tls README "Building standalone"), then: nova build --mode release novapkg\spike.nv -o duckspike.exe
