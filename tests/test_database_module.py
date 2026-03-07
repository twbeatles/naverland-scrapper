import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.core.database import ComplexDatabase


class TestComplexDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_complexes.db")
        self.db = ComplexDatabase(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_add_and_get_complex(self):
        ok = self.db.add_complex("TestComplex", "12345", "memo")
        self.assertTrue(ok)

        rows = self.db.get_all_complexes()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "TestComplex")
        self.assertEqual(rows[0]["complex_id"], "12345")
        self.assertEqual(rows[0]["asset_type"], "APT")

    def test_add_complex_same_complex_id_different_asset_type(self):
        s1 = self.db.add_complex("ComplexA", "30003", asset_type="APT", return_status=True)
        s2 = self.db.add_complex("ComplexB", "30003", asset_type="VL", return_status=True)
        s3 = self.db.add_complex("ComplexA", "30003", asset_type="APT", return_status=True)

        self.assertEqual(s1, "inserted")
        self.assertEqual(s2, "inserted")
        self.assertEqual(s3, "existing")

        rows = self.db.get_all_complexes()
        targets = [row for row in rows if row["complex_id"] == "30003"]
        self.assertEqual(sorted(row["asset_type"] for row in targets), ["APT", "VL"])

    def test_group_lifecycle(self):
        self.db.add_complex("ComplexA", "11111", asset_type="APT")
        all_complexes = self.db.get_all_complexes()
        complex_db_id = all_complexes[0]["id"]

        self.assertTrue(self.db.create_group("GroupA", "desc"))
        groups = self.db.get_all_groups()
        self.assertEqual(len(groups), 1)
        group_id = groups[0]["id"]

        added = self.db.add_complexes_to_group(group_id, [complex_db_id])
        self.assertEqual(added, 1)

        in_group = self.db.get_complexes_in_group(group_id)
        self.assertEqual(len(in_group), 1)
        self.assertEqual(in_group[0]["name"], "ComplexA")
        self.assertEqual(in_group[0]["asset_type"], "APT")

    def test_get_complexes_for_stats_returns_partial_when_one_source_fails(self):
        def _fake_fetchall_safe(_conn, _query, params=(), context=""):
            if "complexes" in context:
                return [{"name": "ComplexA", "complex_id": "11111"}]
            if "crawl_history" in context:
                return []
            if "price_snapshots" in context:
                return [{"complex_id": "22222"}]
            return []

        with patch.object(self.db, "_fetchall_safe", side_effect=_fake_fetchall_safe):
            rows = self.db.get_complexes_for_stats()

        self.assertEqual(len(rows), 2)
        self.assertIn(("ComplexA", "11111"), rows)
        self.assertTrue(any(cid == "22222" for _name, cid in rows))

    def test_write_circuit_breaker_blocks_core_writes(self):
        self.db._disable_writes("database_corruption")
        self.assertTrue(self.db.is_write_disabled())

        self.assertFalse(self.db.add_crawl_history("ComplexA", "12345", "SALE", 1))
        self.assertEqual(len(self.db.get_crawl_history(limit=10)), 0)

        saved = self.db.upsert_article_history_bulk(
            [
                {
                    "article_id": "X1",
                    "complex_id": "11111",
                    "complex_name": "ComplexA",
                    "trade_type": "SALE",
                    "price": 10000,
                    "price_text": "10000",
                    "area": 30.0,
                    "floor": "10",
                    "feature": "f",
                    "last_price": 10000,
                }
            ]
        )
        self.assertEqual(saved, 0)

    def test_delete_complex_removes_group_mapping(self):
        self.db.add_complex("ComplexA", "11111")
        complex_id = self.db.get_all_complexes()[0]["id"]
        self.assertTrue(self.db.create_group("GroupA", ""))
        group_id = self.db.get_all_groups()[0]["id"]
        self.assertEqual(self.db.add_complexes_to_group(group_id, [complex_id]), 1)

        self.assertTrue(self.db.delete_complex(complex_id))
        rows = self.db.get_complexes_in_group(group_id)
        self.assertEqual(len(rows), 0)

    def test_delete_complexes_bulk_removes_group_mapping(self):
        self.db.add_complex("ComplexA", "11111")
        self.db.add_complex("ComplexB", "22222")
        rows = self.db.get_all_complexes()
        ids = [rows[0]["id"], rows[1]["id"]]

        self.assertTrue(self.db.create_group("GroupA", ""))
        group_id = self.db.get_all_groups()[0]["id"]
        self.assertEqual(self.db.add_complexes_to_group(group_id, ids), 2)

        deleted = self.db.delete_complexes_bulk(ids)
        self.assertEqual(deleted, 2)

        conn = self.db._pool.get_connection()
        try:
            cnt = conn.cursor().execute(
                "SELECT COUNT(*) FROM group_complexes WHERE complex_id IN (?, ?)",
                (ids[0], ids[1]),
            ).fetchone()[0]
        finally:
            self.db._pool.return_connection(conn)
        self.assertEqual(cnt, 0)

    def test_delete_complex_purge_related_flag_controls_history_cleanup(self):
        self.db.add_complex("KeepHistory", "50005", asset_type="APT")
        self.db.add_complex("PurgeHistory", "60006", asset_type="APT")
        rows = self.db.get_all_complexes()
        keep_id = next(int(row["id"]) for row in rows if row["complex_id"] == "50005")
        purge_id = next(int(row["id"]) for row in rows if row["complex_id"] == "60006")

        conn = self.db._pool.get_connection()
        try:
            c = conn.cursor()
            for cid in ("50005", "60006"):
                c.execute(
                    """
                    INSERT INTO article_history (
                        article_id, complex_id, complex_name, trade_type, price, price_text, area_pyeong
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (f"A-{cid}", cid, f"C-{cid}", "SALE", 10000, "10000", 30.0),
                )
                c.execute(
                    """
                    INSERT INTO crawl_history (complex_name, complex_id, trade_types, item_count, asset_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (f"C-{cid}", cid, "SALE", 1, ""),
                )
                c.execute(
                    """
                    INSERT INTO price_snapshots (complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "SALE", 30.0, 10000, 11000, 10500, 1),
                )
                c.execute(
                    """
                    INSERT INTO alert_settings (complex_id, complex_name, trade_type, area_min, area_max, price_min, price_max, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (cid, f"C-{cid}", "SALE", 0.0, 100.0, 0, 999999),
                )
                c.execute(
                    """
                    INSERT INTO article_favorites (article_id, complex_id, is_favorite, note)
                    VALUES (?, ?, 1, '')
                    """,
                    (f"A-{cid}", cid),
                )
                c.execute(
                    """
                    INSERT INTO article_alert_log (alert_id, article_id, complex_id)
                    VALUES (?, ?, ?)
                    """,
                    (1, f"A-{cid}", cid),
                )
            conn.commit()
        finally:
            self.db._pool.return_connection(conn)

        self.assertTrue(self.db.delete_complex(keep_id, purge_related=False))
        self.assertTrue(self.db.delete_complex(purge_id, purge_related=True))

        verify_conn = self.db._pool.get_connection()
        try:
            c = verify_conn.cursor()
            self.assertGreater(c.execute("SELECT COUNT(*) FROM article_history WHERE complex_id = '50005'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM article_history WHERE complex_id = '60006'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM crawl_history WHERE complex_id = '60006'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM price_snapshots WHERE complex_id = '60006'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM alert_settings WHERE complex_id = '60006'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM article_favorites WHERE complex_id = '60006'").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM article_alert_log WHERE complex_id = '60006'").fetchone()[0], 0)
        finally:
            self.db._pool.return_connection(verify_conn)

    def test_mark_disappeared_for_targets_scope_with_asset_type(self):
        self.assertTrue(
            self.db.update_article_history(
                article_id="E1",
                complex_id="30003",
                complex_name="ComplexA",
                trade_type="SALE",
                price=18000,
                price_text="18000",
                area=32.0,
                floor="10",
                feature="f",
                extra={"asset_type": "APT"},
            )
        )
        self.assertTrue(
            self.db.update_article_history(
                article_id="E2",
                complex_id="30003",
                complex_name="ComplexA",
                trade_type="SALE",
                price=17500,
                price_text="17500",
                area=31.0,
                floor="9",
                feature="f",
                extra={"asset_type": "VL"},
            )
        )

        conn = self.db._pool.get_connection()
        try:
            conn.cursor().execute(
                "UPDATE article_history SET last_seen = date('now', '-2 day'), status='active' WHERE article_id IN (?, ?)",
                ("E1", "E2"),
            )
            conn.commit()
        finally:
            self.db._pool.return_connection(conn)

        updated = self.db.mark_disappeared_articles_for_targets([("APT", "30003", "SALE")])
        self.assertEqual(updated, 1)

        conn = self.db._pool.get_connection()
        try:
            rows = conn.cursor().execute(
                "SELECT article_id, asset_type, status FROM article_history WHERE article_id IN (?, ?) ORDER BY article_id",
                ("E1", "E2"),
            ).fetchall()
        finally:
            self.db._pool.return_connection(conn)

        self.assertEqual(rows[0]["article_id"], "E1")
        self.assertEqual(rows[0]["asset_type"], "APT")
        self.assertEqual(rows[0]["status"], "disappeared")
        self.assertEqual(rows[1]["article_id"], "E2")
        self.assertEqual(rows[1]["asset_type"], "VL")
        self.assertEqual(rows[1]["status"], "active")

    def test_record_alert_notification_dedup_by_day(self):
        first = self.db.record_alert_notification(
            alert_id=10,
            article_id="A100",
            complex_id="C100",
            notified_on="2026-02-21",
        )
        second = self.db.record_alert_notification(
            alert_id=10,
            article_id="A100",
            complex_id="C100",
            notified_on="2026-02-21",
        )
        third = self.db.record_alert_notification(
            alert_id=10,
            article_id="A100",
            complex_id="C100",
            notified_on="2026-02-22",
        )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(third)

    def test_backup_and_restore_preserves_rows(self):
        self.assertTrue(self.db.add_complex("BaseComplex", "A-100"))
        backup_path = os.path.join(self.tmp.name, "backup_snapshot.db")
        self.assertTrue(self.db.backup_database(backup_path))
        self.assertTrue(os.path.exists(backup_path))

        self.assertTrue(self.db.add_complex("AddedComplex", "A-200"))
        self.assertEqual(len(self.db.get_all_complexes()), 2)

        self.assertTrue(self.db.restore_database(backup_path))
        restored = self.db.get_all_complexes()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["complex_id"], "A-100")

    def test_restore_recreates_missing_tables_from_legacy_schema(self):
        legacy_path = os.path.join(self.tmp.name, "legacy_minimal.db")
        conn = sqlite3.connect(legacy_path)
        try:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE complexes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    complex_id TEXT NOT NULL UNIQUE,
                    memo TEXT DEFAULT ""
                )
                """
            )
            c.execute(
                "INSERT INTO complexes (name, complex_id, memo) VALUES (?, ?, ?)",
                ("LegacyComplex", "LEG-001", ""),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(self.db.restore_database(legacy_path))
        rows = self.db.get_all_complexes()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["complex_id"], "LEG-001")

        check_conn = self.db._pool.get_connection()
        try:
            integrity = check_conn.cursor().execute("PRAGMA integrity_check").fetchone()
            self.assertEqual(str(integrity[0]).lower(), "ok")
            table_rows = check_conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        finally:
            self.db._pool.return_connection(check_conn)
        table_names = {r[0] for r in table_rows}
        self.assertIn("article_history", table_names)
        self.assertIn("price_snapshots", table_names)

    def test_migrate_legacy_complexes_schema_to_asset_type(self):
        legacy_path = os.path.join(self.tmp.name, "legacy_complex_schema.db")
        conn = sqlite3.connect(legacy_path)
        try:
            c = conn.cursor()
            c.execute(
                """
                CREATE TABLE complexes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    complex_id TEXT NOT NULL UNIQUE,
                    memo TEXT DEFAULT "",
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            c.execute(
                "INSERT INTO complexes (name, complex_id, memo) VALUES (?, ?, ?)",
                ("LegacyComplex", "LEG-100", "memo"),
            )
            conn.commit()
        finally:
            conn.close()

        migrated_db = ComplexDatabase(legacy_path)
        try:
            rows = migrated_db.get_all_complexes()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["complex_id"], "LEG-100")
            self.assertEqual(rows[0]["asset_type"], "APT")
        finally:
            migrated_db.close()


if __name__ == "__main__":
    unittest.main()
