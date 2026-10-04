"""KeywordSearchDialog tests (fake browser session, no network)."""

import json
import os
import time
import unittest

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


@unittest.skipIf(__import__("importlib").util.find_spec("PyQt6") is None, "PyQt6 missing")
class TestKeywordSearchDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

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
        from PyQt6.QtCore import Qt

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


@unittest.skipIf(__import__("importlib").util.find_spec("PyQt6") is None, "PyQt6 missing")
class TestKeywordWorkerSessionCleanup(unittest.TestCase):
    """ISSUE-001: failed __enter__ must still release acquired resources."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

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


@unittest.skipIf(__import__("importlib").util.find_spec("PyQt6") is None, "PyQt6 missing")
class TestKeywordWorkerResilience(unittest.TestCase):
    """Retry-once, cooldown, and generation guards (audit §5)."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

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
            self.assertEqual(state["calls"], 2)
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
            self.assertEqual(state["calls"], 2)
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
            self.assertIn("429", failed[1][0])
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


if __name__ == "__main__":
    unittest.main()
