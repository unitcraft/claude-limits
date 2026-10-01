# -*- coding: utf-8 -*-
"""Run the nova compiler for claude-limits -- always a COPY, never the one in the nova tree.

    python scripts/nova_run.py <nova arguments...>      (./nova.sh is this, one line)

WHY (2026-10-01). A running `nova.exe` holds its file, and the nova integrator's
`cargo build` cannot replace a held file: two rebuilds carrying a compiler fix failed
with "failed to remove file ... Access is denied" while this project's builds and tests
ran `../nova/nova-cli/target/release/nova.exe` directly. The binary is therefore copied
into `target/nova-bin/` whenever it differs from the tree's, and the copy is what runs.
`scripts/check-no-shared-compiler.py` holds the rule.

ONE DOOR, IN PYTHON, BY CONVENTION (the integrator, 2026-10-02): the copying used to be
written twice, in `nova.sh` and in a PowerShell twin, and two implementations of one rule
drift at the first edit. The shell wrapper is one line that calls this; the PowerShell
twin is gone.

The main nova repository is the sibling directory `nova` (override with
NOVA_MAIN_REPO). `NOVA_RUN_WHICH=1` prints the executable that would run and exits --
the guard asks it, rather than reading this file's text.
"""
import filecmp
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main_repo() -> pathlib.Path:
    env = os.environ.get("NOVA_MAIN_REPO")
    return pathlib.Path(env).resolve() if env else (ROOT.parent / "nova").resolve()


def tree_binary(m: pathlib.Path) -> pathlib.Path:
    for name in ("nova.exe", "nova"):
        p = m / "nova-cli" / "target" / "release" / name
        if p.is_file():
            return p
    sys.stderr.write(f"nova_run: nova binary not found under '{m}' -- set NOVA_MAIN_REPO to the nova checkout\n")
    sys.stderr.write("nova_run: build it with: cd \"$NOVA_MAIN_REPO/nova-cli\" && cargo build --release\n")
    sys.exit(1)


def fresh_copy(src: pathlib.Path) -> pathlib.Path:
    """The copy beside this repository, refreshed when the tree's binary changed."""
    copy_dir = ROOT / "target" / "nova-bin"
    copy = copy_dir / src.name
    if copy.is_file() and filecmp.cmp(src, copy, shallow=False):
        return copy
    copy_dir.mkdir(parents=True, exist_ok=True)
    # A private temporary name: two runs refreshing at once never see a half-written
    # binary, and the copy in use is replaced only by a whole one.
    tmp = copy_dir / f".{src.name}.{os.getpid()}"
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, copy)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        if not copy.is_file():
            sys.stderr.write(f"nova_run: could not copy the compiler to {copy_dir}\n")
            sys.exit(1)
        # Busy (another run uses the copy): keep it rather than fall back to the
        # tree's binary, which is the one file not to hold.
        sys.stderr.write("nova_run: the compiler copy is in use and was not refreshed; running the previous copy\n")
    return copy


def main(argv):
    m = main_repo()
    exe = fresh_copy(tree_binary(m))
    if os.environ.get("NOVA_RUN_WHICH") == "1":
        print(exe)
        return 0
    env = dict(os.environ)
    env["NOVA_STD_PATH"] = str(m / "std" / "src")
    env["NOVA_RT_DIR"] = str(m / "compiler-codegen" / "nova_rt")
    env["NOVA_CG_INCLUDE"] = str(m / "compiler-codegen")
    vcpkg = m / "compiler-codegen" / "vcpkg_installed" / "x64-windows-static"
    env["NOVA_GC_LIB_DIR"] = str(vcpkg / "lib")
    env["NOVA_INCLUDE_DIR"] = str(vcpkg / "include")
    env["NOVA_GC_INCLUDE_DIR"] = env["NOVA_INCLUDE_DIR"]
    return subprocess.run([str(exe)] + argv[1:], env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
