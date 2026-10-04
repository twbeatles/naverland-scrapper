"""Result-filter upgrades: normalized match, address blob, include AND mode."""

import os
import unittest
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui.widgets.crawler_tab import CrawlerTab as C


def _base_payload(overrides=None):
    payload = {
        "price_int": 150000,
        "면적(평)": 25.0,
        "층/방향": "5층 남향",
        "is_new": False,
        "price_change": 0,
        "단지명": "반포 래미안 퍼스티지",
        "타입/특징": "84m 급매 역세권",
    }
    payload.update(overrides or {})
    return payload


def _default_filters(**overrides):
    filters = {
        "price_min": 0,
        "price_max": 9999999,
        "area_min": 0,
        "area_max": 500,
        "floor_low": True,
        "floor_mid": True,
        "floor_high": True,
        "only_new": False,
        "only_price_down": False,
        "only_price_change": False,
        "include_keywords": [],
        "exclude_keywords": [],
        "include_mode": "any",
    }
    filters.update(overrides)
    return filters


class _Stub:
    # Instance attributes (functions stored on the instance do not bind
    # ``self``, matching how the rebound methods behave on CrawlerTab).
    _advanced_filters: Any
    _area_float: Any
    _floor_category: Any
    _keyword_text_blob: Any
    _match_keyword: Any

    def __init__(self, filters=None):
        self._advanced_filters = filters
        self._area_float = C._area_float
        self._floor_category = C._floor_category
        self._keyword_text_blob = C._keyword_text_blob.__get__(self)
        self._match_keyword = C._match_keyword


def _check(payload, filters):
    return C._check_advanced_filter(_Stub(filters), payload)


class TestKeywordMatching(unittest.TestCase):
    def test_normalize_removes_whitespace(self):
        self.assertEqual(C._normalize_search_text("역 세권"), "역세권")
        self.assertEqual(C._normalize_search_text("Raemian First"), "raemianfirst")

    def test_match_keyword_spacing_tolerant(self):
        self.assertTrue(C._match_keyword("역 세권", "84m 급매 역세권"))
        self.assertTrue(C._match_keyword("급매", "84m 급매 역세권"))
        self.assertFalse(C._match_keyword("반지하", "84m 급매 역세권"))

    def test_blob_covers_broker_and_address_keys(self):
        blob = C._keyword_text_blob(_Stub(), _base_payload({
            "부동산상호": "한빛공인중개사",
            "주소": "서울시 서초구 반포동",
        }))
        self.assertIn("한빛공인중개사", blob)
        self.assertIn("서초구", blob)

    def test_include_matches_address_now(self):
        self.assertTrue(
            _check(_base_payload({"주소": "서울시 서초구 반포동"}),
                   _default_filters(include_keywords=["서초구"]))
        )

    def test_include_spacing_tolerant(self):
        self.assertTrue(
            _check(_base_payload(), _default_filters(include_keywords=["역 세권"]))
        )

    def test_include_or_default(self):
        self.assertTrue(
            _check(_base_payload(), _default_filters(include_keywords=["급매", "반지하"]))
        )

    def test_include_all_mode(self):
        self.assertFalse(
            _check(_base_payload(),
                   _default_filters(include_keywords=["급매", "반지하"], include_mode="all"))
        )
        self.assertTrue(
            _check(_base_payload(),
                   _default_filters(include_keywords=["급매", "역세권"], include_mode="all"))
        )

    def test_exclude_spacing_tolerant(self):
        self.assertFalse(
            _check(_base_payload(), _default_filters(exclude_keywords=["역 세권"]))
        )

    def test_is_default_empty_and_mode(self):
        self.assertTrue(C._is_default_advanced_filter(None))
        self.assertTrue(C._is_default_advanced_filter({}))
        self.assertTrue(C._is_default_advanced_filter(_default_filters()))
        self.assertFalse(C._is_default_advanced_filter(_default_filters(include_mode="all")))
        self.assertFalse(C._is_default_advanced_filter(_default_filters(include_keywords=["a"])))


@unittest.skipIf(__import__("importlib").util.find_spec("PyQt6") is None, "PyQt6 missing")
class TestAdvancedFilterDialogMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_include_mode_roundtrip(self):
        from src.ui.dialogs.filter import AdvancedFilterDialog

        dlg = AdvancedFilterDialog()
        try:
            dlg.include_keywords.setText("급매, 역세권")
            dlg.include_all.setChecked(True)
            dlg._apply()
            filters = dlg.get_filters()
            self.assertIsNotNone(filters)
            assert filters is not None
            self.assertEqual(filters["include_mode"], "all")

            dlg2 = AdvancedFilterDialog(current_filters=filters)
            try:
                self.assertTrue(dlg2.include_all.isChecked())
            finally:
                dlg2.deleteLater()
        finally:
            dlg.deleteLater()

    def test_default_mode_is_any(self):
        from src.ui.dialogs.filter import AdvancedFilterDialog

        dlg = AdvancedFilterDialog()
        try:
            dlg._apply()
            filters = dlg.get_filters()
            self.assertIsNotNone(filters)
            assert filters is not None
            self.assertEqual(filters["include_mode"], "any")
        finally:
            dlg.deleteLater()


@unittest.skipIf(__import__("importlib").util.find_spec("PyQt6") is None, "PyQt6 missing")
class TestCardSearchNormalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_filter_cards_spacing_tolerant(self):
        # CardViewWidget.__init__ builds Fluent children that cannot
        # instantiate in a bare offscreen env (pre-existing); exercise the
        # real _apply_filter matching on a stub instance instead.
        from types import SimpleNamespace
        from typing import cast
        from unittest.mock import MagicMock

        from src.ui.widgets.cards import CardViewWidget

        article = {"단지명": "반포 래미안 퍼스티지", "타입/특징": "급매"}
        view = SimpleNamespace(
            _normalize_search_text=CardViewWidget._normalize_search_text,
            _relayout_rendered_cards=lambda: None,
            _all_data=[article],
            _search_text_cache=[CardViewWidget._build_search_text(article)],
            _search_text_norm_cache=[],
            _filter_text="",
            _filtered_data=[],
            empty_label=MagicMock(),
        )
        card_view = cast("CardViewWidget", view)
        view._filter_text = "래미안퍼스티지"
        CardViewWidget._apply_filter(card_view, reset_view=False)
        self.assertEqual(len(view._filtered_data), 1)
        view._filter_text = "래미안 퍼스티지"
        CardViewWidget._apply_filter(card_view, reset_view=False)
        self.assertEqual(len(view._filtered_data), 1)
        view._filter_text = "없는단지"
        CardViewWidget._apply_filter(card_view, reset_view=False)
        self.assertEqual(len(view._filtered_data), 0)


if __name__ == "__main__":
    unittest.main()
