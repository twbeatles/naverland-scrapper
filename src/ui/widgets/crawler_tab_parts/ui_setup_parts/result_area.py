from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


FavoriteKey = tuple[str, str, str]
FavoriteKeyProvider = Callable[[], set[FavoriteKey]]
CompactRowKey = tuple[str, str, str, str, str, float, str]
RowPayload = dict[str, Any]
ResultRow = dict[str, Any]


class CrawlerTabResultAreaSetupMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    #: 메뉴에 보이는 쉬운 이름 → combo_sort 내부 기준 문자열
    SORT_MENU_LABELS = (
        ("가격 낮은 순", "가격 ↑"),
        ("가격 높은 순", "가격 ↓"),
        ("면적 좁은 순", "면적 ↑"),
        ("면적 넓은 순", "면적 ↓"),
        ("단지 이름순", "단지명 ↑"),
        ("단지 이름 역순", "단지명 ↓"),
        ("거래 종류순", "거래유형 ↑"),
        ("거래 종류 역순", "거래유형 ↓"),
    )

    def _setup_result_area(self: Any, layout):
        # ── 결과 툴바 ──
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("resultToolbar")
        search_sort = QHBoxLayout(toolbar_widget)
        search_sort.setContentsMargins(8, 8, 8, 8)
        search_sort.setSpacing(8)

        self.result_search = SearchBar("결과에서 찾기 (단지 이름, 가격, 층 등)")
        self.result_search.search_changed.connect(self._on_search_text_changed)
        search_sort.addWidget(self.result_search, 3)

        self.view_mode = settings.get("view_mode", "table")
        # Label shows the mode you can switch *to*.
        self.btn_view_mode = QPushButton("카드로 보기" if self.view_mode != "card" else "표로 보기")
        self.btn_view_mode.setObjectName("secondaryBtn")
        self.btn_view_mode.setToolTip("결과를 표 또는 카드 모양으로 바꿔 봅니다.")
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(self.view_mode == "card")
        self.btn_view_mode.clicked.connect(self._toggle_view_mode)
        search_sort.addWidget(self.btn_view_mode)

        # Secondary actions live in one menu to keep the toolbar slim.
        self.btn_result_more = QPushButton("정렬·필터")
        self.btn_result_more.setIcon(FIF.FILTER.icon())
        self.btn_result_more.setToolTip("정렬, 상세 필터, 같은 매물 묶기, 표에 보일 항목을 바꿉니다.")
        self.btn_result_more.setObjectName("secondaryBtn")
        search_sort.addWidget(self.btn_result_more)

        self.check_compact_duplicates = QCheckBox("묶기")
        self.check_compact_duplicates.setChecked(self._compact_duplicates)
        self.check_compact_duplicates.setToolTip("여러 중개소가 올린 같은 매물을 한 줄로 묶어 보여 줍니다.")
        self.check_compact_duplicates.toggled.connect(self._toggle_compact_duplicates)

        self.btn_advanced_filter = QPushButton("상세 필터")
        self.btn_advanced_filter.setToolTip("가격·면적·층·키워드 등 조건으로 결과를 좁혀 봅니다.")
        self.btn_advanced_filter.clicked.connect(self.open_advanced_filter_dialog)

        self.btn_clear_advanced_filter = QPushButton("필터 해제")
        self.btn_clear_advanced_filter.setToolTip("적용한 상세 필터를 모두 풉니다.")
        self.btn_clear_advanced_filter.clicked.connect(self.clear_advanced_filters)
        self.btn_clear_advanced_filter.setEnabled(False)

        self.lbl_advanced_filter = QLabel("")
        self.lbl_advanced_filter.setObjectName("fieldLabel")

        self.combo_sort = QComboBox()
        self.combo_sort.addItems([criterion for _label, criterion in self.SORT_MENU_LABELS])
        self.combo_sort.setToolTip("결과 정렬 기준을 선택합니다.")
        self.combo_sort.currentTextChanged.connect(self._sort_results)

        from src.utils.ui_labels import BTN_EXTRA_COLUMNS

        self.btn_columns = QPushButton(BTN_EXTRA_COLUMNS)
        self.btn_columns.setToolTip("표에 더 보여 줄 항목을 고릅니다.")
        self.btn_columns.clicked.connect(self._open_extra_columns_menu)

        more_menu = QMenu(self.btn_result_more)
        sort_menu = more_menu.addMenu("정렬")
        if sort_menu is not None:
            for label, criterion in self.SORT_MENU_LABELS:
                act = sort_menu.addAction(label)
                if act is not None:
                    act.triggered.connect(
                        lambda _=False, t=criterion: self.combo_sort.setCurrentText(t)
                    )

        more_menu.addAction("상세 필터…", self.open_advanced_filter_dialog)
        self._clear_filter_menu_action = more_menu.addAction(
            "상세 필터 풀기", self.clear_advanced_filters
        )
        if self._clear_filter_menu_action is not None:
            self._clear_filter_menu_action.setEnabled(False)
        more_menu.addSeparator()
        compact_action = more_menu.addAction("같은 매물 묶어 보기")
        if compact_action is not None:
            compact_action.setCheckable(True)
            compact_action.setChecked(self.check_compact_duplicates.isChecked())
            compact_action.toggled.connect(self.check_compact_duplicates.setChecked)
            self.check_compact_duplicates.toggled.connect(compact_action.setChecked)
        more_menu.addAction("표에 보일 항목…", self._open_extra_columns_menu)
        # Kept as an attribute for the badge updater; no separate status row in the menu.
        self._result_more_filter_status_action = None
        self.btn_result_more.setMenu(more_menu)

        # Keep legacy widgets in layout but hidden (signal/slot compatibility).
        for w in (
            self.check_compact_duplicates,
            self.btn_advanced_filter,
            self.btn_clear_advanced_filter,
            self.combo_sort,
            self.btn_columns,
        ):
            w.setVisible(False)
            search_sort.addWidget(w)

        layout.addWidget(toolbar_widget)

        # 상세 필터가 켜져 있으면 결과 위에 한 줄로 알려 준다.
        self.filter_notice = QWidget()
        notice_layout = QHBoxLayout(self.filter_notice)
        notice_layout.setContentsMargins(4, 0, 4, 0)
        notice_layout.setSpacing(8)
        notice_layout.addWidget(self.lbl_advanced_filter)
        notice_layout.addStretch()
        self.btn_filter_notice_clear = QPushButton("필터 풀기")
        self.btn_filter_notice_clear.setObjectName("secondaryBtn")
        self.btn_filter_notice_clear.clicked.connect(self.clear_advanced_filters)
        notice_layout.addWidget(self.btn_filter_notice_clear)
        self.filter_notice.setVisible(False)
        layout.addWidget(self.filter_notice)

        # Result Tabs
        result_tabs = QTabWidget()
        self.result_tabs = result_tabs
        result_tab = QWidget()
        rl = QVBoxLayout(result_tab)
        rl.setContentsMargins(0, 4, 0, 0)

        # Table View
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(int(getattr(self, "RESULT_COLUMN_COUNT", 25)))
        self.result_table.setHorizontalHeaderLabels([
            "단지명", "거래", "가격", "면적", "평당가", "층/방향", "특징",
            "같은 매물", "신규", "가격 변동", "종류", "기존 전세금", "갭 금액", "갭 비율",
            "수집 시각", "링크", "URL", "가격(숫자)",
            "확인일", "동", "타입명", "동일주소", "정보제공", "중개소", "전화",
        ])
        self.result_table.setColumnHidden(self.COL_URL, True)
        self.result_table.setColumnHidden(self.COL_PRICE_SORT, True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.result_table.setToolTip("두 번 누르면 네이버 부동산 매물 페이지를 엽니다.")
        self.result_table.doubleClicked.connect(self._open_article_url)
        from src.ui.widgets.components import EmptyStateWidget, install_token_labels
        from src.utils.ui_labels import asset_label

        install_token_labels(self.result_table, self.COL_ASSET_TYPE, asset_label)
        if hasattr(self, "_apply_extra_column_visibility"):
            self._apply_extra_column_visibility()

        # Card View
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.result_table)

        self.card_view = CardViewWidget(is_dark=(self.current_theme == "dark"))
        if callable(self.article_open_handler):
            self.card_view.article_clicked.connect(self.article_open_handler)
        else:
            self.card_view.article_clicked.connect(
                lambda d: webbrowser.open(get_article_url(d.get("단지ID"), d.get("매물ID"), d.get("자산유형", "APT")))
            )
        self.view_stack.addWidget(self.card_view)

        if self.view_mode == "card":
             self.view_stack.setCurrentWidget(self.card_view)

        self.result_empty = EmptyStateWidget(icon="SEARCH")
        rl.addWidget(self.result_empty, 1)
        rl.addWidget(self.view_stack, 1)
        result_tabs.addTab(result_tab, "매물 결과")

        # Log Tab
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        ll.setContentsMargins(0, 4, 0, 0)
        # log_browser = 전체 기록(진단 줄 포함), log_summary = 사용자용 요약.
        # 평소에는 요약만 보여 주고, 「자세히 보기」를 켜면 전체 기록으로 바뀐다.
        self.log_browser = QTextBrowser()
        self.log_browser.setMinimumHeight(150)
        self.log_summary = QTextBrowser()
        self.log_summary.setMinimumHeight(150)
        self.log_summary.setPlaceholderText("수집을 시작하면 진행 과정이 여기에 기록됩니다.")
        self.log_stack = QStackedWidget()
        self.log_stack.addWidget(self.log_summary)
        self.log_stack.addWidget(self.log_browser)
        ll.addWidget(self.log_stack, 1)
        self.check_log_details = QCheckBox("자세히 보기 (문제 진단용 기록 포함)")
        self.check_log_details.setToolTip(
            "수집이 잘 안 될 때 원인을 찾기 위한 세부 기록까지 보여 줍니다. 문의할 때 이 내용을 함께 보내 주세요."
        )
        self.check_log_details.toggled.connect(
            lambda on: self.log_stack.setCurrentWidget(self.log_browser if on else self.log_summary)
        )
        ll.addWidget(self.check_log_details)
        result_tabs.addTab(log_tab, "진행 기록")

        layout.addWidget(result_tabs, 1)

        # Progress
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)

        result_model = self.result_table.model()
        if result_model is not None:
            result_model.rowsInserted.connect(lambda *_: self._update_result_empty_state())
            result_model.rowsRemoved.connect(lambda *_: self._update_result_empty_state())
            result_model.modelReset.connect(lambda *_: self._update_result_empty_state())
        self._update_result_empty_state()

    #: (제목, 설명) — 서브클래스(지도 탐색)가 첫 안내 문구를 바꿀 수 있다.
    RESULT_EMPTY_INITIAL = (
        "아직 수집한 매물이 없습니다",
        "왼쪽에서 단지를 추가한 뒤 「수집 시작」을 눌러 주세요.",
    )

    def _update_result_empty_state(self: Any):
        """결과가 비었을 때 빈 표 대신 상황에 맞는 안내를 보여 준다."""
        empty = getattr(self, "result_empty", None)
        stack = getattr(self, "view_stack", None)
        if empty is None or stack is None:
            return
        has_rows = int(self.result_table.rowCount() or 0) > 0
        if not has_rows:
            thread = getattr(self, "crawler_thread", None)
            try:
                running = bool(thread is not None and thread.isRunning())
            except Exception:
                running = False
            if running:
                empty.set_text("매물을 수집하고 있습니다", "찾는 대로 여기에 바로 표시됩니다.")
            elif getattr(self, "collected_data", None):
                empty.set_text(
                    "조건에 맞는 매물이 없습니다",
                    "「정렬·필터」에서 상세 필터를 풀면 전체 결과를 볼 수 있습니다.",
                )
            elif getattr(self, "_crawl_finished_once", False):
                empty.set_text(
                    "수집된 매물이 없습니다",
                    "거래 종류나 조건을 넓히거나 다른 단지로 다시 시도해 보세요.",
                )
            else:
                empty.set_text(*self.RESULT_EMPTY_INITIAL)
        empty.setVisible(not has_rows)
        stack.setVisible(has_rows)
