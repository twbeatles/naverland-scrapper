import queue
import threading

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QListWidgetItem,
    QLineEdit, QLabel, QTabWidget, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer

from src.utils.ui_labels import asset_label
from src.core.services.keyword_search import (
    KeywordBrowserSession,
    KeywordSearchError,
    fetch_search_page,
    fetch_search_page_with_fallback,
    fetch_suggestions,
    is_rate_limit_error,
)

_SUGGEST_DEBOUNCE_MS = 400


class _KeywordWorker(QObject):
    """Background fetch logic driven by a plain (non-Qt) pump thread.

    Playwright's sync API must not share a thread with a Qt event loop:
    consecutive in-page fetches from a QThread slot crash the process
    with an access violation. A daemon threading.Thread owns the browser
    session outright; results cross back through queued signals.
    """

    suggestions_ready = Signal(list, int)
    search_ready = Signal(dict, int, bool)
    failed = Signal(str, int, str)

    def __init__(self, session_factory=None, rate_limit_cooldown_sec=30.0,
                 retry_delay_sec=1.0):
        super().__init__()
        self._session_factory = session_factory or KeywordBrowserSession
        self._session = None
        self._cancelled = False
        self._rate_limit_cooldown_sec = max(0.0, float(rate_limit_cooldown_sec))
        self._retry_delay_sec = max(0.0, float(retry_delay_sec))
        self._cooldown_until = 0.0

    def cancel(self):
        self._cancelled = True

    def _cooldown_message(self):
        import time as _time

        remaining = self._cooldown_until - _time.monotonic()
        if remaining <= 0:
            return ""
        return f"요청이 많아 잠시 쉬는 중입니다. {int(remaining) + 1}초 뒤에 다시 시도해 주세요."

    def _note_rate_limit(self):
        import time as _time

        if self._rate_limit_cooldown_sec > 0:
            self._cooldown_until = _time.monotonic() + self._rate_limit_cooldown_sec

    def _sleep_retry_delay(self):
        import time as _time

        remaining = self._retry_delay_sec
        while remaining > 0:
            if self._cancelled:
                return False
            step = min(0.1, remaining)
            _time.sleep(step)
            remaining -= step
        return not self._cancelled

    def _ensure_session(self):
        if self._session is None:
            session = self._session_factory()
            try:
                session.__enter__()
            except Exception:
                # ISSUE-001: a failed __enter__ must still release resources
                # the factory already acquired (browser/driver processes).
                try:
                    session.__exit__(None, None, None)
                except Exception:
                    pass
                raise
            if self._cancelled:
                try:
                    session.__exit__(None, None, None)
                finally:
                    self._session = None
                raise RuntimeError("cancelled")
            self._session = session
        return self._session

    def _run_fetch_once(self, kind, keyword, page=1):
        if kind == "suggest":
            return fetch_suggestions(keyword, self._ensure_session().fetch)
        return fetch_search_page(keyword, self._ensure_session().fetch, page=int(page or 1))

    def _fetch_with_retry(self, kind, keyword, page=1):
        """Single retry on transport errors; rate limits arm the cooldown."""
        try:
            return self._run_fetch_once(kind, keyword, page=page)
        except KeywordSearchError as exc:
            if self._cancelled:
                raise
            if is_rate_limit_error(exc):
                self._note_rate_limit()
            if not self._sleep_retry_delay():
                raise
            return self._run_fetch_once(kind, keyword, page=page)

    @Slot(str, int)
    def suggest(self, keyword, generation):
        if self._cooldown_message():
            return
        try:
            names = self._fetch_with_retry("suggest", keyword)
            if not self._cancelled:
                self.suggestions_ready.emit(list(names), int(generation))
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc)[:200], int(generation), "suggest")

    @Slot(str, int, int, bool)
    def search(self, keyword, page, generation, append):
        cooled = self._cooldown_message()
        if cooled:
            self.failed.emit(cooled, int(generation), "search")
            return
        try:
            if bool(append) or int(page or 1) > 1:
                result = self._fetch_with_retry("search", keyword, page=page)
            else:
                result = self._fetch_fresh_search(keyword)
            if not self._cancelled:
                payload = result if isinstance(result, dict) else {}
                self.search_ready.emit(dict(payload), int(generation), bool(append))
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc)[:200], int(generation), "search")

    def _fetch_fresh_search(self, keyword):
        """Fresh (page-1) search: address variants first, one retry."""
        try:
            return fetch_search_page_with_fallback(
                keyword, self._ensure_session().fetch, page=1)
        except KeywordSearchError as exc:
            if self._cancelled:
                raise
            if is_rate_limit_error(exc):
                self._note_rate_limit()
            if not self._sleep_retry_delay():
                raise
            return fetch_search_page_with_fallback(
                keyword, self._ensure_session().fetch, page=1)

    def resolve(self, entries, generation):
        """Resolve pasted complex IDs to rows (runs on the pump thread)."""
        try:
            from src.core.parser import NaverURLParser
        except Exception as exc:
            if not self._cancelled:
                self.failed.emit(str(exc)[:200], int(generation), "search")
            return
        rows = []
        for entry in entries or []:
            if self._cancelled:
                return
            data = dict(entry or {})
            cid = str(data.get("complex_id", "") or "").strip()
            asset = str(data.get("asset_type", "APT") or "APT").strip().upper()
            if asset not in {"APT", "VL"}:
                asset = "APT"
            if not cid:
                continue
            try:
                name = NaverURLParser.fetch_complex_name(cid, asset_type=asset)
            except Exception:
                name = ""
            name = str(name or "").strip() or f"단지_{cid}"
            rows.append({
                "complex_id": cid,
                "name": name,
                "address": "",
                "asset_type": asset,
                "latitude": None,
                "longitude": None,
                "deep_link": "",
            })
        if not self._cancelled:
            self.search_ready.emit(
                {"complexes": rows, "regions": [],
                 "is_more_data": False, "effective_query": ""},
                int(generation), False)

    @Slot()
    def close_session(self):
        session, self._session = self._session, None
        if session is not None:
            try:
                session.__exit__(None, None, None)
            except Exception:
                pass


class KeywordSearchDialog(QDialog):
    """키워드 단지 검색 다이얼로그 (v15.2).

    네이버 ``/api/autocomplete`` 제안 + ``/api/search`` 해석을 사용한다.
    단지 후보는 체크 후 목록에 추가하고, 지역 후보는 지도 탭으로 보낸다.
    """

    complexes_added = Signal(list)  # [(name, complex_id, asset_type), ...]
    region_chosen = Signal(dict)  # {"cortar_no","name","latitude","longitude",...}

    def __init__(self, parent=None, session_factory=None, mode="complex"):
        super().__init__(parent)
        # mode="region": 지도 탐색 위치를 고르는 용도 (지역 목록만 보여 준다).
        self._mode = "region" if str(mode or "").lower() == "region" else "complex"
        self._session_factory = session_factory
        self._pump_thread: threading.Thread | None = None
        self._task_queue: queue.Queue | None = None
        self._worker: _KeywordWorker | None = None
        self._generation = 0
        self._search_generation = 0
        self._completed_search_generation = -1
        self._keyword = ""
        self._search_query = ""
        self._next_page = 1
        self._has_more = False
        self._busy = False
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("지역 찾기" if self._mode == "region" else "단지 찾기")
        self.setMinimumSize(560, 600)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        hint = QLabel(
            "동·구 이름이나 실제 주소로 검색한 뒤 목록에서 탐색할 지역을 골라 주세요."
            if self._mode == "region"
            else "단지 이름·지역 이름·실제 주소로 검색한 뒤, 수집할 단지를 체크해 추가하세요. 네이버 지도 링크도 붙여넣을 수 있습니다."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText(
            "예: 반포동, 분당구, 서울특별시 서초구 반포동"
            if self._mode == "region"
            else "예: 래미안 퍼스티지, 반포자이, 반포동, 지도 링크 붙여넣기"
        )
        self.input_keyword.setToolTip("두 글자 이상 입력하면 추천 검색어가 나타납니다.")
        self.input_keyword.returnPressed.connect(self._run_search)
        self.input_keyword.textChanged.connect(self._on_keyword_text_changed)
        search_row.addWidget(self.input_keyword, 1)
        self.btn_search = QPushButton("검색")
        self.btn_search.setObjectName("primaryBtn")
        self.btn_search.setToolTip("네이버 부동산에서 검색합니다. (Enter)")
        self.btn_search.clicked.connect(self._run_search)
        search_row.addWidget(self.btn_search)
        layout.addLayout(search_row)

        self.suggest_list = QListWidget()
        self.suggest_list.setMaximumHeight(120)
        self.suggest_list.setAlternatingRowColors(True)
        self.suggest_list.setToolTip("추천 검색어를 누르면 바로 검색합니다.")
        self.suggest_list.itemClicked.connect(self._on_suggest_clicked)
        self.suggest_list.hide()
        layout.addWidget(self.suggest_list)

        self.tabs = QTabWidget()
        self.complex_list = QListWidget()
        self.complex_list.setAlternatingRowColors(True)
        self.complex_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        complex_page = QWidget()
        complex_layout = QVBoxLayout(complex_page)
        complex_layout.setContentsMargins(0, 4, 0, 0)
        complex_layout.addWidget(self.complex_list)
        complex_btns = QHBoxLayout()
        self.btn_select_all = QPushButton("전체 선택")
        self.btn_select_all.setObjectName("secondaryBtn")
        self.btn_select_all.clicked.connect(lambda: self._set_all_checked(True))
        self.btn_deselect_all = QPushButton("전체 해제")
        self.btn_deselect_all.setObjectName("secondaryBtn")
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_checked(False))
        complex_btns.addWidget(self.btn_select_all)
        complex_btns.addWidget(self.btn_deselect_all)
        complex_btns.addStretch()
        complex_layout.addLayout(complex_btns)
        self.tabs.addTab(complex_page, "단지")

        self.region_list = QListWidget()
        self.region_list.setAlternatingRowColors(True)
        region_page = QWidget()
        region_layout = QVBoxLayout(region_page)
        region_layout.setContentsMargins(0, 4, 0, 0)
        region_layout.addWidget(self.region_list)
        region_btns = QHBoxLayout()
        self.btn_region_map = QPushButton("이 지역 주변을 「지도로 찾기」로 탐색")
        self.btn_region_map.setObjectName("secondaryBtn")
        self.btn_region_map.setToolTip("고른 지역을 「지도로 찾기」 화면의 탐색 위치로 정합니다.")
        self.btn_region_map.clicked.connect(self._emit_region)
        region_btns.addWidget(self.btn_region_map)
        region_btns.addStretch()
        region_layout.addLayout(region_btns)
        self.tabs.addTab(region_page, "지역")
        layout.addWidget(self.tabs, 1)
        self.region_list.itemDoubleClicked.connect(lambda *_: self._emit_region())

        self.status_label = QLabel("검색어를 입력하세요.")
        self.status_label.setObjectName("hintLabel")
        layout.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.btn_more = QPushButton("더 보기")
        self.btn_more.setObjectName("secondaryBtn")
        self.btn_more.setToolTip("검색 결과를 더 불러옵니다.")
        self.btn_more.clicked.connect(self._load_more)
        self.btn_more.setEnabled(False)
        bottom.addWidget(self.btn_more)
        bottom.addStretch()
        self.btn_close = QPushButton("닫기")
        self.btn_close.setObjectName("secondaryBtn")
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        self.btn_add = QPushButton("체크한 단지 추가")
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.setToolTip("체크한 단지를 수집 목록에 추가합니다.")
        self.btn_add.clicked.connect(self._emit_complexes)
        bottom.addWidget(self.btn_add)
        layout.addLayout(bottom)

        if self._mode == "region":
            self.tabs.setTabVisible(0, False)
            self.tabs.setCurrentIndex(1)
            self.btn_add.hide()
            self.btn_region_map.setText("이 지역으로 정하기")
            self.btn_region_map.setObjectName("primaryBtn")
            region_style = self.btn_region_map.style()
            if region_style is not None:
                region_style.unpolish(self.btn_region_map)
                region_style.polish(self.btn_region_map)
            self.btn_region_map.setToolTip("고른 지역을 탐색 위치로 정합니다. (두 번 눌러도 됩니다)")

        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(_SUGGEST_DEBOUNCE_MS)
        self._suggest_timer.timeout.connect(self._request_suggestions)

    # -- worker plumbing -------------------------------------------------
    def _ensure_worker(self):
        if self._pump_thread is not None:
            return
        self._task_queue = queue.Queue()
        self._worker = _KeywordWorker(session_factory=self._session_factory)
        self._worker.suggestions_ready.connect(self._on_suggestions_ready)
        self._worker.search_ready.connect(self._on_search_ready)
        self._worker.failed.connect(self._on_worker_failed)
        self._pump_thread = threading.Thread(target=self._pump_loop, daemon=True)
        self._pump_thread.start()

    def _enqueue(self, task):
        self._ensure_worker()
        if self._task_queue is not None:
            self._task_queue.put(task)

    def _pump_loop(self):
        """Run queued fetches on a plain thread (never a QThread)."""
        worker = self._worker
        task_queue = self._task_queue
        if worker is None or task_queue is None:
            return
        try:
            while True:
                try:
                    task = task_queue.get()
                except Exception:
                    return
                if task is None:
                    return
                kind = task[0]
                try:
                    if kind == "suggest":
                        worker.suggest(task[1], task[2])
                    elif kind == "search":
                        worker.search(task[1], task[2], task[3], task[4])
                    elif kind == "resolve":
                        worker.resolve(task[1], task[2])
                except Exception:
                    pass
                finally:
                    try:
                        task_queue.task_done()
                    except Exception:
                        pass
        finally:
            try:
                worker.close_session()
            except Exception:
                pass

    def _shutdown_worker(self):
        try:
            self._suggest_timer.stop()
        except Exception:
            pass
        if self._worker is not None:
            try:
                self._worker.cancel()
            except Exception:
                pass
        thread, self._pump_thread = self._pump_thread, None
        task_queue, self._task_queue = self._task_queue, None
        worker, self._worker = self._worker, None
        if task_queue is not None:
            try:
                task_queue.put(None)
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            try:
                thread.join(timeout=5.0)
            except Exception:
                pass
        # A still-blocked pump thread is a daemon: it can never abort the
        # process. It sees the cancel flag after its fetch returns, closes
        # its own session, and exits on its own.

    def closeEvent(self, a0):
        self._shutdown_worker()
        super().closeEvent(a0)

    def reject(self):
        self._shutdown_worker()
        super().reject()

    def accept(self):
        self._shutdown_worker()
        super().accept()

    # -- suggestions ------------------------------------------------------
    def _on_keyword_text_changed(self):
        self._suggest_timer.start()

    def _request_suggestions(self):
        keyword = self.input_keyword.text().strip()
        if len(keyword) < 2:
            self.suggest_list.hide()
            return
        self._ensure_worker()
        self._generation += 1
        self._enqueue(("suggest", keyword, self._generation))

    @Slot(list, int)
    def _on_suggestions_ready(self, names, generation):
        if generation != self._generation:
            return
        self.suggest_list.clear()
        for name in names[:10]:
            self.suggest_list.addItem(QListWidgetItem(str(name)))
        self.suggest_list.setVisible(bool(names))

    def _on_suggest_clicked(self, item):
        self.input_keyword.setText(item.text())
        self.suggest_list.hide()
        self._run_search()
        # setText() restarts the debounce timer; the clicked suggestion is
        # already being searched, so cancel that redundant suggest request.
        self._suggest_timer.stop()

    # -- search ------------------------------------------------------------
    def _run_search(self):
        keyword = self.input_keyword.text().strip()
        if not keyword:
            QMessageBox.warning(self, "검색어를 입력해 주세요", "찾을 이름을 입력해 주세요.")
            return
        if self._busy:
            return
        self._search_generation += 1
        self._completed_search_generation = -1
        self._keyword = keyword
        self._search_query = keyword
        self._next_page = 1
        self._has_more = False
        self.complex_list.clear()
        self.region_list.clear()
        if self._handle_map_link(keyword):
            return
        self._set_busy(True, f"'{keyword}' 검색 중...")
        self._enqueue(("search", keyword, 1, self._search_generation, False))

    def _handle_map_link(self, keyword):
        """Pasted Naver map links: IDs resolve, ms= centers, else guidance."""
        text = str(keyword or "")
        lowered = text.lower()
        if "land.naver.com" not in lowered and "fin.land" not in lowered:
            return False
        try:
            from src.core.parser import NaverURLParser
        except Exception:
            return False
        found = NaverURLParser.extract_from_text(text)
        entries = [e for e in found if str((e or {}).get("complex_id", "") or "").strip()]
        if entries:
            self._set_busy(True, f"링크에서 단지 {len(entries)}곳을 확인 중...")
            self._enqueue(("resolve", entries, self._search_generation))
            return True
        center = NaverURLParser.extract_map_center(text)
        if center is not None:
            lat, lon, _zoom = center
            self.complex_list.clear()
            self.region_list.clear()
            self._has_more = False
            self._next_page = 1
            self._search_query = ""
            name = f"지도 링크 위치 ({lat:.4f}, {lon:.4f})"
            row = QListWidgetItem(name)
            row.setData(
                Qt.ItemDataRole.UserRole,
                {"cortar_no": "", "name": name,
                 "latitude": lat, "longitude": lon, "deep_link": ""},
            )
            row.setToolTip("이 위치를 탐색 위치로 쓸 수 있습니다.")
            self.region_list.addItem(row)
            self.tabs.setTabText(0, "단지 0")
            self.tabs.setTabText(1, "지역 1")
            if self._mode != "region":
                self.tabs.setCurrentIndex(1)
            self._set_busy(False)
            self.status_label.setText(f"지도 링크의 위치를 찾았습니다: {name}")
            return True
        articles = [e for e in found if str((e or {}).get("article_id", "") or "").strip()]
        if articles:
            self.status_label.setText(
                "매물 링크는 「불러오기 → 주소 붙여넣기」에서 열어 주세요. "
                "여기서는 단지·지도 링크를 붙여넣을 수 있습니다."
            )
        else:
            self.status_label.setText(
                "지도 화면 링크에는 단지 정보가 없어요. "
                "단지가 열린 상태의 링크(단지 번호 포함)를 붙여넣어 주세요."
            )
        return True

    def _load_more(self):
        if self._busy or not self._has_more or not self._keyword:
            return
        self._set_busy(True, f"'{self._keyword}' {self._next_page}페이지 불러오는 중...")
        query = str(self._search_query or self._keyword or "")
        self._enqueue(("search", query, self._next_page, self._search_generation, True))

    def _set_busy(self, busy: bool, status: str = ""):
        self._busy = busy
        self.btn_search.setEnabled(not busy)
        self.btn_more.setEnabled((not busy) and self._has_more)
        if status:
            self.status_label.setText(status)

    @Slot(dict, int, bool)
    def _on_search_ready(self, result, generation, append):
        if generation != self._search_generation:
            return
        if not append:
            self.complex_list.clear()
            self.region_list.clear()
        if not append:
            self._search_query = str(result.get("effective_query", "") or self._keyword or "")
        for item in result.get("complexes", []) or []:
            cid = str(item.get("complex_id", "") or "")
            name = str(item.get("name", "") or f"단지_{cid}")
            address = str(item.get("address", "") or "")
            asset = str(item.get("asset_type", "APT") or "APT")
            text = f"{name}  ·  {asset_label(asset)}" + (f"\n{address}" if address else "")
            row = QListWidgetItem(text)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Unchecked)
            row.setData(Qt.ItemDataRole.UserRole, {"name": name, "cid": cid, "asset": asset})
            self.complex_list.addItem(row)
        for item in result.get("regions", []) or []:
            name = str(item.get("name", "") or "")
            row = QListWidgetItem(name or "(이름 없음)")
            row.setData(Qt.ItemDataRole.UserRole, dict(item))
            lat, lon = item.get("latitude"), item.get("longitude")
            if lat is not None and lon is not None:
                row.setToolTip("이 지역을 탐색 위치로 쓸 수 있습니다.")
            else:
                row.setToolTip("위치 정보가 없는 지역입니다.")
            self.region_list.addItem(row)
        self._completed_search_generation = generation
        self._has_more = bool(result.get("is_more_data"))
        if self._has_more:
            self._next_page += 1
        n_complex = self.complex_list.count()
        n_region = self.region_list.count()
        self.tabs.setTabText(0, f"단지 {n_complex}")
        self.tabs.setTabText(1, f"지역 {n_region}")
        if self._mode == "region" and n_complex > 0:
            self.tabs.setTabVisible(0, True)
        if self._mode != "region" and n_complex == 0 and n_region > 0:
            self.tabs.setCurrentIndex(1)
        self._set_busy(False)
        if n_complex == 0 and n_region == 0:
            self.status_label.setText(f"'{self._keyword}' 결과가 없습니다. 다른 이름으로 검색해 보세요.")
        else:
            self.status_label.setText(
                (
                    f"'{self._keyword}' 지역 {n_region}곳"
                    if self._mode == "region"
                    else f"'{self._keyword}' 단지 {n_complex}곳 · 지역 {n_region}곳"
                )
                + (" · 「더 보기」로 더 불러올 수 있습니다" if self._has_more else "")
            )

    @Slot(str, int, str)
    def _on_worker_failed(self, message, generation, kind):
        if kind == "search":
            if generation != self._search_generation:
                return
            self._set_busy(False)
            self._completed_search_generation = generation
            self.status_label.setText(f"검색하지 못했습니다: {message or '잠시 후 다시 시도해 주세요.'}")
            return
        if generation != self._generation or self._busy:
            return
        if self._completed_search_generation == self._search_generation:
            return
        self.status_label.setText(f"추천 검색어를 불러오지 못했습니다: {message or '잠시 후 다시 시도해 주세요.'}")

    def _set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.complex_list.count()):
            item = self.complex_list.item(i)
            if item is not None:
                item.setCheckState(state)

    def checked_complexes(self):
        selected = []
        for i in range(self.complex_list.count()):
            item = self.complex_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole) or {}
                selected.append(
                    (str(data.get("name", "")), str(data.get("cid", "")), str(data.get("asset", "APT")))
                )
        return [row for row in selected if row[1]]

    def _emit_complexes(self):
        selected = self.checked_complexes()
        if not selected:
            QMessageBox.information(self, "단지를 체크해 주세요", "목록에서 추가할 단지를 체크해 주세요.")
            return
        self.complexes_added.emit(selected)
        self.accept()

    def _emit_region(self):
        item = self.region_list.currentItem()
        if item is None:
            QMessageBox.information(self, "지역을 골라 주세요", "「지역」 목록에서 지역을 하나 골라 주세요.")
            return
        self.region_chosen.emit(dict(item.data(Qt.ItemDataRole.UserRole) or {}))
        self.accept()


class RecentSearchDialog(QDialog):
    """최근 검색 기록 다이얼로그"""
    def __init__(self, parent=None, history_manager=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_search = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("최근 수집 조건")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)

        btn_layout = QHBoxLayout()
        btn_load = QPushButton("불러오기")
        btn_load.setObjectName("primaryBtn")
        btn_load.clicked.connect(self._load)
        btn_clear = QPushButton("기록 지우기")
        btn_clear.setObjectName("secondaryBtn")
        btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._refresh()

    def _refresh(self):
        self.list.clear()
        if self.history_manager:
            for h in self.history_manager.get_recent():
                complexes = h.get('complexes', [])
                types = h.get('trade_types', [])
                timestamp = h.get('timestamp', '')
                text = f"{timestamp}  ·  단지 {len(complexes)}곳  ·  {', '.join(types)}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, h)
                self.list.addItem(item)

    def _load(self):
        if item := self.list.currentItem():
            self.selected_search = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _clear(self):
        if self.history_manager:
            self.history_manager.clear()
            self._refresh()
