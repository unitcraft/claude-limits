import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import recover_history as recovery


NAME = "claude:fixture@example.com|session"


class RecoveryTests(unittest.TestCase):
    def test_union_keeps_older_backup_orders_and_current_wins(self):
        old = recovery.decode(json.dumps({NAME: [[172800, 12.5], [86400, 7], [172800, 12.5]]}))
        current = recovery.decode(json.dumps({NAME: [["1970-01-03T01:00:00+01:00", 22.25], [259200, 30]]}))
        merged, stats = recovery.merge([old, current])
        self.assertEqual(merged[NAME], [[86400, 7], ["1970-01-03T01:00:00+01:00", 22.25], [259200, 30]])
        self.assertEqual((stats["unique_points"], stats["duplicates"], stats["conflicts"]), (3, 2, 1))
        self.assertEqual(stats["from_utc"], "1970-01-02T00:00:00Z")
        reversed_result, _ = recovery.merge([current, old])
        self.assertEqual(reversed_result[NAME][1], [172800, 12.5])
        latest_only, _ = recovery.merge([current])
        self.assertNotEqual(latest_only, merged)
        self.assertEqual(recovery.encoded(merged), recovery.encoded(recovery.merge([old, current])[0]))

    def test_empty_and_multiple_providers(self):
        docs = [recovery.decode('{}'), recovery.decode(json.dumps({
            "kimi:fixture|month limit": [[86400.125, 0]],
            "codex:fixture|weekly limit": [["1970-01-02T00:00:00.125Z", 100]], NAME: []}))]
        result, stats = recovery.merge(docs)
        self.assertEqual(stats["unique_points"], 2)
        self.assertEqual(result[NAME], [])
        self.assertIsNone(recovery.merge([{}, {}])[1]["from_utc"])

    def test_invalid_shapes_times_and_percent(self):
        bad = ['[]', 'null', '{', '{"x": [], "x": []}', '{"x": []}',
               json.dumps({NAME: {}})]
        for row in [[1], [True, 1], [0, 1], [-1, 1], [1e100, 1],
                    ["2026-02-30T00:00:00Z", 1], ["2026-01-01", 1],
                    ["2026-01-01T00:00:00", 1], [86400, True], [86400, -1],
                    [86400, 101], [86400, float('nan')], [86400, float('inf')], [86400, "1"]]:
            bad.append(json.dumps({NAME: [row]}))
        for body in bad:
            with self.subTest(body=body), self.assertRaises(recovery.InvalidHistory):
                recovery.decode(body)

    def test_read_only_snapshots_dry_run_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / 'old.json', root / 'current.json']
            paths[0].write_bytes(recovery.encoded({NAME: [[86400, 12.5]]}))
            paths[1].write_bytes(recovery.encoded({NAME: [[172800, 30]]}))
            before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
            out = root / 'merged.json'
            stats = recovery.recover(paths, snapshot_dir=root / 'snapshots')
            self.assertFalse(out.exists())
            self.assertEqual(stats["unique_points"], 2)
            for index, p in enumerate(paths):
                self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns), before[index])
                self.assertEqual((root / 'snapshots' / f'source-{index:02d}.json').read_bytes(), before[index][0])
            manifest = json.loads((root / 'snapshots' / 'manifest.json').read_bytes())
            self.assertEqual(manifest['sources'][0]['sha256'], hashlib.sha256(before[0][0]).hexdigest())
            recovery.recover(paths, out)
            first = out.read_bytes()
            recovery.recover(paths, out)
            self.assertEqual(out.read_bytes(), first)
            with self.assertRaises(recovery.InvalidHistory):
                recovery.recover(paths, paths[0])
            paths[1].write_text('[]')
            with self.assertRaises(recovery.InvalidHistory):
                recovery.recover(paths, out)
            self.assertEqual(out.read_bytes(), first)
            with self.assertRaises(recovery.InvalidHistory):
                recovery.recover(paths, root / 'absent.json')
            self.assertFalse((root / 'absent.json').exists())
            with self.assertRaises(recovery.InvalidHistory):
                recovery.recover(paths[:1])


if __name__ == '__main__':
    unittest.main()
