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

    def _setup_result_area(self: Any, layout):
        # ── 결과 툴바 패널 ──
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("resultToolbar")
        search_sort = QHBoxLayout(toolbar_widget)
        search_sort.setContentsMargins(8, 6, 8, 6)
        search_sort.setSpacing(6)

        self.check_compact_duplicates = QCheckBox("묶기")
        self.check_compact_duplicates.setChecked(self._compact_duplicates)
        self.check_compact_duplicates.setToolTip("동일 매물의 여러 호가를 하나로 묶어 표시합니다.")
        self.check_compact_duplicates.toggled.connect(self._toggle_compact_duplicates)
        search_sort.addWidget(self.check_compact_duplicates)

        self.result_search = SearchBar("결과 검색...")
        self.result_search.search_changed.connect(self._on_search_text_changed)
        search_sort.addWidget(self.result_search, 3)

        self.btn_advanced_filter = QPushButton("⚙ 고급필터")
        self.btn_advanced_filter.setToolTip("층수, 방 수, 주차 등 세부 조건으로 결과를 필터링합니다.")
        self.btn_advanced_filter.clicked.connect(self.open_advanced_filter_dialog)
        search_sort.addWidget(self.btn_advanced_filter)

        self.btn_clear_advanced_filter = QPushButton("× 해제")
        self.btn_clear_advanced_filter.setToolTip("적용된 고급 필터를 모두 해제합니다.")
        self.btn_clear_advanced_filter.clicked.connect(self.clear_advanced_filters)
        self.btn_clear_advanced_filter.setEnabled(False)
        search_sort.addWidget(self.btn_clear_advanced_filter)

        self.lbl_advanced_filter = QLabel("OFF")
        self.lbl_advanced_filter.setObjectName("filterBadgeOff")
        search_sort.addWidget(self.lbl_advanced_filter)
        
        lbl_sort = QLabel("정렬")
        lbl_sort.setStyleSheet("font-size: 11px; color: #888;")
        search_sort.addWidget(lbl_sort)
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(
            ["가격 ↑", "가격 ↓", "면적 ↑", "면적 ↓", "단지명 ↑", "단지명 ↓", "거래유형 ↑", "거래유형 ↓"]
        )
        self.combo_sort.setToolTip("결과 정렬 기준을 선택합니다.")
        self.combo_sort.currentTextChanged.connect(self._sort_results)
        search_sort.addWidget(self.combo_sort, 1)
        
        self.view_mode = settings.get("view_mode", "table")
        self.btn_view_mode = QPushButton("🃏" if self.view_mode != "card" else "📄")
        self.btn_view_mode.setToolTip("카드 뷰 / 테이블 뷰 전환")
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(self.view_mode == "card")
        self.btn_view_mode.clicked.connect(self._toggle_view_mode)
        search_sort.addWidget(self.btn_view_mode)
        layout.addWidget(toolbar_widget)
        
        # Result Tabs
        result_tabs = QTabWidget()
        result_tab = QWidget()
        rl = QVBoxLayout(result_tab)
        rl.setContentsMargins(0, 5, 0, 0)
        
        # Table View
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(18)
        self.result_table.setHorizontalHeaderLabels([
            "단지명", "거래", "가격", "면적", "평당가", "층/방향", "특징",
            "묶음", "🆕", "📊 변동", "자산", "기전세금", "갭금액", "갭비율",
            "시각", "링크", "URL", "가격(숫자)"
        ])
        self.result_table.setColumnHidden(self.COL_URL, True)
        self.result_table.setColumnHidden(self.COL_PRICE_SORT, True)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.doubleClicked.connect(self._open_article_url)
        
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
        
        rl.addWidget(self.view_stack)
        result_tabs.addTab(result_tab, "📊 결과")
        
        # Log Tab
        log_tab = QWidget()
        ll = QVBoxLayout(log_tab)
        ll.setContentsMargins(0, 5, 0, 0)
        self.log_browser = QTextBrowser()
        self.log_browser.setMinimumHeight(150)
        ll.addWidget(self.log_browser)
        result_tabs.addTab(log_tab, "📝 로그")
        
        layout.addWidget(result_tabs)
        
        # Progress
        self.progress_widget = ProgressWidget()
        layout.addWidget(self.progress_widget)
