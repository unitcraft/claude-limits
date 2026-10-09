"""Offline database health regressions; no binary, sockets or credentials needed."""
import unittest

from smoke_server import database_health_ok


class DatabaseHealthTest(unittest.TestCase):
    def health(self, **changes):
        storage = {"encrypted": True, "schema_version": 3, "db_size_bytes": 12288}
        storage.update(changes)
        return {"ok": True, "storage": storage}

    def test_current_encrypted_database(self):
        self.assertTrue(database_health_ok(self.health()))

    def test_wrong_schema(self):
        for schema in (2, 4, None, "3", 3.0, True):
            with self.subTest(schema=schema):
                self.assertFalse(database_health_ok(self.health(schema_version=schema)))

    def test_encryption_required(self):
        for encrypted in (False, None, 1, "true"):
            with self.subTest(encrypted=encrypted):
                self.assertFalse(database_health_ok(self.health(encrypted=encrypted)))

    def test_real_file_required(self):
        for size in (0, -1, None, "12288", True, 1.5):
            with self.subTest(size=size):
                self.assertFalse(database_health_ok(self.health(db_size_bytes=size)))

    def test_missing_fields_and_malformed_shapes(self):
        for health in (None, [], "health", {}, {"storage": None}, {"storage": []}):
            with self.subTest(health=health):
                self.assertFalse(database_health_ok(health))
        for field in ("encrypted", "schema_version", "db_size_bytes"):
            health = self.health()
            del health["storage"][field]
            with self.subTest(missing=field):
                self.assertFalse(database_health_ok(health))


if __name__ == "__main__":
    unittest.main()
