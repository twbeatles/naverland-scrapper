import os
import tempfile
import unittest

from src.core.database import ComplexDatabase


class TestDatabaseEngineExtensions(unittest.TestCase):
    def test_crawl_history_extended_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "extended.db"))
            self.assertTrue(
                db.add_crawl_history(
                    "테스트단지",
                    "12345",
                    "매매,전세",
                    7,
                    engine="playwright",
                    mode="geo_sweep",
                    source_lat=37.5,
                    source_lon=127.0,
                    source_zoom=15,
                    asset_type="APT",
                )
            )
            conn = db._pool.get_connection()
            try:
                row = conn.cursor().execute(
                    "SELECT engine, mode, source_lat, source_lon, source_zoom, asset_type FROM crawl_history LIMIT 1"
                ).fetchone()
            finally:
                db._pool.return_connection(conn)
            self.assertEqual(row["engine"], "playwright")
            self.assertEqual(row["mode"], "geo_sweep")
            self.assertEqual(row["asset_type"], "APT")
            db.close()

    def test_article_history_upsert_persists_extended_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "article_extended.db"))
            saved = db.upsert_article_history_bulk(
                [
                    {
                        "article_id": "A1",
                        "complex_id": "12345",
                        "complex_name": "테스트단지",
                        "trade_type": "매매",
                        "price": 10000,
                        "price_text": "1억",
                        "area": 30.0,
                        "floor": "10층 남향",
                        "feature": "올수리",
                        "last_price": 10000,
                        "asset_type": "VL",
                        "source_mode": "geo_sweep",
                        "source_lat": 37.5,
                        "source_lon": 127.0,
                        "source_zoom": 15,
                        "marker_id": "M1",
                        "broker_office": "테스트부동산",
                        "broker_name": "홍길동",
                        "broker_phone1": "02-1111-2222",
                        "broker_phone2": "010-1111-2222",
                        "prev_jeonse_won": 90000000,
                        "jeonse_period_years": 3,
                        "jeonse_max_won": 95000000,
                        "jeonse_min_won": 85000000,
                        "gap_amount_won": 10000000,
                        "gap_ratio": 0.1,
                    }
                ]
            )
            self.assertEqual(saved, 1)
            conn = db._pool.get_connection()
            try:
                row = conn.cursor().execute(
                    """
                    SELECT asset_type, source_mode, broker_office, broker_name,
                           prev_jeonse_won, gap_amount_won, gap_ratio
                    FROM article_history WHERE article_id='A1'
                    """
                ).fetchone()
            finally:
                db._pool.return_connection(conn)
            self.assertEqual(row["asset_type"], "VL")
            self.assertEqual(row["source_mode"], "geo_sweep")
            self.assertEqual(row["broker_office"], "테스트부동산")
            self.assertEqual(int(row["prev_jeonse_won"]), 90000000)
            self.assertEqual(int(row["gap_amount_won"]), 10000000)
            self.assertAlmostEqual(float(row["gap_ratio"]), 0.1)
            db.close()


if __name__ == "__main__":
    unittest.main()
