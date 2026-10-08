#!/usr/bin/env python3
"""Pack a built claude-limits.exe into the release zip and write SHA256SUMS.txt.

    python scripts/package_release.py --exe target/claude-limits.exe --out dist [--tag v0.1.0]

Before it packs anything it checks that the three places that name the version agree:
`claude-limits.exe --version`, `src/version.nv` and `nova.toml`; with --tag the tag
(minus its `v`) must be the same number too. A mismatch exits 1 and no zip is written --
this is the check the release workflow relies on. Then it writes

    <out>/claude-limits-<version>-windows-x64.zip   (a fixed list of files, nothing else)
    <out>/SHA256SUMS.txt                            (`sha256sum -c` format)

and reads both back to prove the zip holds exactly that list and the sum matches.
Prints the path of the release notes for the workflow to use. Stdlib only.
"""
import argparse
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The ONLY files that go into the zip, from the repository root. Anything else
# (keys, databases, the owner's claude-limits.toml) cannot get in by a stray glob.
EXTRAS = ["README.md", "LICENSE-MIT", "LICENSE-APACHE", "claude-limits.example.toml"]
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # same input -> same zip bytes


def fail(msg):
    print(f"package_release: {msg}", file=sys.stderr)
    sys.exit(1)


def source_version():
    m = re.search(r'fn version\(\) -> str => "([^"]+)"', (ROOT / "src/version.nv").read_text(encoding="utf-8"))
    if not m:
        fail("cannot find `fn version()` in src/version.nv")
    return m.group(1)


def manifest_version():
    m = re.search(r'^\[package\].*?^version\s*=\s*"([^"]+)"', (ROOT / "nova.toml").read_text(encoding="utf-8"), re.S | re.M)
    if not m:
        fail("cannot find the package version in nova.toml")
    return m.group(1)


def exe_version(exe):
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        fail(f"{exe} --version exited {out.returncode}")
    line = out.stdout.strip()
    m = re.fullmatch(r"claude-limits (\S+)", line)
    if not m:
        fail(f"unexpected --version output: {line!r}")
    return m.group(1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--tag", help="release tag, e.g. v0.1.0; must equal the version")
    a = ap.parse_args()

    if not a.exe.is_file():
        fail(f"no such file: {a.exe}")
    ver = exe_version(a.exe)
    for what, got in (("src/version.nv", source_version()), ("nova.toml", manifest_version())):
        if got != ver:
            fail(f"exe says {ver} but {what} says {got}")
    if a.tag is not None:
        if not a.tag.startswith("v") or a.tag[1:] != ver:
            fail(f"tag {a.tag!r} does not match the binary's version {ver!r}")
    notes = ROOT / "docs" / "release-notes" / f"{ver}.md"
    if not notes.is_file():
        fail(f"no release notes: {notes.relative_to(ROOT)}")

    base = f"claude-limits-{ver}-windows-x64"
    members = [("claude-limits.exe", a.exe)] + [(n, ROOT / n) for n in EXTRAS]
    for _, src in members:
        if not src.is_file():
            fail(f"missing: {src}")
    a.out.mkdir(parents=True, exist_ok=True)
    zpath = a.out / f"{base}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in members:
            zi = zipfile.ZipInfo(f"{base}/{name}", FIXED_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, src.read_bytes())
    digest = sha256(zpath)
    sums = a.out / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  {zpath.name}\n", encoding="utf-8", newline="\n")

    # Read back what was written, not what was meant to be.
    with zipfile.ZipFile(zpath) as z:
        if z.testzip() is not None:
            fail("zip is corrupt")
        names = sorted(z.namelist())
    want = sorted(f"{base}/{n}" for n, _ in members)
    if names != want:
        fail(f"zip holds {names}, expected {want}")
    line = sums.read_text(encoding="utf-8").split()
    if line != [sha256(zpath), zpath.name]:
        fail("SHA256SUMS.txt does not match the zip")

    print(f"version {ver}")
    print(f"zip     {zpath}  ({zpath.stat().st_size} bytes)")
    for n in names:
        print(f"  {n}")
    print(f"sha256  {digest}")
    print(f"notes   {notes.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
