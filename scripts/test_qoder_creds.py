"""Qoder credential path offline regressions; python -m unittest discover -s scripts -p test_qoder_creds.py.

Task 035. The cipher here is Qoder's own (a WASM module inside qodercli, key =
machine_id[:16]), so the vectors are the whole case: the blob the WASM itself
built (fixtures/usage/qoder-blob.json, the oracle run over synthetic input),
a Python round trip, and the refused wrong machine. Two implementations
agreeing on the same committed bytes is what makes the pair trustworthy.
"""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

import claude_limits as ref


REPO = Path(__file__).resolve().parent.parent
# A synthetic machine id: the first 16 characters are the key the WASM takes.
MACHINE_ID = "0192f3a4-0000-7000-8000-0000000000c1"
PLAINTEXT = '{"uid":"u-1","login_method":"browser","access_token":"qoder-fixture-access"}'


class WasmOracleBlobTest(unittest.TestCase):
    def test_roundtrip_wasm_oracle(self):
        """Encrypted by qodercli's own WASM (the oracle run over synthetic
        input, committed as a fixture), the Python side must decrypt it: the
        two agree on the primitive, the framing and the key cut."""
        blob_doc = json.loads((REPO / "fixtures" / "usage" / "qoder-blob.json")
                              .read_text(encoding="utf-8"))
        got = ref.qoder_decrypt(blob_doc["blob"], blob_doc["machine_id"])
        self.assertEqual(got, blob_doc["plaintext"])


class RoundTripTest(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        blob = ref.qoder_encrypt(PLAINTEXT, MACHINE_ID)
        self.assertEqual(ref.qoder_decrypt(blob, MACHINE_ID), PLAINTEXT)

    def test_wrong_machine_refused(self):
        # The wrong machine differs inside the FIRST 16 characters -- that is
        # the key zone; ids differing only in the tail share the key and open
        # each other's stores (and the WASM behaves the same way).
        blob = ref.qoder_encrypt(PLAINTEXT, MACHINE_ID)
        with self.assertRaises(ValueError):
            ref.qoder_decrypt(blob, "0192f3a5-0000-7000-8000-0000000000c2")


class PrimitiveVectorTest(unittest.TestCase):
    """The AES core on its own, before any framing: FIPS-197 (one block) and
    SP 800-38A F.2.1 (the CBC chain) -- so a framing bug cannot hide a cipher
    bug, and the published numbers pin both key halves of the round trip."""

    def test_fips197_block(self):
        key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        words = ref._expand_key(key)
        block = bytes.fromhex("00112233445566778899aabbccddeeff")
        ct = ref._encrypt_block(words, block)
        self.assertEqual(ct.hex(), "69c4e0d86a7b0430d8cdb78070b4c55a")
        self.assertEqual(bytes(ref._decrypt_block(words, ct)).hex(),
                         "00112233445566778899aabbccddeeff")

    def test_sp800_38a_cbc(self):
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        iv = bytes(range(16))
        pt = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")
        ct = ref._cbc_encrypt(ref._expand_key(key), pt, iv)
        self.assertEqual(ct.hex(), "7649abac8119b246cee98e9b12e9197d")
        self.assertEqual(ref._cbc_decrypt(ref._expand_key(key), ct, iv), pt)


class RowsTest(unittest.TestCase):
    def test_fixture_row(self):
        usage = json.loads((ref.REPO_ROOT / "fixtures" / "usage" / "qoder.json")
                           .read_text(encoding="utf-8"))
        rows = list(ref.qoder_rows_of(usage))
        self.assertEqual(len(rows), 1)
        kind, pct, sev, reset, epoch = rows[0]
        self.assertEqual(kind, "quota")
        self.assertAlmostEqual(pct, 42.0)
        self.assertIsNone(sev)
        self.assertEqual(epoch, 1793462400)
        self.assertIn("(", reset)   # "when (time left)" shape of every row

    def test_no_rows_without_total(self):
        self.assertEqual(list(ref.qoder_rows_of({"code": 0, "data": {}})), [])
        self.assertEqual(list(ref.qoder_rows_of({})), [])
        self.assertEqual(list(ref.qoder_rows_of({"code": 3001, "msg": "parameter error"})), [])

    def test_no_rows_for_any_non_zero_code_including_200(self):
        # The acceptance's finding: a code that LOOKS like success must still be
        # an error shape -- qoder_rows_of reads nothing from it, so the caller's
        # gate refuses the reply before the live paint and the stale rows stay.
        # The live wire carries no code at all on success; anything non-zero
        # (200 included) is the server's error envelope.
        for code in (200, 401, 3001):
            self.assertEqual(list(ref.qoder_rows_of({"code": code, "msg": "x"})), [],
                             f"code {code}")


class SeriesTest(unittest.TestCase):
    def test_quota_rows_are_recorded_with_their_own_forecast_class(self):
        self.assertEqual(ref.kind_class_of("quota"), "monthly")
        mark = datetime.fromtimestamp(1793400000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        history = {}
        ref.record_sample(history, "qoder:me@example.com", "quota", 42.0, 1793400000)
        self.assertEqual(history, {"qoder:me@example.com|quota": [[mark, 42.0]]})


class PlanTest(unittest.TestCase):
    def test_fixture_plan(self):
        reply = json.loads((ref.REPO_ROOT / "fixtures" / "usage" / "qoder-plan.json")
                           .read_text(encoding="utf-8"))
        plan = ref.qoder_active_plan(reply)
        self.assertEqual(plan["name"], "QODER FIXTURE PLAN")
        line = ref.qoder_plan_line(plan, now=1793400000)
        self.assertTrue(line.startswith("plan: QODER FIXTURE PLAN, ends "))
        self.assertIn("(", line)

    def test_no_plan(self):
        self.assertIsNone(ref.qoder_active_plan({"code": 0, "data": {}}))
        self.assertIsNone(ref.qoder_plan_line(None))


class ConfigTest(unittest.TestCase):
    def test_qoder_kind_accepted(self):
        self.assertEqual(ref.kinded([{"dir": "~/.qoder", "kind": "qoder"}]),
                         [("~/.qoder", "qoder", False)])
        self.assertIn("qoder", ref.LOGIN_KINDS)


if __name__ == "__main__":
    unittest.main()
