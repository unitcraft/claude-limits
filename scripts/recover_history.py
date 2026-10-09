"""Offline reference-history recovery. Inputs are ordered oldest to current.

No CLI, database, credentials, network or refresh is accessed. Last input wins
at equal (series, instant); within an input, last row wins. Output keeps the
winning original timestamp and percent, sorted by UTC instant. Diagnostics never
include series names, input values or paths. Use private directories for outputs.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


class InvalidHistory(ValueError):
    pass


def instant(value):
    if isinstance(value, bool):
        raise InvalidHistory("invalid timestamp")
    if isinstance(value, (int, float)):
        if not 0 < value <= 253402300799 or not math.isfinite(value):
            raise InvalidHistory("invalid timestamp")
        seconds = Decimal(str(value))
        try:
            datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            raise InvalidHistory("invalid timestamp") from None
        return seconds
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise InvalidHistory("invalid timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        delta = dt.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        seconds = Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / 1000000
        if seconds <= 0:
            raise ValueError()
        return seconds
    except (ValueError, OverflowError):
        raise InvalidHistory("invalid timestamp") from None


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise InvalidHistory("duplicate JSON member")
        out[key] = value
    return out


def decode(body):
    try:
        root = json.loads(body, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise InvalidHistory("invalid JSON") from None
    if not isinstance(root, dict):
        raise InvalidHistory("history must be an object")
    for name, rows in root.items():
        series, sep, kind = name.rpartition("|")
        provider, colon, account = series.partition(":")
        if not sep or not kind or not colon or not account.strip() or provider not in ("claude", "kimi", "codex"):
            raise InvalidHistory("invalid series shape")
        if not isinstance(rows, list):
            raise InvalidHistory("series must be an array")
        for row in rows:
            if not isinstance(row, list) or len(row) != 2:
                raise InvalidHistory("point must be a pair")
            instant(row[0])
            pct = row[1]
            if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not 0 <= pct <= 100 or not math.isfinite(pct):
                raise InvalidHistory("invalid percent")
    return root


def utc(seconds):
    return datetime.fromtimestamp(float(seconds), timezone.utc).isoformat().replace("+00:00", "Z")


def merge(documents):
    points = {}
    total = duplicates = conflicts = 0
    for document in documents:
        for name, rows in document.items():
            series = points.setdefault(name, {})
            for row in rows:
                at = instant(row[0])
                total += 1
                if at in series:
                    duplicates += 1
                    conflicts += series[at][1] != row[1]
                series[at] = row
    result = {name: [rows[at] for at in sorted(rows)] for name, rows in sorted(points.items())}
    times = [at for rows in points.values() for at in rows]
    stats = {"sources": len(documents), "series": len(result), "input_points": total,
             "unique_points": len(times), "duplicates": duplicates, "conflicts": conflicts,
             "from_utc": utc(min(times)) if times else None,
             "to_utc": utc(max(times)) if times else None}
    return result, stats


def encoded(document):
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def atomic_write(path, body):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".recovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recover(paths, output=None, snapshot_dir=None):
    paths = [Path(p) for p in paths]
    if len(paths) < 2:
        raise InvalidHistory("at least two inputs required")
    if output and Path(output).resolve() in [p.resolve() for p in paths]:
        raise InvalidHistory("output must not be an input")
    bodies = [p.read_bytes() for p in paths]
    # Capture the bytes actually read, not a later daemon version of the file.
    # Exclusive names prevent overwriting earlier snapshots or source files.
    if snapshot_dir:
        directory = Path(snapshot_dir)
        directory.mkdir(parents=True, exist_ok=False)
        for index, body in enumerate(bodies):
            atomic_write(directory / f"source-{index:02d}.json", body)
    documents = [decode(body) for body in bodies]
    result, stats = merge(documents)
    if snapshot_dir:
        manifest = []
        for index, (body, doc) in enumerate(zip(bodies, documents)):
            _, counts = merge([doc])
            manifest.append({"snapshot": f"source-{index:02d}.json", "sha256": hashlib.sha256(body).hexdigest(),
                             "bytes": len(body), **counts})
        atomic_write(directory / "manifest.json", encoded({"sources": manifest, "merged": stats}))
    if output:
        atomic_write(output, encoded(result))
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="oldest first; current source LAST")
    parser.add_argument("--output", help="private merged JSON; omit for dry run")
    parser.add_argument("--snapshot-dir", help="new private directory for exact snapshots and hashes")
    args = parser.parse_args(argv)
    try:
        stats = recover(args.inputs, args.output, args.snapshot_dir)
    except (InvalidHistory, OSError):
        print("Recovery failed: invalid input or inaccessible path; merged output not written.")
        return 2
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
