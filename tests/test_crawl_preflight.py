"""수집 시작 전 점검(조건 범위·확인·입력 잠금)과 완료 요약 회귀 테스트."""

import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestCrawlPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        from src.core.crawl_lock import reset_crawl_lock_for_tests
        from src.core.database import ComplexDatabase
        from src.ui.widgets.crawler_tab import CrawlerTab

        reset_crawl_lock_for_tests()
        self._tmp = tempfile.TemporaryDirectory()
        self.db = ComplexDatabase(os.path.join(self._tmp.name, "preflight.db"))
        self.tab = CrawlerTab(self.db)

    def tearDown(self):
        from src.core.crawl_lock import reset_crawl_lock_for_tests

        self.db.close()
        self.tab.deleteLater()
        self._qt_app.processEvents()
        self._tmp.cleanup()
        reset_crawl_lock_for_tests()

    def test_inverted_area_range_blocks_start_and_opens_panel(self):
        from src.core.crawl_lock import get_crawl_lock
        from src.core.crawler import CrawlerThread

        tab = self.tab
        tab.add_task("테스트단지", "12345")
        tab.check_area_filter.setChecked(True)
        tab.btn_filter_toggle.setChecked(False)
        tab.spin_area_min.setValue(120)
        tab.spin_area_max.setValue(60)

        self.assertEqual([name for name, _spin in tab._filter_range_issues()], ["면적"])
        self.assertFalse(tab.lbl_filter_error.isHidden())
        self.assertIn("확인 필요", tab.lbl_filter_summary.text())

        with patch.object(CrawlerThread, "start", return_value=None) as mock_start:
            self.assertFalse(tab.start_crawling())

        mock_start.assert_not_called()
        self.assertTrue(tab.btn_filter_toggle.isChecked())
        self.assertIsNone(get_crawl_lock().owner())
        self.assertTrue(tab.btn_start.isEnabled())

    def test_price_range_of_unchecked_trade_type_is_ignored(self):
        tab = self.tab
        tab.check_monthly.setChecked(False)
        tab.check_price_filter.setChecked(True)
        tab.spin_monthly_rent_min.setValue(900)
        tab.spin_monthly_rent_max.setValue(100)

        self.assertEqual(tab._filter_range_issues(), [])
        self.assertFalse(tab.spin_monthly_rent_min.isEnabled())
        self.assertTrue(tab.spin_trade_min.isEnabled())

        tab.check_monthly.setChecked(True)
        self.assertTrue(tab.spin_monthly_rent_min.isEnabled())
        self.assertEqual([name for name, _spin in tab._filter_range_issues()], ["월세"])

    def test_filter_hints_show_pyeong_and_eok(self):
        tab = self.tab
        tab.check_area_filter.setChecked(True)
        tab.spin_area_min.setValue(59)
        tab.spin_area_max.setValue(84)
        tab.check_price_filter.setChecked(True)
        tab.spin_trade_max.setValue(100000)

        self.assertEqual(tab.lbl_area_hint.text(), "약 18평 ~ 25평")
        self.assertIn("매매 0 ~ 10억", tab.lbl_price_hint.text())
        self.assertIn("면적 59~84㎡", tab._filter_summary_text())

    def test_pasting_complex_url_fills_id_and_asset_type(self):
        from src.utils.helpers import get_complex_url

        tab = self.tab
        tab.input_id.setText(get_complex_url("34567", "VL"))

        self.assertEqual(tab.input_id.text(), "34567")
        self.assertEqual(tab.combo_manual_asset.currentData(), "VL")

    def test_inputs_lock_while_crawling_and_unlock_on_finish(self):
        from src.core.crawler import CrawlerThread

        tab = self.tab
        tab.add_task("단지A", "111")
        tab.add_task("단지B", "222")
        tab.table_list.selectRow(0)

        with patch.object(CrawlerThread, "start", return_value=None):
            self.assertTrue(tab.start_crawling())

        self.assertFalse(tab.btn_find_complex.isEnabled())
        self.assertFalse(tab.check_trade.isEnabled())
        self.assertFalse(tab.filter_panel.isEnabled())
        self.assertFalse(tab.btn_list_clear.isEnabled())
        self.assertFalse(tab.btn_list_delete.isEnabled())
        self.assertFalse(tab.lbl_inputs_locked.isHidden())

        with (
            patch("src.ui.widgets.crawler_tab.QApplication.beep"),
            patch.object(tab, "_save_price_snapshots", return_value=None),
        ):
            tab._on_crawl_finished([])

        self.assertTrue(tab.btn_find_complex.isEnabled())
        self.assertTrue(tab.check_trade.isEnabled())
        self.assertTrue(tab.filter_panel.isEnabled())
        self.assertTrue(tab.btn_list_clear.isEnabled())
        self.assertTrue(tab.lbl_inputs_locked.isHidden())

    def test_stopped_crawl_is_not_reported_as_complete(self):
        tab = self.tab
        tab.crawler_thread = None
        tab._stop_requested = True
        tab.progress_widget.progress_bar.setValue(40)
        messages = []
        tab.status_message.connect(messages.append)

        with (
            patch("src.ui.widgets.crawler_tab.QApplication.beep"),
            patch.object(tab, "_save_price_snapshots", return_value=None),
        ):
            tab._on_crawl_finished([{"단지명": "A"}])

        self.assertEqual(tab.progress_widget.progress_bar.value(), 40)
        self.assertIn("중지", tab.progress_widget.status_label.text())
        self.assertTrue(any("중지" in message for message in messages))
        self.assertFalse(tab.run_summary.isHidden())
        self.assertIn("중지", tab.lbl_run_summary.text())

    def test_run_summary_texts(self):
        tab = self.tab
        head, notes = tab._run_summary_texts(
            12,
            {"new_count": 3, "price_down": 2, "filtered_out": 5, "block_like_redirect_count": 1},
            stopped=False,
            elapsed_text="1분 5초",
        )
        self.assertEqual(head, "수집 완료 · 매물 12건 · 신규 3건 · 가격 하락 2건 · 소요 1분 5초")
        self.assertIn("뺀 매물 5건", notes)
        self.assertIn("접속을 제한", notes)

        head, notes = tab._run_summary_texts(0, {"filtered_out": 7}, stopped=False)
        self.assertIn("조건에 맞는 매물이 없습니다", head)
        self.assertIn("조건을 넓히면", notes)

    def test_request_start_asks_before_discarding_unsaved_results(self):
        from PyQt6.QtWidgets import QMessageBox

        tab = self.tab
        tab.collected_data = [{"단지명": "A"}]

        with (
            patch(
                "src.ui.widgets.crawler_tab.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as mock_question,
            patch.object(tab, "start_crawling", return_value=True) as mock_start,
        ):
            self.assertFalse(tab.request_start())
        mock_question.assert_called_once()
        mock_start.assert_not_called()

        tab._results_exported = True
        with (
            patch("src.ui.widgets.crawler_tab.QMessageBox.question") as mock_question,
            patch.object(tab, "start_crawling", return_value=True) as mock_start,
        ):
            self.assertTrue(tab.request_start())
        mock_question.assert_not_called()
        mock_start.assert_called_once()

    def test_clear_list_confirms_when_several_complexes(self):
        from PyQt6.QtWidgets import QMessageBox

        tab = self.tab
        tab.add_task("단지A", "111")
        tab.add_task("단지B", "222")

        with patch(
            "src.ui.widgets.crawler_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            tab._clear_list()
        self.assertEqual(tab.table_list.rowCount(), 2)

        with patch(
            "src.ui.widgets.crawler_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab._clear_list()
        self.assertEqual(tab.table_list.rowCount(), 0)

    def test_sort_menu_marks_current_order_and_sorts_by_pyeong_price(self):
        tab = self.tab
        tab.combo_sort.setCurrentText("평당가 ↓")

        checked = [c for c, action in tab._sort_menu_actions.items() if action.isChecked()]
        self.assertEqual(checked, ["평당가 ↓"])

        rows = [{"단지명": "A", "평당가": 1000}, {"단지명": "B", "평당가": 3000}]
        tab._sort_compact_rows(rows)
        self.assertEqual([row["단지명"] for row in rows], ["B", "A"])

    def test_advanced_filter_dialog_rejects_inverted_range(self):
        from src.ui.dialogs import AdvancedFilterDialog

        dialog = AdvancedFilterDialog(self.tab)
        dialog.price_min.setValue(50000)
        dialog.price_max.setValue(10000)
        with patch("src.ui.dialogs.filter.QMessageBox.warning") as mock_warning:
            dialog._apply()
        mock_warning.assert_called_once()
        self.assertIsNone(dialog.get_filters())

        dialog.price_max.setValue(0)  # 「제한 없음」으로 보이는 값
        dialog._apply()
        applied = dialog.get_filters()
        assert applied is not None
        self.assertEqual(applied["price_max"], dialog.price_max.maximum())
        dialog.deleteLater()


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestGeoPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_default_location_is_confirmed_and_range_is_explained(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.core.database import ComplexDatabase
        from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "geo_preflight.db"))
            tab = GeoCrawlerTab(db)
            lat, lon = tab.DEFAULT_GEO_CENTER
            tab._applying_geo_profile = True
            tab.spin_lat.setValue(lat)
            tab.spin_lon.setValue(lon)
            tab._applying_geo_profile = False
            tab._geo_place_name = ""

            tab.spin_rings.setValue(2)
            self.assertIn("25화면", tab.lbl_geo_range.text())

            with (
                patch(
                    "src.ui.widgets.geo_crawler_tab.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.No,
                ) as mock_question,
                patch.object(tab, "start_crawling", return_value=True) as mock_start,
            ):
                self.assertFalse(tab.request_start())
            mock_question.assert_called_once()
            mock_start.assert_not_called()

            tab._geo_place_name = "반포동"
            with (
                patch("src.ui.widgets.geo_crawler_tab.QMessageBox.question") as mock_question,
                patch.object(tab, "start_crawling", return_value=True) as mock_start,
            ):
                self.assertTrue(tab.request_start())
            mock_question.assert_not_called()
            mock_start.assert_called_once()

            db.close()
            tab.deleteLater()
            self._qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()
