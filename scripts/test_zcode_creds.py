"""ZCode credential path offline regressions; python -m unittest discover -s scripts -p test_zcode_creds.py.

The AES-256-GCM here is implemented by hand (the stdlib has no GCM and the
project admits no dependencies, plan 01.8), so the vectors are the whole
case: the published FIPS-197 block vector, NIST SP 800-38D GCM vectors, and
one blob encrypted by NODE (the independent implementation ZCode itself
uses) that the Python side must decrypt -- two implementations agreeing on
the same bytes is what makes the committed constant trustworthy.
"""
import base64
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import claude_limits as ref


NODE_BLOB_SECRET = "zcode-credential-fallback:win32:C:\\Users\\me:me"
NODE_BLOB_VALUE = ("enc:v1:ABEiM0RVZneImaq7.JbJY0TTnSmaKHOE4psJmPQ."
                   "EPFwkziZz7Pd7aoZ3_tboMpbyvOOy0lWvZ7JksehX8f8AuMT")
NODE_BLOB_PLAINTEXT = "zcode-fixture-token-0123456789abcdef"


class AesBlockTest(unittest.TestCase):
    def test_fips197_c3_block(self):
        """The published AES-256 vector: key 000102..1f, pt 00112233..eeff."""
        words = ref._expand_key(bytes(range(32)))
        ct = ref._encrypt_block(words, bytes.fromhex("00112233445566778899aabbccddeeff"))
        self.assertEqual(ct, bytes.fromhex("8ea2b7ca516745bfeafc49904b496089"))


class GcmTest(unittest.TestCase):
    def _enc(self, key, iv, pt):
        return ref._gcm_encrypt(key, iv, pt)

    def test_nist_zero_key_empty(self):
        ct, tag = self._enc(b"\0" * 32, b"\0" * 12, b"")
        self.assertEqual(ct, b"")
        self.assertEqual(tag, bytes.fromhex("530f8afbc74536b9a963b4f1c4cb738b"))

    def test_nist_zero_key_all_zero_block(self):
        ct, tag = self._enc(b"\0" * 32, b"\0" * 12, b"\0" * 16)
        self.assertEqual(ct.hex(), "cea7403d4d606b6e074ec5d3baf39d18")
        self.assertEqual(tag, bytes.fromhex("d0d1c8a799996bf0265b98b5d48ab919"))

    def test_nist_tc15(self):
        key = bytes.fromhex("feffe9928665731c6d6a8f9467308308feffe9928665731c6d6a8f9467308308")
        iv = bytes.fromhex("cafebabefacedbaddecaf888")
        pt = bytes.fromhex("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
                           "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255")
        ct, tag = self._enc(key, iv, pt)
        self.assertEqual(ct.hex(), "522dc1f099567d07f47f37a32a84427d643a8cdcbfe5c0c97598a2bd2555d1aa"
                                   "8cb08e48590dbb3da7b08b1056828838c5f61e6393ba7a0abcc9f662898015ad")
        self.assertEqual(tag, bytes.fromhex("b094dac5d93471bdec1a502270e3cc6c"))

    def test_round_trip(self):
        key = hashlib.sha256(b"round-trip").digest()
        iv = bytes.fromhex("00112233445566778899aabb")
        pt = "тест-строка with ascii mixed".encode("utf-8")
        ct, tag = self._enc(key, iv, pt)
        self.assertEqual(ref._gcm_decrypt(key, iv, ct, tag), pt)

    def test_tampered_tag_rejected(self):
        key = hashlib.sha256(b"tamper").digest()
        iv = b"\0" * 12
        ct, tag = self._enc(key, iv, b"payload")
        bad = bytearray(tag)
        bad[0] ^= 1
        with self.assertRaises(ValueError):
            ref._gcm_decrypt(key, iv, ct, bytes(bad))

    def test_tampered_ciphertext_rejected(self):
        key = hashlib.sha256(b"tamper-ct").digest()
        iv = b"\0" * 12
        ct, tag = self._enc(key, iv, b"payload")
        bad = bytearray(ct)
        bad[0] ^= 1
        with self.assertRaises(ValueError):
            ref._gcm_decrypt(key, iv, bytes(bad), tag)


class NodeBlobTest(unittest.TestCase):
    def test_node_encrypted_blob_decrypts(self):
        """Encrypted by node's crypto (the implementation ZCode uses), the
        Python side must decrypt it: the two agree on key derivation, GCM and
        base64url framing."""
        self.assertEqual(ref.zcode_decrypt(NODE_BLOB_VALUE, NODE_BLOB_SECRET),
                         NODE_BLOB_PLAINTEXT)


class SecretTest(unittest.TestCase):
    def test_env_wins(self):
        saved = os.environ.pop("ZCODE_CREDENTIAL_SECRET", None)
        try:
            os.environ["ZCODE_CREDENTIAL_SECRET"] = "  custom secret  "
            self.assertEqual(ref.zcode_secret(), "custom secret")
        finally:
            if saved is None:
                del os.environ["ZCODE_CREDENTIAL_SECRET"]
            else:
                os.environ["ZCODE_CREDENTIAL_SECRET"] = saved

    def test_blank_env_falls_back(self):
        saved = os.environ.pop("ZCODE_CREDENTIAL_SECRET", None)
        try:
            os.environ["ZCODE_CREDENTIAL_SECRET"] = "   "
            s = ref.zcode_secret()
            self.assertTrue(s.startswith("zcode-credential-fallback:"))
            self.assertIn(":", s[len("zcode-credential-fallback:"):])
        finally:
            if saved is None:
                del os.environ["ZCODE_CREDENTIAL_SECRET"]
            else:
                os.environ["ZCODE_CREDENTIAL_SECRET"] = saved


def write_creds(dirpath, body, encrypt=False, secret=NODE_BLOB_SECRET):
    d = Path(dirpath) / "v2"
    d.mkdir(parents=True, exist_ok=True)
    if encrypt:
        key = hashlib.sha256(secret.encode("utf-8")).digest()
        iv = bytes.fromhex("00112233445566778899aabb")
        encoded = {}
        for k, v in body.items():
            data = v.encode("utf-8")
            ct, tag = ref._gcm_encrypt(key, iv, data)
            b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
            encoded[k] = "enc:v1:" + ".".join(b64(x) for x in (iv, tag, ct))
        body = encoded
    f = d / "credentials.json"
    f.write_text(json.dumps(body), encoding="utf-8")
    return f


class LoginTest(unittest.TestCase):
    BODY = {
        "zcodejwttoken": "jwt-part-a.jwt-part-b.jwt-part-c",
        "oauth:zai:access_token": "access.jwt.value",
        "oauth:zai:user_info": json.dumps({"user_id": "u-1", "email": "Me@Example.COM",
                                           "name": "Fixture User"}),
    }

    # zcode_login_of resolves the secret itself (env first): pinning it keeps
    # the encrypted fixtures machine-independent.
    def run(self, result=None):
        with mock.patch.dict(os.environ, {"ZCODE_CREDENTIAL_SECRET": NODE_BLOB_SECRET}):
            return super().run(result)

    def test_plain_values(self):
        """Unencrypted values pass through -- the map holds plain strings too."""
        with tempfile.TemporaryDirectory() as tmp:
            f = write_creds(tmp, self.BODY)
            login = ref.zcode_login_of(f)
            self.assertIsNone(login["error"])
            self.assertEqual(login["name"], "me@example.com")
            self.assertEqual(login["jwt"], "jwt-part-a.jwt-part-b.jwt-part-c")

    def test_encrypted_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = write_creds(tmp, self.BODY, encrypt=True)
            login = ref.zcode_login_of(f)
            self.assertIsNone(login["error"])
            self.assertEqual(login["name"], "me@example.com")

    def test_wrong_secret_reports_not_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = write_creds(tmp, self.BODY, encrypt=True, secret="another machine")
            login = ref.zcode_login_of(f)
            self.assertIsNotNone(login["error"])
            self.assertIn("ZCODE_CREDENTIAL_SECRET", login["error"])

    def test_missing_email_reports(self):
        body = {"zcodejwttoken": "a.b.c", "oauth:zai:access_token": "x",
                "oauth:zai:user_info": json.dumps({"user_id": "u-1"})}
        with tempfile.TemporaryDirectory() as tmp:
            f = write_creds(tmp, body)
            login = ref.zcode_login_of(f)
            self.assertIsNotNone(login["error"])

    def test_discovery_by_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_creds(root / "home", self.BODY)
            (root / "empty").mkdir()
            found = ref.zcode_logins_of([root / "home", root / "empty"])
            self.assertEqual(len(found), 1)
            self.assertIsNone(found[0]["error"])
            self.assertIn("[home]", found[0]["label"])   # multi-dir label


class RowsTest(unittest.TestCase):
    def test_fixture_row(self):
        usage = json.loads((ref.REPO_ROOT / "fixtures" / "usage" / "zcode.json")
                           .read_text(encoding="utf-8"))
        rows = list(ref.zcode_rows_of(usage))
        self.assertEqual(len(rows), 1)
        kind, pct, sev, reset, epoch = rows[0]
        self.assertEqual(kind, "plan usage")
        self.assertAlmostEqual(pct, 12.0)
        self.assertIsNone(sev)
        self.assertEqual(epoch, 1793462400)
        self.assertIn("(", reset)   # "when (time left)" shape of every row

    def test_no_rows_without_total(self):
        self.assertEqual(list(ref.zcode_rows_of({"code": 0, "data": {}})), [])
        self.assertEqual(list(ref.zcode_rows_of({})), [])
        zero = {"data": {"total_usage": {"used": 0, "limit": 0}}}
        self.assertEqual(list(ref.zcode_rows_of(zero)), [])

    def test_plan_use_is_recorded_and_has_its_own_forecast_class(self):
        # The class exists since the log payload named the window's length
        # (plan 01.8, amendment 2026-10-31); the length itself rides per reply.
        self.assertEqual(ref.kind_class_of("plan usage"), "monthly")
        mark = datetime.fromtimestamp(1793400000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        history = {}
        ref.record_sample(history, "zcode:me@example.com", "plan usage", 12.0, 1793400000)
        self.assertEqual(history, {"zcode:me@example.com|plan usage": [[mark, 12.0]]})
        other = {}
        ref.record_sample(other, "s", "some unknown row", 12.0, 1793400000)
        self.assertEqual(other, {})   # unknown rows are still not recorded


class LogBalanceTest(unittest.TestCase):
    LINE = ('[2026-10-31 11:31:56] [usage-stats] billing/balance 请求完成 '
            '{"balanceCount":1,"payload":{"code":0,"data":{"server_time":1793435515,'
            '"plans":[{"user_plan_id":"upl_1","plan_id":"p1","name":"ZCODE TEST PLAN",'
            '"priority":101,"status":"active","ends_at":1793581200}],'
            '"balances":[{"user_plan_id":"upl_1","plan_id":"p1","total_units":500000000,'
            '"used_units":250000000,"expires_at":1793581200}]}}}')

    def _home(self, log_body):
        d = Path(tempfile.mkdtemp())
        (d / "v2" / "logs").mkdir(parents=True)
        (d / "v2" / "logs" / "2026-10-31.log").write_text(log_body, encoding="utf-8")
        return d

    def test_burn_from_the_app_log(self):
        """The real meter the MCP endpoint does not carry: used/total from the
        newest `billing/balance` payload the running app logged (plan 01.8)."""
        snap = ref.zcode_balance_from_log(self._home(self.LINE), now=1793435515)
        self.assertIsNotNone(snap)
        self.assertEqual(snap["plan"]["name"], "ZCODE TEST PLAN")
        rows = list(ref.zcode_log_rows(snap))
        self.assertEqual(len(rows), 1)
        kind, pct, sev, reset, epoch = rows[0]
        self.assertEqual(kind, "plan usage")
        self.assertAlmostEqual(pct, 50.0)
        self.assertEqual(epoch, 1793581200)
        plan = ref.zcode_log_plan(snap)
        self.assertEqual(ref.zcode_plan_line(plan, now=1793435515),
                         "plan: ZCODE TEST PLAN, ends Nov 2 (1d 16h)")

    def test_no_log_or_garbage_is_none(self):
        empty = self._home("")
        self.assertIsNone(ref.zcode_balance_from_log(empty, now=1793435515))
        garbage = self._home('x billing/balance {"payload": {"data": {}}}')
        self.assertIsNone(ref.zcode_balance_from_log(garbage, now=1793435515))
        self.assertIsNone(ref.zcode_balance_from_log(Path(tempfile.mkdtemp()), now=0))


class PlanTest(unittest.TestCase):
    def test_active_plan_by_priority(self):
        reply = json.loads((ref.REPO_ROOT / "fixtures" / "usage" / "zcode-plan.json")
                           .read_text(encoding="utf-8"))
        plan = ref.zcode_active_plan(reply)
        self.assertEqual(plan["name"], "ZCODE FIXTURE PLAN")
        line = ref.zcode_plan_line(plan, now=1793400000)
        self.assertTrue(line.startswith("plan: ZCODE FIXTURE PLAN, ends "))
        self.assertIn("(", line)

    def test_no_active_plan(self):
        self.assertIsNone(ref.zcode_active_plan({"data": {"plans": [
            {"name": "X", "status": "expired", "priority": 101}]}}))
        self.assertIsNone(ref.zcode_active_plan({"data": {}}))
        self.assertIsNone(ref.zcode_plan_line(None))
        self.assertIsNone(ref.zcode_plan_line({"name": "  "}))


class ConfigTest(unittest.TestCase):
    def test_zcode_kind_accepted(self):
        self.assertEqual(ref.kinded([{"dir": "~/.zcode", "kind": "zcode"}]),
                         [("~/.zcode", "zcode", False)])
        self.assertIn("zcode", ref.LOGIN_KINDS)


if __name__ == "__main__":
    unittest.main()
