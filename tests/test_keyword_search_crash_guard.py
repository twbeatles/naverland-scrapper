"""Crash-guard regression tests for KeywordSearchDialog.

Background: the frozen onedir build (``dist/naverland``, 10:36) shipped
pre-32258ed QThread worker code and died with ``c0000005`` in ``python315.dll``
on complex/region keyword search. 32258ed moved fetches onto a plain pump
thread; these tests pin the containment properties so no worker or parser
failure can wedge (stuck busy spinner) or kill the dialog again.
"""

import json
import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SEARCH_BANPO_RAW = json.dumps(
    {
        "complexes": [
            {
                "complexNo": "22853",
                "complexName": "반포자이",
                "cortarNo": "1165010700",
                "realEstateTypeCode": "APT",
                "latitude": 37.507784,
                "longitude": 127.014484,
                "cortarAddress": "서울시 서초구 반포동",
                "deepLink": "/complexes/22853?&a=APT:ABYG:JGC",
            }
        ],
        "isShown": True,
        "isMoreData": False,
        "keyword": "반포자이",
        "totalCount": 0,
    },
    ensure_ascii=False,
)


class _FakeSession:
    def __init__(self, bodies):
        self._bodies = dict(bodies)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def fetch(self, url):
        for key, value in self._bodies.items():
            if key in url:
                return value
        return 404, ""


def _make_factory(bodies, sessions):
    def _factory():
        session = _FakeSession(bodies)
        sessions.append(session)
        return session

    return _factory


@unittest.skipIf(__import__("importlib").util.find_spec("PySide6") is None, "PySide6 missing")
class TestKeywordSearchCrashGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _pump_until(self, predicate, timeout_sec=15.0):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            self._qt_app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        self._qt_app.processEvents()
        return bool(predicate())

    def _run_search_text(self, dlg, text):
        dlg.input_keyword.setText(text)
        dlg._run_search()

    def test_transport_failure_reports_failed_and_releases_busy(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(session_factory=_make_factory({}, sessions))
        try:
            self._run_search_text(dlg, "반포자이")
            self.assertTrue(self._pump_until(lambda: not dlg._busy, timeout_sec=20.0))
            self.assertIn("검색하지 못했습니다", dlg.status_label.text())
            self.assertEqual(dlg.complex_list.count(), 0)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_invalid_json_reports_failed_and_releases_busy(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, "not-json{{{")}, sessions)
        )
        try:
            self._run_search_text(dlg, "반포자이")
            self.assertTrue(self._pump_until(lambda: not dlg._busy, timeout_sec=20.0))
            self.assertIn("검색하지 못했습니다", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_missing_payload_lists_show_no_results(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory(
                {"api/search": (200, '{"isShown":false,"isMoreData":false}')}, sessions
            )
        )
        try:
            self._run_search_text(dlg, "empty-query-zzz")
            self.assertTrue(self._pump_until(lambda: not dlg._busy))
            self.assertIn("결과가 없습니다", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_malformed_complex_item_still_renders(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        raw = json.dumps(
            {
                "complexes": [
                    {
                        "complexNo": 12345,
                        "complexName": None,
                        "cortarAddress": None,
                        "latitude": "bad",
                        "deepLink": None,
                    }
                ],
                "isMoreData": False,
            }
        )
        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, raw)}, sessions)
        )
        try:
            self._run_search_text(dlg, "12345")
            self.assertTrue(self._pump_until(lambda: not dlg._busy))
            self.assertEqual(dlg.complex_list.count(), 1)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_map_link_parser_error_does_not_raise_or_wedge(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, SEARCH_BANPO_RAW)}, sessions)
        )
        try:
            with patch(
                "src.core.parser.NaverURLParser.extract_from_text",
                side_effect=RuntimeError("parser boom"),
            ):
                self._run_search_text(dlg, "https://new.land.naver.com/complexes/22853")
            self.assertFalse(dlg._busy)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_map_center_parser_error_does_not_raise_or_wedge(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, SEARCH_BANPO_RAW)}, sessions)
        )
        try:
            with (
                patch(
                    "src.core.parser.NaverURLParser.extract_from_text",
                    return_value=[],
                ),
                patch(
                    "src.core.parser.NaverURLParser.extract_map_center",
                    side_effect=RuntimeError("center boom"),
                ),
            ):
                self._run_search_text(dlg, "https://new.land.naver.com/map")
            self.assertFalse(dlg._busy)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_suggest_failure_keeps_search_usable(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory(
                {
                    "autocomplete": (500, ""),
                    "api/search": (200, SEARCH_BANPO_RAW),
                },
                sessions,
            )
        )
        try:
            # Suggest path fails; the search path must still populate rows.
            dlg._enqueue(("suggest", "반포자이", 1))
            self._run_search_text(dlg, "반포자이")
            self.assertTrue(
                self._pump_until(lambda: dlg.complex_list.count() == 1),
                "search rows did not populate after suggest failure",
            )
            self.assertFalse(dlg._busy)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_close_during_search_releases_pump_thread(self):
        import threading

        from src.ui.dialogs.search import KeywordSearchDialog

        release = threading.Event()

        class _BlockingSession(_FakeSession):
            def fetch(self, url):
                release.wait(timeout=10.0)
                return (200, '{"isShown":false,"isMoreData":false}')

        sessions = []

        def _blocking_factory():
            session = _BlockingSession({"api/search": (200, SEARCH_BANPO_RAW)})
            sessions.append(session)
            return session

        dlg = KeywordSearchDialog(session_factory=_blocking_factory)
        try:
            self._run_search_text(dlg, "반포자이")
            thread = dlg._pump_thread
            self.assertIsNotNone(thread)
            dlg.reject()
            release.set()
            assert thread is not None
            thread.join(timeout=10.0)
            self.assertFalse(thread.is_alive(), "pump thread did not exit after close")
        finally:
            release.set()
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
