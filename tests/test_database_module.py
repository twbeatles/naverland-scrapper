import os
import sys
import tempfile
import sqlite3
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
        ok = self.db.add_complex("테스트단지", "12345", "메모")
        self.assertTrue(ok)

        rows = self.db.get_all_complexes()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "테스트단지")
        self.assertEqual(rows[0]["complex_id"], "12345")

    def test_group_lifecycle(self):
        self.db.add_complex("단지A", "11111")
        all_complexes = self.db.get_all_complexes()
        complex_db_id = all_complexes[0]["id"]

        self.assertTrue(self.db.create_group("관심단지", "설명"))
        groups = self.db.get_all_groups()
        self.assertEqual(len(groups), 1)
        group_id = groups[0]["id"]

        added = self.db.add_complexes_to_group(group_id, [complex_db_id])
        self.assertEqual(added, 1)

        in_group = self.db.get_complexes_in_group(group_id)
        self.assertEqual(len(in_group), 1)
        self.assertEqual(in_group[0]["name"], "단지A")

    def test_add_price_snapshots_bulk(self):
        rows = [
            ("11111", "매매", 30.0, 10000, 12000, 11000, 7),
            ("11111", "매매", 35.0, 13000, 15000, 14000, 5),
            ("11111", "전세", 30.0, 4000, 5000, 4500, 4),
        ]
        saved = self.db.add_price_snapshots_bulk(rows)
        self.assertEqual(saved, 3)

        snapshots = self.db.get_price_snapshots("11111")
        self.assertEqual(len(snapshots), 3)

    def test_price_snapshot_query_normalizes_legacy_text_values(self):
        conn = self.db._pool.get_connection()
        try:
            conn.cursor().execute(
                """
                INSERT INTO price_snapshots (
                    complex_id, trade_type, pyeong, min_price, max_price, avg_price, item_count, snapshot_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("11111", "매매", "34평", "1억", "1억 2,000만", "1억 1,000만", "3건", "2026-02-25"),
            )
            conn.commit()
        finally:
            self.db._pool.return_connection(conn)

        snapshots = self.db.get_price_snapshots("11111", "매매")
        self.assertEqual(len(snapshots), 1)
        _, _, pyeong, min_price, max_price, avg_price, item_count = snapshots[0]
        self.assertEqual(pyeong, 34.0)
        self.assertEqual(min_price, 10000)
        self.assertEqual(max_price, 12000)
        self.assertEqual(avg_price, 11000)
        self.assertEqual(item_count, 3)

        history = self.db.get_complex_price_history("11111", "매매", "34평")
        self.assertEqual(len(history), 1)

    def test_article_history_tracks_new_and_price_change(self):
        is_new, change, prev = self.db.check_article_history("A1", "12345", 10000)
        self.assertTrue(is_new)
        self.assertEqual(change, 0)
        self.assertEqual(prev, 0)

        self.assertTrue(
            self.db.update_article_history(
                article_id="A1",
                complex_id="12345",
                complex_name="테스트단지",
                trade_type="매매",
                price=10000,
                price_text="1억",
                area=30.0,
                floor="10층",
                feature="역세권",
            )
        )

        is_new2, change2, prev2 = self.db.check_article_history("A1", "12345", 9000)
        self.assertFalse(is_new2)
        self.assertEqual(change2, -1000)
        self.assertEqual(prev2, 10000)

    def test_mark_disappeared_and_alert_lookup(self):
        self.assertTrue(
            self.db.update_article_history(
                article_id="B1",
                complex_id="99999",
                complex_name="테스트단지",
                trade_type="매매",
                price=12000,
                price_text="1억 2,000만",
                area=33.0,
                floor="8층",
                feature="신축",
            )
        )

        conn = self.db._pool.get_connection()
        try:
            conn.cursor().execute(
                "UPDATE article_history SET last_seen = date('now', '-2 day'), status='active' WHERE article_id = ? AND complex_id = ?",
                ("B1", "99999"),
            )
            conn.commit()
        finally:
            self.db._pool.return_connection(conn)

        disappeared = self.db.mark_disappeared_articles()
        self.assertGreaterEqual(disappeared, 1)

        self.assertTrue(
            self.db.add_alert_setting("99999", "테스트단지", "매매", 20.0, 40.0, 10000, 13000)
        )
        alerts = self.db.check_alerts("99999", "매매", 33.0, 12000)
        self.assertGreaterEqual(len(alerts), 1)

    def test_mark_disappeared_for_targets_scope_and_rowcount(self):
        self.assertTrue(
            self.db.update_article_history(
                article_id="D1",
                complex_id="10001",
                complex_name="타깃단지",
                trade_type="매매",
                price=15000,
                price_text="1억 5,000만",
                area=35.0,
                floor="12층",
                feature="테스트",
            )
        )
        self.assertTrue(
            self.db.update_article_history(
                article_id="D2",
                complex_id="20002",
                complex_name="비타깃단지",
                trade_type="전세",
                price=7000,
                price_text="7,000만",
                area=24.0,
                floor="7층",
                feature="테스트",
            )
        )

        conn = self.db._pool.get_connection()
        try:
            conn.cursor().execute(
                "UPDATE article_history SET last_seen = date('now', '-2 day'), status='active'"
            )
            conn.commit()
        finally:
            self.db._pool.return_connection(conn)

        updated = self.db.mark_disappeared_articles_for_targets([("10001", "매매")])
        self.assertEqual(updated, 1)

        conn = self.db._pool.get_connection()
        try:
            rows = conn.cursor().execute(
                "SELECT complex_id, trade_type, status FROM article_history WHERE article_id IN (?, ?) ORDER BY article_id",
                ("D1", "D2"),
            ).fetchall()
        finally:
            self.db._pool.return_connection(conn)

        self.assertEqual(rows[0]["complex_id"], "10001")
        self.assertEqual(rows[0]["status"], "disappeared")
        self.assertEqual(rows[1]["complex_id"], "20002")
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

    def test_upsert_article_history_bulk_and_state_lookup(self):
        rows_v1 = [
            {
                "article_id": "C1",
                "complex_id": "77777",
                "complex_name": "테스트단지",
                "trade_type": "매매",
                "price": 12000,
                "price_text": "1억 2,000만",
                "area": 33.0,
                "floor": "10층",
                "feature": "올수리",
                "last_price": 12000,
            },
            {
                "article_id": "C2",
                "complex_id": "77777",
                "complex_name": "테스트단지",
                "trade_type": "매매",
                "price": 10000,
                "price_text": "1억",
                "area": 30.0,
                "floor": "8층",
                "feature": "신축",
                "last_price": 10000,
            },
        ]
        saved1 = self.db.upsert_article_history_bulk(rows_v1)
        self.assertEqual(saved1, 2)

        rows_v2 = [
            {
                "article_id": "C1",
                "complex_id": "77777",
                "complex_name": "테스트단지",
                "trade_type": "매매",
                "price": 11000,
                "price_text": "1억 1,000만",
                "area": 33.0,
                "floor": "10층",
                "feature": "올수리",
                "last_price": 12000,
            }
        ]
        saved2 = self.db.upsert_article_history_bulk(rows_v2)
        self.assertEqual(saved2, 1)

        state = self.db.get_article_history_state_bulk("77777", "매매")
        self.assertIn("C1", state)
        self.assertIn("C2", state)
        self.assertEqual(state["C1"]["price"], 11000)
        self.assertEqual(state["C1"]["price_change"], -1000)
        self.assertEqual(state["C2"]["price"], 10000)

    def test_get_enabled_alert_rules(self):
        self.assertTrue(
            self.db.add_alert_setting("12345", "테스트단지", "매매", 20.0, 40.0, 9000, 13000)
        )
        self.assertTrue(
            self.db.add_alert_setting("12345", "테스트단지", "전세", 20.0, 40.0, 3000, 6000)
        )
        all_rows = self.db.get_all_alert_settings()
        self.assertGreaterEqual(len(all_rows), 2)
        sale_alert_id = None
        for row in all_rows:
            if row["trade_type"] == "매매":
                sale_alert_id = row["id"]
                break
        self.assertIsNotNone(sale_alert_id)
        self.db.toggle_alert_setting(sale_alert_id, False)

        rules_sale = self.db.get_enabled_alert_rules("12345", "매매")
        rules_jeonse = self.db.get_enabled_alert_rules("12345", "전세")
        self.assertEqual(len(rules_sale), 0)
        self.assertEqual(len(rules_jeonse), 1)

    def test_backup_and_restore_preserves_rows(self):
        self.assertTrue(self.db.add_complex("원본단지", "A-100"))
        backup_path = os.path.join(self.tmp.name, "backup_snapshot.db")
        self.assertTrue(self.db.backup_database(backup_path))
        self.assertTrue(os.path.exists(backup_path))

        self.assertTrue(self.db.add_complex("추가단지", "A-200"))
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
                ("레거시단지", "LEG-001", ""),
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


if __name__ == "__main__":
    unittest.main()
