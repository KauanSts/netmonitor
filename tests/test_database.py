import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "test.sqlite3"
        db.init_db(self.path)

    def add(self, address="127.0.0.1", **kwargs):
        return db.save_device(self.path, kwargs.get("name", "Meu dispositivo"), address,
                              kwargs.get("device_type", "servidor"), kwargs.get("description", ""))

    def result(self, status="online"):
        return dict(status=status, latency_ms=1.0, latency_is_upper_bound=True, error=None)

    def test_initialization_is_idempotent(self):
        device_id = self.add()
        db.record_check(self.path, device_id, self.result())
        db.init_db(self.path)
        self.assertEqual(len(db.list_devices(self.path)), 1)
        self.assertEqual(len(db.get_history(self.path, device_id)), 1)
        with db.connect(self.path) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(checks)")}
            self.assertTrue({"checks_device_date", "checks_date"} <= indexes)

    def test_crud_and_utc(self):
        device_id = self.add()
        device = db.get_device(self.path, device_id)
        self.assertEqual(device["name"], "Meu dispositivo")
        self.assertEqual(datetime.fromisoformat(device["created_at"]).utcoffset(), timedelta(0))
        db.save_device(self.path, "Atualizado", "::1", "computador", "Local", device_id)
        updated = db.get_device(self.path, device_id)
        self.assertEqual(updated["address"], "::1")
        self.assertEqual(updated["description"], "Local")
        self.assertEqual(updated["created_at"], device["created_at"])
        db.delete_device(self.path, device_id)
        self.assertIsNone(db.get_device(self.path, device_id))
        self.assertEqual(db.list_devices(self.path), [])

    def test_validation(self):
        for name, address, kind, description in [
            (" ", "::1", "outro", ""), ("x" * 101, "::1", "outro", ""),
            ("x\n", "::1", "outro", ""), ("x", "https://a.com", "outro", ""),
            ("x", "-6", "outro", ""), ("x", "::1", "switch", ""),
            ("x", "::1", "outro", "x" * 1001), ("x", "1::2::3", "outro", ""),
        ]:
            with self.subTest(address=address, name=name), self.assertRaises(ValueError):
                db.save_device(self.path, name, address, kind, description)
        self.assertEqual(db.list_devices(self.path), [])

    def test_normalized_duplicates(self):
        for first, second in [("Example.COM.", "example.com"),
                              ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
                              ("127.0.0.1", "127.0.0.1")]:
            with self.subTest(first=first):
                self.add(first)
                with self.assertRaisesRegex(ValueError, "Já existe"):
                    self.add(second)

    def test_edit_duplicate_is_atomic(self):
        first = self.add()
        second = self.add("::1")
        with self.assertRaisesRegex(ValueError, "Já existe"):
            db.save_device(self.path, "Novo", "127.0.0.1", "outro", device_id=second)
        self.assertEqual(db.get_device(self.path, second)["address"], "::1")
        db.save_device(self.path, "Mesmo", "127.0.0.1", "outro", device_id=first)

    def test_missing_device(self):
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            db.delete_device(self.path, 999)
        with self.assertRaisesRegex(ValueError, "não encontrado"):
            db.save_device(self.path, "Nome", "::1", "outro", device_id=999)

    def test_history_order_and_cascade(self):
        device_id = self.add()
        other = self.add("::1")
        for status in ("online", "offline", "timeout", "error"):
            db.record_check(self.path, device_id, self.result(status))
        history = db.get_history(self.path, device_id)
        self.assertEqual([row["status"] for row in history], ["error", "timeout", "offline", "online"])
        self.assertEqual(history[0]["latency_is_upper_bound"], 1)
        self.assertEqual(datetime.fromisoformat(history[0]["checked_at"]).utcoffset(), timedelta(0))
        self.assertEqual(len(db.get_history(self.path, device_id, 1)), 1)
        self.assertEqual(db.get_history(self.path, other), [])
        db.delete_device(self.path, device_id)
        self.assertEqual(db.get_history(self.path, device_id), [])
        self.assertIsNotNone(db.get_device(self.path, other))

    def test_foreign_key_and_status_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.record_check(self.path, 999, self.result())
        device_id = self.add()
        with self.assertRaises(sqlite3.IntegrityError):
            db.record_check(self.path, device_id, self.result("invalid"))

    def test_sql_injection_remains_data(self):
        name = "x'); DROP TABLE devices; --"
        device_id = self.add(name=name, description="' OR 1=1 --")
        self.assertEqual(db.get_device(self.path, device_id)["name"], name)
        self.assertIsNone(db.get_device(self.path, "1 OR 1=1"))
        self.assertEqual(len(db.list_devices(self.path)), 1)
