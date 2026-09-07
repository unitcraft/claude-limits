#!/usr/bin/env bash
# Build wrapper for claude-limits: supplies the environment `nova` needs to find
# std and the runtime, then forwards every argument to the compiler.
#
# The main nova repository is located RELATIVE TO THIS SCRIPT (sibling directory
# `nova`), so the wrapper works on any checkout that keeps the siblings together.
# Override with NOVA_MAIN_REPO if your layout differs.
#
# Unlike the sibling packages, this wrapper IS committed: the acceptance of every
# task runs `./nova.sh …`, and a fresh clone that cannot run the acceptance is the
# same defect that kept the reference tool out of git.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
M="${NOVA_MAIN_REPO:-$(cd "$HERE/../nova" 2>/dev/null && pwd)}"

NOVA_BIN="$M/nova-cli/target/release/nova.exe"
[ -x "$NOVA_BIN" ] || NOVA_BIN="$M/nova-cli/target/release/nova"
[ -x "$NOVA_BIN" ] || {
    echo "nova.sh: nova binary not found under '$M' — set NOVA_MAIN_REPO to the nova checkout" >&2
    echo "nova.sh: build it with: cd \"\$NOVA_MAIN_REPO/nova-cli\" && cargo build --release" >&2
    exit 1
}

export NOVA_STD_PATH="$M/std/src"
export NOVA_RT_DIR="$M/compiler-codegen/nova_rt"
export NOVA_CG_INCLUDE="$M/compiler-codegen"
export NOVA_GC_LIB_DIR="$M/compiler-codegen/vcpkg_installed/x64-windows-static/lib"
export NOVA_INCLUDE_DIR="$M/compiler-codegen/vcpkg_installed/x64-windows-static/include"
export NOVA_GC_INCLUDE_DIR="$NOVA_INCLUDE_DIR"

exec "$NOVA_BIN" "$@"
