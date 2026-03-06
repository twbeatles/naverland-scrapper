import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestGeoTabWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_geo_tab_builds_geo_sweep_thread(self):
        from src.core.database import ComplexDatabase
        from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_tab.db"))
            tab = GeoCrawlerTab(db)
            tab.spin_lat.setValue(37.55)
            tab.spin_lon.setValue(126.99)
            tab.check_trade.setChecked(True)

            with patch("src.core.crawler.CrawlerThread.start", return_value=None):
                tab.start_crawling()

            self.assertIsNotNone(tab.crawler_thread)
            self.assertEqual(tab.crawler_thread.crawl_mode, "geo_sweep")
            self.assertEqual(tab.crawler_thread.engine_name, "playwright")
            self.assertIsNotNone(tab.crawler_thread.geo_config)
            self.assertAlmostEqual(tab.crawler_thread.geo_config.lat, 37.55)

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
