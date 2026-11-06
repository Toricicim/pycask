from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import struct
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from bitcask import DB, HEADER, MAGIC, PUT


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "test.data"

    def test_literal_tombstone_empty_and_unicode_values_survive_restart_and_compaction(self):
        values = {"literal": "__DELETED__", "empty": "", "şifre🔑": "İstanbul\x00🌍", "": "empty key"}
        with DB(self.path) as db:
            for key, value in values.items():
                db.put(key, value)
            db.put("gone", "old value")
            self.assertTrue(db.delete("gone"))
            self.assertFalse(db.delete("missing"))
        for compact in (False, True, False):
            with DB(self.path) as db:
                if compact:
                    db.compact()
                self.assertIsNone(db.get("gone"))
                self.assertEqual({key: db.get(key) for key in values}, values)

    def test_compaction_reclaims_space_and_allows_further_appends(self):
        with DB(self.path) as db:
            for i in range(20):
                db.put("same", "x" * 100 + str(i))
            db.put("deleted", "x" * 100)
            db.delete("deleted")
            before = self.path.stat().st_size
            db.compact()
            self.assertLess(self.path.stat().st_size, before)
            self.assertEqual(db.get("same"), "x" * 100 + "19")
            db.put("after", "new")
            db.put("same", "updated")
        with DB(self.path) as db:
            self.assertEqual(db.get("same"), "updated")
            self.assertEqual(db.get("after"), "new")
            self.assertIsNone(db.get("deleted"))

    def test_failed_compaction_preserves_file_index_and_writes(self):
        with DB(self.path) as db:
            db.put("key", "before")
            original = self.path.read_bytes()
            with patch("bitcask.os.replace", side_effect=OSError("injected replace failure")):
                with self.assertRaises(OSError):
                    db.compact()
            self.assertEqual(self.path.read_bytes(), original)
            self.assertEqual(db.get("key"), "before")
            db.put("key", "after")
        self.assertEqual(list(Path(self.directory.name).glob("*.compact")), [])
        with DB(self.path) as db:
            self.assertEqual(db.get("key"), "after")

    def test_partial_tail_is_removed_before_future_appends(self):
        for tail in (b"\x01\x05", HEADER.pack(PUT, 1000, 1000) + b"short"):
            with self.subTest(tail=tail):
                self.path.write_bytes(b"")
                with DB(self.path) as db:
                    db.put("good", "kept")
                valid_size = self.path.stat().st_size
                with self.path.open("ab") as file:
                    file.write(tail)
                with self.assertWarnsRegex(RuntimeWarning, "incomplete final record"):
                    with DB(self.path) as db:
                        self.assertEqual(self.path.stat().st_size, valid_size)
                        self.assertEqual(db.get("good"), "kept")
                        db.put("later", "visible")
                with DB(self.path) as db:
                    self.assertEqual(db.get("later"), "visible")

    def test_malformed_operation_is_rejected_without_changing_file(self):
        raw = MAGIC + HEADER.pack(99, 0, 0)
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "Invalid record operation"):
            DB(self.path)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_legacy_migration_keeps_backup_and_deletions(self):
        def legacy(key, value):
            key, value = key.encode(), value.encode()
            return struct.pack("II", len(key), len(value)) + key + value

        raw = legacy("kept", "old") + legacy("gone", "old") + legacy("gone", "__DELETED__")
        self.path.write_bytes(raw)
        with self.assertWarnsRegex(RuntimeWarning, "Migrated legacy database"):
            with DB(self.path) as db:
                self.assertEqual(db.get("kept"), "old")
                self.assertIsNone(db.get("gone"))
                db.put("literal", "__DELETED__")
                db.compact()
        self.assertEqual(Path(str(self.path) + ".v1.bak").read_bytes(), raw)
        with DB(self.path) as db:
            self.assertEqual(db.get("literal"), "__DELETED__")
            self.assertIsNone(db.get("gone"))

    def test_incomplete_legacy_file_is_not_replaced(self):
        raw = struct.pack("II", 100, 100) + b"short"
        self.path.write_bytes(raw)
        with self.assertRaises(EOFError):
            DB(self.path)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertFalse(Path(str(self.path) + ".v1.bak").exists())

    def test_concurrent_read_write_delete_and_compact(self):
        workers = 8
        barrier = threading.Barrier(workers)
        with DB(self.path) as db:
            def exercise(worker):
                barrier.wait(timeout=5)
                key = f"worker:{worker}"
                for i in range(30):
                    value = f"{worker}:{i}" + "x" * i
                    db.put(key, value)
                    self.assertEqual(db.get(key), value)
                    if i % 7 == 0:
                        db.compact()
                    if i % 3 == 0:
                        self.assertTrue(db.delete(key))
                        self.assertIsNone(db.get(key))
                        db.put(key, value)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(exercise, range(workers)))
        with DB(self.path) as db:
            for worker in range(workers):
                self.assertEqual(db.get(f"worker:{worker}"), f"{worker}:29" + "x" * 29)

    def test_randomized_operations_match_dictionary_across_restarts(self):
        rng = random.Random(42)
        expected = {}
        for _ in range(5):
            with DB(self.path) as db:
                for _ in range(100):
                    key = str(rng.randrange(20))
                    operation = rng.randrange(10)
                    if operation < 6:
                        value = rng.choice(["", "__DELETED__", "Türkçe", str(rng.random())])
                        db.put(key, value)
                        expected[key] = value
                    elif operation < 9:
                        self.assertEqual(db.delete(key), key in expected)
                        expected.pop(key, None)
                    else:
                        db.compact()
                    self.assertEqual({str(i): db.get(str(i)) for i in range(20)},
                                     {str(i): expected.get(str(i)) for i in range(20)})


if __name__ == "__main__":
    unittest.main()
