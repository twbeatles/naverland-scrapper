import importlib.util
import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestPerformanceSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_result_filter_miss_10k_smoke(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "perf_filter.db"))
            tab = CrawlerTab(db)
            rows = 10000
            cols = tab.result_table.columnCount()
            tab.result_table.setRowCount(rows)
            tab._row_search_cache = []
            for r in range(rows):
                values = []
                for c in range(cols):
                    text = f"row{r} col{c} alpha"
                    values.append(text)
                    tab.result_table.setItem(r, c, QTableWidgetItem(text))
                tab._row_search_cache.append(" ".join(values).lower())

            self._qt_app.processEvents()
            start = time.perf_counter()
            tab._filter_results("zzzzz_not_found")
            self._qt_app.processEvents()
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, 0.6)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()

    def test_append_rows_batch_large_smoke(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "perf_append.db"))
            tab = CrawlerTab(db)
            items = []
            for i in range(3000):
                items.append(
                    {
                        "단지명": f"A단지{i}",
                        "단지ID": "11111",
                        "거래유형": "매매",
                        "매매가": "10000",
                        "보증금": "",
                        "월세": "",
                        "면적(평)": 34.0,
                        "평당가_표시": "294만/평",
                        "층/방향": "10층 남향",
                        "타입/특징": "올수리",
                        "매물ID": f"A{i}",
                        "수집시각": "2026-02-20 10:00:00",
                        "is_new": False,
                        "price_change": 0,
                    }
                )

            start = time.perf_counter()
            tab._append_rows_batch(items)
            self._qt_app.processEvents()
            elapsed = time.perf_counter() - start

            self.assertEqual(tab.result_table.rowCount(), 3000)
            self.assertLess(elapsed, 1.5)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
