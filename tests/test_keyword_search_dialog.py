"""KeywordSearchDialog tests (fake browser session, no network)."""

import json
import os
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Fixtures mirror tests/test_keyword_search.py (live responses, 2026-10-04).
AUTOCOMPLETE_BANPO_RAW = (
    '["<strong class=\'text_input\'>반포</strong>동 '
    '<strong class=\'text_input\'>반포</strong>'
    "<strong class='text_input'>자이</strong>\","
    '"잠원동 메이플<strong class=\'text_input\'>자이</strong>",'
    '"잠원동 <strong class=\'text_input\'>반포</strong>센트럴'
    "<strong class='text_input'>자이</strong>\","
    '"잠원동 신<strong class=\'text_input\'>반포</strong>'
    "<strong class='text_input'>자이</strong>\"]"
)
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
SEARCH_HAPJEONG_REGIONS = {
    "complexes": [],
    "regions": [
        {
            "cortarNo": "1144012200",
            "centerLat": 37.549433,
            "centerLon": 126.905725,
            "cortarName": "서울시 마포구 합정동",
            "cortarType": "sec",
            "deepLink": "/complexes?ms=37.549433,126.905725,16&e=RETAIL",
        }
    ],
    "isShown": True,
    "isMoreData": True,
    "keyword": "합정동",
    "totalCount": 0,
}


class _FakeSession:
    def __init__(self, bodies):
        self._bodies = dict(bodies)
        self.calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def fetch(self, url):
        self.calls.append(url)
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
class TestKeywordSearchDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _pump_until(self, predicate, timeout_sec=10.0):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            self._qt_app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        self._qt_app.processEvents()
        return bool(predicate())

    def test_search_populates_complex_rows(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory(
                {"autocomplete": (200, AUTOCOMPLETE_BANPO_RAW), "api/search": (200, SEARCH_BANPO_RAW)},
                sessions,
            )
        )
        try:
            dlg.input_keyword.setText("반포자이")
            dlg._run_search()
            self.assertTrue(
                self._pump_until(lambda: dlg.complex_list.count() == 1),
                "complex rows did not populate",
            )
            self.assertIn("반포자이", dlg.status_label.text())
            self.assertTrue(
                self._pump_until(lambda: dlg.suggest_list.count() == 4),
                "suggestions did not populate (debounce)",
            )
            self.assertTrue(any("autocomplete" in url for url in sessions[0].calls))
            self.assertTrue(any("api/search" in url for url in sessions[0].calls))
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_checked_complexes_emitted(self):
        from PySide6.QtCore import Qt

        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, SEARCH_BANPO_RAW)}, sessions)
        )
        emitted = []
        try:
            dlg.complexes_added.connect(emitted.append)
            dlg.input_keyword.setText("반포자이")
            dlg._run_search()
            self.assertTrue(self._pump_until(lambda: dlg.complex_list.count() == 1))
            first_row = dlg.complex_list.item(0)
            self.assertIsNotNone(first_row)
            assert first_row is not None
            first_row.setCheckState(Qt.CheckState.Checked)
            dlg._emit_complexes()
            self.assertEqual(emitted, [[("반포자이", "22853", "APT")]])
        finally:
            dlg.deleteLater()

    def test_region_chosen_emitted(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory(
                {"api/search": (200, json.dumps(SEARCH_HAPJEONG_REGIONS, ensure_ascii=False))},
                sessions,
            )
        )
        emitted = []
        try:
            dlg.region_chosen.connect(emitted.append)
            dlg.input_keyword.setText("합정동")
            dlg._run_search()
            self.assertTrue(self._pump_until(lambda: dlg.region_list.count() == 1))
            dlg.region_list.setCurrentRow(0)
            dlg._emit_region()
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0]["cortar_no"], "1144012200")
            self.assertAlmostEqual(emitted[0]["latitude"], 37.549433)
        finally:
            dlg.deleteLater()

    def test_no_results_status(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory(
                {"api/search": (200, '{"isShown":false,"isMoreData":false}')} , sessions)
        )
        try:
            dlg.input_keyword.setText("empty-query-zzz")
            dlg._run_search()
            self.assertTrue(
                self._pump_until(lambda: not dlg._busy),
                "search did not finish",
            )
            self.assertIn("결과가 없습니다", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()


@unittest.skipIf(__import__("importlib").util.find_spec("PySide6") is None, "PySide6 missing")
class TestKeywordWorkerSessionCleanup(unittest.TestCase):
    """ISSUE-001: failed __enter__ must still release acquired resources."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_enter_failure_calls_exit(self):
        from src.ui.dialogs.search import _KeywordWorker

        calls = {"enter": 0, "exit": 0, "failed": []}

        class _FailingSession:
            def __enter__(self):
                calls["enter"] += 1
                raise RuntimeError("no browser")

            def __exit__(self, *args):
                calls["exit"] += 1
                return False

            def fetch(self, url):
                return (500, "")

        worker = _KeywordWorker(session_factory=_FailingSession)
        try:
            worker.failed.connect(
                lambda msg, gen, kind: calls["failed"].append((msg, gen, kind)))
            worker.suggest("test", 1)
            self._qt_app.processEvents()
            self.assertEqual(calls["enter"], 1)
            self.assertEqual(calls["exit"], 1)
            self.assertEqual(len(calls["failed"]), 1)
            self.assertIsNone(worker._session)
        finally:
            worker.deleteLater()

    def test_enter_failure_does_not_cache_session(self):
        from src.ui.dialogs.search import _KeywordWorker

        attempts = {"count": 0}

        class _FailingSession:
            def __enter__(self):
                attempts["count"] += 1
                raise RuntimeError("no browser")

            def __exit__(self, *args):
                return False

            def fetch(self, url):
                return (500, "")

        worker = _KeywordWorker(session_factory=_FailingSession)
        try:
            worker.suggest("a", 1)
            worker.suggest("b", 2)
            # Each attempt retries session creation (nothing cached on failure).
            self.assertEqual(attempts["count"], 2)
            self.assertIsNone(worker._session)
        finally:
            worker.deleteLater()


@unittest.skipIf(__import__("importlib").util.find_spec("PySide6") is None, "PySide6 missing")
class TestKeywordWorkerResilience(unittest.TestCase):
    """Retry-once, cooldown, and generation guards (audit §5)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _flaky_session(self, bodies_sequence, sessions):
        state = {"calls": 0}

        class _FlakySession:
            def __enter__(self):
                sessions.append(self)
                return self

            def __exit__(self, *args):
                return False

            def fetch(self, url):
                idx = min(state["calls"], len(bodies_sequence) - 1)
                state["calls"] += 1
                return bodies_sequence[idx]

        return _FlakySession, state

    def test_search_retry_once_then_succeeds(self):
        from src.ui.dialogs.search import _KeywordWorker

        sessions = []
        factory, state = self._flaky_session([(429, ""), (200, SEARCH_BANPO_RAW)], sessions)
        worker = _KeywordWorker(session_factory=factory, retry_delay_sec=0.0)
        ready, failed = [], []
        try:
            worker.search_ready.connect(lambda result, gen, append: ready.append((result, gen)))
            worker.failed.connect(lambda msg, gen, kind: failed.append((msg, gen, kind)))
            worker.search("반포자이", 1, 7, False)
            self._qt_app.processEvents()
            # 429, then the retry: fin rejects the legacy-shaped body, new.land parses it.
            self.assertEqual(state["calls"], 3)
            self.assertEqual(len(ready), 1)
            self.assertEqual(len(ready[0][0]["complexes"]), 1)
            self.assertEqual(failed, [])
        finally:
            worker.deleteLater()

    def test_search_retry_exhausted_emits_kind(self):
        from src.ui.dialogs.search import _KeywordWorker

        sessions = []
        factory, state = self._flaky_session([(500, "oops")], sessions)
        worker = _KeywordWorker(session_factory=factory, retry_delay_sec=0.0)
        ready, failed = [], []
        try:
            worker.search_ready.connect(lambda result, gen, append: ready.append(result))
            worker.failed.connect(lambda msg, gen, kind: failed.append((msg, gen, kind)))
            worker.search("a", 1, 3, False)
            self._qt_app.processEvents()
            # Two attempts, each trying fin then the legacy new.land fallback.
            self.assertEqual(state["calls"], 4)
            self.assertEqual(ready, [])
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0][1], 3)
            self.assertEqual(failed[0][2], "search")
        finally:
            worker.deleteLater()

    def test_rate_limit_cooldown_short_circuits(self):
        from src.ui.dialogs.search import _KeywordWorker

        sessions = []
        factory, state = self._flaky_session([(429, "")], sessions)
        worker = _KeywordWorker(
            session_factory=factory, retry_delay_sec=0.0, rate_limit_cooldown_sec=3600.0)
        failed = []
        try:
            worker.failed.connect(lambda msg, gen, kind: failed.append((msg, gen, kind)))
            worker.search("a", 1, 1, False)
            first_calls = state["calls"]
            self.assertGreater(first_calls, 0)
            worker.search("a", 1, 2, False)
            self._qt_app.processEvents()
            # Second request never reaches the network; cooldown message instead.
            self.assertEqual(state["calls"], first_calls)
            self.assertEqual(len(failed), 2)
            self.assertIn("잠시 쉬는 중", failed[1][0])
        finally:
            worker.deleteLater()

    def test_suggest_cooldown_is_silent(self):
        from src.ui.dialogs.search import _KeywordWorker

        sessions = []
        factory, state = self._flaky_session([(200, SEARCH_BANPO_RAW)], sessions)
        worker = _KeywordWorker(
            session_factory=factory, retry_delay_sec=0.0, rate_limit_cooldown_sec=3600.0)
        worker._note_rate_limit()
        ready, failed = [], []
        try:
            worker.suggestions_ready.connect(lambda names, gen: ready.append(names))
            worker.failed.connect(lambda msg, gen, kind: failed.append((msg, gen, kind)))
            worker.suggest("a", 1)
            self._qt_app.processEvents()
            self.assertEqual(ready, [])
            self.assertEqual(failed, [])
            self.assertEqual(state["calls"], 0)
        finally:
            worker.deleteLater()

    def test_stale_search_failure_ignored(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, SEARCH_BANPO_RAW)}, sessions))
        try:
            dlg._busy = True
            dlg._search_generation = 5
            before = dlg.status_label.text()
            dlg._on_worker_failed("stale boom", 4, "search")
            self.assertTrue(dlg._busy)
            self.assertEqual(dlg.status_label.text(), before)
            dlg._on_worker_failed("fresh boom", 5, "search")
            self.assertFalse(dlg._busy)
            self.assertIn("fresh boom", dlg.status_label.text())
        finally:
            dlg.deleteLater()

    def test_suggest_failure_never_clears_search_busy(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=_make_factory({"api/search": (200, SEARCH_BANPO_RAW)}, sessions))
        try:
            dlg._busy = True
            dlg._generation = 9
            dlg._on_worker_failed("suggest boom", 9, "suggest")
            self.assertTrue(dlg._busy)
        finally:
            dlg.deleteLater()


@unittest.skipIf(__import__("importlib").util.find_spec("PySide6") is None, "PySide6 missing")
class TestKeywordSearchDialogHardening(unittest.TestCase):
    """Refactor guards: null payloads, address fallback, map links, shutdown."""

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

    def test_null_lists_do_not_stick_busy(self):
        """API explicit nulls must render as 'no results', not wedge the dialog."""
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(session_factory=lambda: None)
        try:
            dlg._search_generation = 1
            dlg._keyword = "분당구"
            dlg._busy = True
            dlg._on_search_ready(
                {"complexes": None, "regions": None, "is_more_data": False}, 1, False
            )
            self.assertFalse(dlg._busy)
            self.assertEqual(dlg.complex_list.count(), 0)
            self.assertEqual(dlg.region_list.count(), 0)
            self.assertIn("결과가 없습니다", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_address_fallback_keeps_effective_query_for_more(self):
        """Full address with empty raw hit resolves via dong; page 2 reuses it."""
        from src.ui.dialogs.search import KeywordSearchDialog

        second_page = json.dumps(
            {"complexes": [], "regions": [], "isShown": False,
             "isMoreData": False, "keyword": "반포동"},
            ensure_ascii=False,
        )
        first_page = json.dumps(
            {"complexes": [
                {"complexNo": "22853", "complexName": "반포자이",
                 "realEstateTypeCode": "APT",
                 "cortarAddress": "서울시 서초구 반포동",
                 "deepLink": "/complexes/22853"}],
             "isShown": True, "isMoreData": True, "keyword": "반포동"},
            ensure_ascii=False,
        )
        calls = []

        class _Session:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def fetch(self, url):
                keyword = parse_qs(urlparse(url).query).get("keyword", [""])[0]
                page = parse_qs(urlparse(url).query).get("page", ["1"])[0]
                calls.append((keyword, page))
                if "api/search" in url and keyword == "반포동":
                    return (200, first_page if page == "1" else second_page)
                return (200, '{"isShown":false,"isMoreData":false}')

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=lambda: sessions.append(_Session()) or sessions[-1]
        )
        try:
            dlg.input_keyword.setText("서울특별시 서초구 반포동")
            dlg._run_search()
            self.assertTrue(
                self._pump_until(lambda: dlg.complex_list.count() == 1),
                "fallback search did not populate",
            )
            self.assertEqual(dlg._search_query, "반포동")
            searched = [kw for kw, _pg in calls if kw]
            self.assertEqual(searched[0], "서울특별시 서초구 반포동")
            self.assertIn("반포동", searched)
            dlg._load_more()
            self.assertTrue(
                self._pump_until(lambda: not dlg._busy),
                "second page did not finish",
            )
            pages = [(kw, pg) for kw, pg in calls if pg == "2"]
            self.assertTrue(pages, "no page-2 fetch observed")
            self.assertTrue(all(kw == "반포동" for kw, _pg in pages))
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_map_link_ms_center_becomes_region_row(self):
        """new.land map links (ms=lat,lon,zoom) give a usable row without waiting on network.

        Naming the point (fin searchByCoordinate) only happens in the background.
        """
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(mode="region", session_factory=lambda: None)
        try:
            dlg.input_keyword.setText(
                "https://new.land.naver.com/complexes?ms=37.5494,126.9057,16&a=APT:ABYG:JGC"
            )
            dlg._run_search()
            self.assertEqual(dlg.region_list.count(), 1, "map-link region row missing")
            data = dlg.region_list.item(0).data(
                __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole
            )
            self.assertAlmostEqual(data["latitude"], 37.5494)
            self.assertAlmostEqual(data["longitude"], 126.9057)
            self.assertFalse(dlg._busy)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_located_region_name_replaces_coordinate_label(self):
        from PySide6.QtCore import Qt
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(mode="region", session_factory=lambda: None)
        try:
            dlg.input_keyword.setText("https://fin.land.naver.com/map?center=3zkT1e-2AM2FA&zoom=15")
            dlg._run_search()
            dlg._on_region_located(
                {"cortar_no": "1123010500", "name": "서울시 동대문구 답십리동"}, dlg._search_generation
            )
            item = dlg.region_list.item(0)
            self.assertIn("답십리동", item.text())
            data = item.data(Qt.ItemDataRole.UserRole)
            self.assertEqual(data["cortar_no"], "1123010500")
            self.assertAlmostEqual(data["latitude"], 37.566377, places=5)
            # A stale generation must not rename rows of a newer search.
            dlg._on_region_located({"cortar_no": "1", "name": "다른 곳"}, dlg._search_generation - 1)
            self.assertIn("답십리동", dlg.region_list.item(0).text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_fin_viewport_link_resolves_center(self):
        """fin.land viewport links carry no IDs but a base62 center (2026-10-22)."""
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(session_factory=lambda: None)
        try:
            dlg.input_keyword.setText(
                "https://fin.land.naver.com/map?center=3zkT1e-2AM2FA&zoom=15.6"
            )
            dlg._run_search()
            self.assertFalse(dlg._busy)
            self.assertIn("지도 링크의 위치를 찾았습니다", dlg.status_label.text())
            self.assertEqual(dlg.region_list.count(), 1)
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_viewport_link_without_center_shows_guidance(self):
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(session_factory=lambda: None)
        try:
            dlg.input_keyword.setText("https://fin.land.naver.com/map?tradeTypes=A1-B1")
            dlg._run_search()
            self.assertFalse(dlg._busy)
            self.assertIn("단지 정보가 없어요", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_resolve_pasted_complex_link(self):
        """Pasted complex URLs resolve to checkable rows via name lookup."""
        from src.ui.dialogs.search import KeywordSearchDialog

        class _Session:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def fetch(self, url):
                raise AssertionError("resolve path must not hit the network")

        sessions = []
        dlg = KeywordSearchDialog(
            session_factory=lambda: sessions.append(_Session()) or sessions[-1]
        )
        try:
            with patch(
                "src.core.parser.NaverURLParser.fetch_complex_name",
                return_value="반포자이",
            ):
                dlg.input_keyword.setText("https://new.land.naver.com/complexes/22853")
                dlg._run_search()
                self.assertTrue(
                    self._pump_until(lambda: dlg.complex_list.count() == 1),
                    "resolved row missing",
                )
                row = dlg.complex_list.item(0)
                self.assertIn("반포자이", row.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_late_suggest_failure_keeps_search_status(self):
        """A late autocomplete failure must not clobber the search status."""
        from src.ui.dialogs.search import KeywordSearchDialog

        dlg = KeywordSearchDialog(session_factory=lambda: None)
        try:
            dlg._search_generation = 2
            dlg._keyword = "반포자이"
            dlg._busy = True
            dlg._on_search_ready(
                {"complexes": [{"complex_id": "22853", "name": "반포자이",
                                "address": "", "asset_type": "APT"}],
                 "regions": [], "is_more_data": False},
                2, False,
            )
            self.assertIn("단지 1곳", dlg.status_label.text())
            dlg._generation = 5
            dlg._on_worker_failed("boom", 5, "suggest")
            self.assertIn("단지 1곳", dlg.status_label.text())
        finally:
            dlg.reject()
            dlg.deleteLater()

    def test_close_during_slow_search_exits_pump(self):
        """Closing mid-flight must stop the pump without hanging the dialog."""
        from src.ui.dialogs.search import KeywordSearchDialog

        class _SlowSession:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def fetch(self, url):
                time.sleep(2.0)
                return (200, '{"isShown":false,"isMoreData":false}')

        dlg = KeywordSearchDialog(session_factory=_SlowSession)
        try:
            dlg.input_keyword.setText("분당구")
            dlg._run_search()
            self.assertTrue(
                self._pump_until(lambda: dlg._pump_thread is not None),
                "pump thread did not start",
            )
            time.sleep(0.5)
            dlg.reject()
            thread = dlg._pump_thread
            # reject() already shut the pump down; the thread must be gone or
            # finish on its own shortly after its in-flight fetch returns.
            if thread is not None:
                thread.join(timeout=10.0)
                self.assertFalse(thread.is_alive())
        finally:
            try:
                dlg.reject()
            except Exception:
                pass
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
