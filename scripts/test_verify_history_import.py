from pathlib import Path
import tempfile
import unittest

import verify_history_import as verification


class VerificationTests(unittest.TestCase):
    def test_api_without_refresh_uses_explicit_private_file_setting(self):
        stand = Path("private-fixture")
        api = {"history": {"keep_days": 30}, "folders": [{"path": str(stand / "empty-folder")}]}
        settings = {"refresh": {"enabled": False}}
        verification.check_config(api, settings, stand)
        settings["refresh"]["enabled"] = True
        with self.assertRaises(RuntimeError):
            verification.check_config(api, settings, stand)

    def test_health_coverage_is_not_configured_retention(self):
        with tempfile.TemporaryDirectory() as temporary:
            stand = Path(temporary)
            health = {"ok": True, "storage": {"schema_version": 3, "encrypted": False,
                      "key_store": "none", "history_days": 0,
                      "db_path": str(stand / "data" / "claude-limits.duckdb"),
                      "config_path": str(stand / "config" / "import.toml")}}
            verification.check_health(health, stand)
            health["storage"]["encrypted"] = True
            with self.assertRaises(RuntimeError):
                verification.check_health(health, stand)

    def test_inherited_owner_paths_and_credentials_overrides_are_scrubbed(self):
        inherited = {"CLAUDE_LIMITS_CONFIG": "owner", "CLAUDE_LIMITS_DATA": "owner",
                     "CLAUDE_LIMITS_DB_KEY_FILE": "owner", "claude_config_dir": "owner",
                     "KIMI_CODE_HOME": "owner", "CODEX_HOME": "owner", "XDG_CACHE_HOME": "owner",
                     "HOME": "owner", "USERPROFILE": "owner", "HOMEDRIVE": "owner", "HOMEPATH": "owner",
                     "APPDATA": "owner", "LOCALAPPDATA": "owner", "PATH": "real-cli",
                     "SystemRoot": "C:/Windows"}
        original = dict(inherited)
        root = Path("private-fixture")
        env = verification.child_env(root, inherited)
        self.assertEqual(inherited, original)
        self.assertFalse(any(value == "owner" for value in env.values()))
        self.assertNotIn("CLAUDE_LIMITS_DB_KEY_FILE", env)
        self.assertNotIn("CLAUDE_LIMITS_CONFIG", env)
        self.assertNotIn("real-cli", env["PATH"])
        self.assertEqual(env["CLAUDE_LIMITS_DATA"], str(root / "data"))

    def test_expected_integer_contract_and_window_mapping(self):
        result = verification.expected_rows({
            "claude:FIXTURE@example.com|weekly_scoped:fixture": [[86400, 12.5], [86401, 13.5]],
            "kimi:fixture|month limit (code)": [[86400, 30.9]],
            "codex:FIXTURE|weekly limit": [[86400, 100]]})
        self.assertEqual(result[("claude:fixture@example.com", "weekly_scoped", "fixture", 86400000)], 12)
        self.assertEqual(result[("claude:fixture@example.com", "weekly_scoped", "fixture", 86401000)], 14)
        self.assertEqual(result[("kimi:fixture", "monthly", "code", 86400000)], 31)
        self.assertEqual(result[("codex:fixture", "weekly_all", "", 86400000)], 100)
        with self.assertRaises(RuntimeError):
            verification.expected_rows({"claude:fixture@example.com|unknown": [[86400, 1]]})
        with self.assertRaises(RuntimeError):
            verification.expected_rows({"codex:FIXTURE|weekly limit": [[86400, 1]],
                                        "codex:fixture|weekly_all": [[86400, 2]]})


if __name__ == '__main__':
    unittest.main()
