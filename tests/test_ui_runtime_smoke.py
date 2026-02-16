import importlib.util
import os
import tempfile
import unittest


# Ensure headless-friendly Qt platform for CI runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIRuntimeSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_real_estate_app_instantiation(self):
        from src.ui.app import RealEstateApp

        w = RealEstateApp()

        # Prevent background activity leaking into other tests.
        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            # Avoid calling close()/quit paths; they can block in headless test runs.
            w.tray_icon.hide()

        # Close DB connections explicitly (RealEstateApp.closeEvent calls this, but close can block).
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()

    def test_dialogs_instantiation(self):
        from src.ui.dialogs import URLBatchDialog, AdvancedFilterDialog

        d1 = URLBatchDialog()
        d2 = AdvancedFilterDialog()
        d1.deleteLater()
        d2.deleteLater()
        self._qt_app.processEvents()

    def test_crawler_tab_batch_render_smoke(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab
        from PyQt6.QtWidgets import QLabel

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "test_ui_batch.db"))
            tab = CrawlerTab(db)
            sample = [
                {
                    "단지명": "A단지",
                    "단지ID": "11111",
                    "거래유형": "매매",
                    "매매가": "10억",
                    "보증금": "",
                    "월세": "",
                    "면적(평)": 34.0,
                    "평당가_표시": "2,941만/평",
                    "층/방향": "10/20층 남향",
                    "타입/특징": "올수리",
                    "매물ID": "A1",
                    "수집시각": "2026-02-16 10:00:00",
                },
                {
                    "단지명": "B단지",
                    "단지ID": "22222",
                    "거래유형": "전세",
                    "매매가": "",
                    "보증금": "5억",
                    "월세": "",
                    "면적(평)": 25.0,
                    "평당가_표시": "2,000만/평",
                    "층/방향": "5/15층 동향",
                    "타입/특징": "역세권",
                    "매물ID": "B1",
                    "수집시각": "2026-02-16 10:00:01",
                },
            ]

            tab._on_items_batch(sample)
            self.assertEqual(tab.result_table.rowCount(), 2)
            self.assertEqual(len(tab.collected_data), 2)

            tab._update_stats_ui({
                "total_found": 2,
                "filtered_out": 0,
                "cache_hits": 0,
                "by_trade_type": {"매매": 1, "전세": 1, "월세": 0},
            })
            total_value = tab.summary_card.total_widget.findChild(QLabel, "value")
            self.assertIsNotNone(total_value)
            self.assertEqual(total_value.text(), "2건")

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()
