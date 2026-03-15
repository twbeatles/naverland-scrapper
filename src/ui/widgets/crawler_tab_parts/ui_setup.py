from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabUISetupMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def __init__(self: Any, db, history_manager=None, theme="dark", parent=None, maintenance_guard=None):
        base_init: Any = super().__init__
        base_init(parent)
        self.db = db
        self.history_manager = history_manager
        self.current_theme = theme
        self._maintenance_guard = maintenance_guard
        self.crawler_thread = None
        self.crawl_cache = None
        self.collected_data = []
        self.grouped_rows = {}
        self._pending_search_text = ""
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        self._advanced_filters = None
        self._append_chunk_size = 200
        self._compact_duplicates = bool(settings.get("compact_duplicate_listings", True))
        self._compact_items_by_key = {}
        self._compact_rows_data = []
        self.favorite_keys_provider = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self._splitter_save_timer = QTimer(self)
        self._splitter_save_timer.setSingleShot(True)
        self._splitter_save_timer.setInterval(250)
        self._splitter_save_timer.timeout.connect(self._save_splitter_state)
        
        # UI Setup
        self._init_ui()
        self._load_state()

    def _init_ui(self: Any):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Controls)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(400)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_content = QWidget()
        left = QVBoxLayout(scroll_content)
        left.setContentsMargins(6, 6, 6, 6)
        left.setSpacing(6)

        self.controls_splitter = QSplitter(Qt.Orientation.Vertical)
        self.controls_splitter.setChildrenCollapsible(False)
        self.controls_splitter.setHandleWidth(6)

        def _section(setup_fn):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
            setup_fn(section_layout)
            section_layout.addStretch(1)
            return section

        self.controls_splitter.addWidget(_section(self._setup_options_group))
        self.controls_splitter.addWidget(_section(self._setup_filter_group))
        self.controls_splitter.addWidget(_section(self._setup_complex_list_group))
        self.controls_splitter.addWidget(_section(self._setup_speed_group))
        self.controls_splitter.addWidget(_section(self._setup_action_group))
        left.addWidget(self.controls_splitter, 1)

        scroll.setWidget(scroll_content)
        self.main_splitter.addWidget(scroll)
        
        # Right Panel (Results)
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setContentsMargins(6, 6, 6, 6)
        right.setSpacing(8)
        
        self.summary_card = SummaryCard(theme=self.current_theme)
        right.addWidget(self.summary_card)
        
        self._setup_result_area(right)
        
        self.main_splitter.addWidget(right_w)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([440, 880])
        self.main_splitter.splitterMoved.connect(lambda *_: self._queue_splitter_state_save())
        self.controls_splitter.splitterMoved.connect(lambda *_: self._queue_splitter_state_save())
        layout.addWidget(self.main_splitter)

    def _queue_splitter_state_save(self: Any):
        self._splitter_save_timer.start()

    def _save_splitter_state(self: Any):
        if not hasattr(self, "main_splitter") or not hasattr(self, "controls_splitter"):
            return
        settings.update(
            {
                "crawler_main_splitter_sizes": list(self.main_splitter.sizes()),
                "crawler_controls_splitter_sizes": list(self.controls_splitter.sizes()),
            }
        )

    def _restore_splitter_state(self: Any):
        main_default = [520, 880]
        control_count = int(getattr(self.controls_splitter, "count", lambda: 0)())
        control_default = [170, 300, 340, 140, 120]
        if control_count != len(control_default):
            control_default = [1 for _ in range(max(control_count, 1))]

        main_sizes = settings.get("crawler_main_splitter_sizes", main_default) or main_default
        control_sizes = settings.get("crawler_controls_splitter_sizes", control_default) or control_default
        try:
            main_values = [max(1, int(v)) for v in main_sizes]
        except (TypeError, ValueError):
            main_values = main_default
        try:
            control_values = [max(1, int(v)) for v in control_sizes]
        except (TypeError, ValueError):
            control_values = control_default

        if len(main_values) != 2:
            main_values = main_default
        if len(control_values) != control_count:
            control_values = control_default

        self.main_splitter.setSizes(main_values)
        self.controls_splitter.setSizes(control_values)

    def _configure_filter_spinbox(self: Any, spinbox):
        """Compact spinbox policy for narrow control panel / HiDPI scaling."""
        spinbox.setMinimumWidth(80)
        spinbox.setMaximumWidth(180)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _setup_options_group(self: Any, layout):
        # 1. 거래유형
        tg = QGroupBox("거래 유형")
        tl = QHBoxLayout()
        tl.setSpacing(14)
        self.check_trade = QCheckBox("매매")
        self.check_trade.setChecked(True)
        self.check_trade.setToolTip("아파트 매매 매물을 수집합니다.")
        self.check_jeonse = QCheckBox("전세")
        self.check_jeonse.setChecked(True)
        self.check_jeonse.setToolTip("전세 매물을 수집합니다.")
        self.check_monthly = QCheckBox("월세")
        self.check_monthly.setToolTip("월세 매물을 수집합니다.")
        tl.addWidget(self.check_trade)
        tl.addWidget(self.check_jeonse)
        tl.addWidget(self.check_monthly)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)

    def _setup_filter_group(self: Any, layout):
        # 2. 면적 필터
        ag = QGroupBox("면적 필터")
        al = QVBoxLayout()
        al.setSpacing(6)
        self.check_area_filter = QCheckBox("면적 필터 사용")
        self.check_area_filter.setToolTip("체크하면 설정한 면적 범위의 매물만 수집합니다.")
        self.check_area_filter.stateChanged.connect(self._toggle_area_filter)
        al.addWidget(self.check_area_filter)
        
        area_input = QHBoxLayout()
        area_input.setContentsMargins(0, 0, 0, 0)
        area_input.setSpacing(4)
        self.spin_area_min = QSpinBox()
        self.spin_area_min.setRange(0, 300)
        self.spin_area_min.setEnabled(False)
        self.spin_area_min.setToolTip("최소 면적 (㎡)\n예: 59㎡ = 약 18평")
        self._configure_filter_spinbox(self.spin_area_min)
        self.spin_area_max = QSpinBox()
        self.spin_area_max.setRange(0, 300)
        self.spin_area_max.setValue(200)
        self.spin_area_max.setEnabled(False)
        self.spin_area_max.setToolTip("최대 면적 (㎡)\n예: 84㎡ = 약 25평")
        self._configure_filter_spinbox(self.spin_area_max)
        
        lbl_min = QLabel("최소")
        lbl_min.setStyleSheet("color: #888; font-size: 11px;")
        lbl_tilde = QLabel("~")
        lbl_tilde.setStyleSheet("color: #888;")
        lbl_max = QLabel("최대")
        lbl_max.setStyleSheet("color: #888; font-size: 11px;")
        lbl_unit = QLabel("㎡")
        lbl_unit.setStyleSheet("color: #888; font-size: 11px;")
        area_input.addWidget(lbl_min)
        area_input.addWidget(self.spin_area_min, 1)
        area_input.addWidget(lbl_tilde)
        area_input.addWidget(lbl_max)
        area_input.addWidget(self.spin_area_max, 1)
        area_input.addWidget(lbl_unit)
        al.addLayout(area_input)
        ag.setLayout(al)
        layout.addWidget(ag)
        
        # 3. 가격 필터
        pg = QGroupBox("가격 필터")
        pl = QVBoxLayout()
        pl.setSpacing(6)
        self.check_price_filter = QCheckBox("가격 필터 사용")
        self.check_price_filter.setToolTip("체크하면 설정한 가격 범위의 매물만 수집합니다.\n단위: 만원 (예: 50000 = 5억)")
        self.check_price_filter.stateChanged.connect(self._toggle_price_filter)
        pl.addWidget(self.check_price_filter)
        
        price_grid = QGridLayout()
        price_grid.setContentsMargins(0, 0, 0, 0)
        price_grid.setHorizontalSpacing(4)
        price_grid.setVerticalSpacing(6)
        price_grid.setColumnStretch(1, 1)
        price_grid.setColumnStretch(3, 1)

        def _price_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            return lbl

        # 매매
        price_grid.addWidget(_price_label("매매"), 0, 0)
        self.spin_trade_min = QSpinBox()
        self.spin_trade_min.setRange(0, 999999)
        self.spin_trade_min.setSingleStep(1000)
        self.spin_trade_min.setEnabled(False)
        self.spin_trade_min.setToolTip("매매 최소 가격 (만원)")
        self._configure_filter_spinbox(self.spin_trade_min)
        price_grid.addWidget(self.spin_trade_min, 0, 1)
        price_grid.addWidget(_price_label("~"), 0, 2)
        self.spin_trade_max = QSpinBox()
        self.spin_trade_max.setRange(0, 999999)
        self.spin_trade_max.setValue(100000)
        self.spin_trade_max.setSingleStep(1000)
        self.spin_trade_max.setEnabled(False)
        self.spin_trade_max.setToolTip("매매 최대 가격 (만원)")
        self._configure_filter_spinbox(self.spin_trade_max)
        price_grid.addWidget(self.spin_trade_max, 0, 3)
        price_grid.addWidget(_price_label("만원"), 0, 4)
        
        # 전세
        price_grid.addWidget(_price_label("전세"), 1, 0)
        self.spin_jeonse_min = QSpinBox()
        self.spin_jeonse_min.setRange(0, 999999)
        self.spin_jeonse_min.setSingleStep(1000)
        self.spin_jeonse_min.setEnabled(False)
        self.spin_jeonse_min.setToolTip("전세 최소 가격 (만원)")
        self._configure_filter_spinbox(self.spin_jeonse_min)
        price_grid.addWidget(self.spin_jeonse_min, 1, 1)
        price_grid.addWidget(_price_label("~"), 1, 2)
        self.spin_jeonse_max = QSpinBox()
        self.spin_jeonse_max.setRange(0, 999999)
        self.spin_jeonse_max.setValue(50000)
        self.spin_jeonse_max.setSingleStep(1000)
        self.spin_jeonse_max.setEnabled(False)
        self.spin_jeonse_max.setToolTip("전세 최대 가격 (만원)")
        self._configure_filter_spinbox(self.spin_jeonse_max)
        price_grid.addWidget(self.spin_jeonse_max, 1, 3)
        price_grid.addWidget(_price_label("만원"), 1, 4)
        
        # 월세 보증금
        price_grid.addWidget(_price_label("월세\n보증금"), 2, 0)
        self.spin_monthly_deposit_min = QSpinBox()
        self.spin_monthly_deposit_min.setRange(0, 999999)
        self.spin_monthly_deposit_min.setSingleStep(1000)
        self.spin_monthly_deposit_min.setEnabled(False)
        self.spin_monthly_deposit_min.setToolTip("월세 보증금 최소 금액 (만원)")
        self._configure_filter_spinbox(self.spin_monthly_deposit_min)
        price_grid.addWidget(self.spin_monthly_deposit_min, 2, 1)
        price_grid.addWidget(_price_label("~"), 2, 2)
        self.spin_monthly_deposit_max = QSpinBox()
        self.spin_monthly_deposit_max.setRange(0, 999999)
        self.spin_monthly_deposit_max.setValue(50000)
        self.spin_monthly_deposit_max.setSingleStep(1000)
        self.spin_monthly_deposit_max.setEnabled(False)
        self.spin_monthly_deposit_max.setToolTip("월세 보증금 최대 금액 (만원)")
        self._configure_filter_spinbox(self.spin_monthly_deposit_max)
        price_grid.addWidget(self.spin_monthly_deposit_max, 2, 3)
        price_grid.addWidget(_price_label("만원"), 2, 4)

        # 월세 금액
        price_grid.addWidget(_price_label("월세\n금액"), 3, 0)
        self.spin_monthly_rent_min = QSpinBox()
        self.spin_monthly_rent_min.setRange(0, 999999)
        self.spin_monthly_rent_min.setSingleStep(100)
        self.spin_monthly_rent_min.setEnabled(False)
        self.spin_monthly_rent_min.setToolTip("월 납입 금액 최소 (만원)")
        self._configure_filter_spinbox(self.spin_monthly_rent_min)
        price_grid.addWidget(self.spin_monthly_rent_min, 3, 1)
        price_grid.addWidget(_price_label("~"), 3, 2)
        self.spin_monthly_rent_max = QSpinBox()
        self.spin_monthly_rent_max.setRange(0, 999999)
        self.spin_monthly_rent_max.setValue(5000)
        self.spin_monthly_rent_max.setSingleStep(100)
        self.spin_monthly_rent_max.setEnabled(False)
        self.spin_monthly_rent_max.setToolTip("월 납입 금액 최대 (만원)")
        self._configure_filter_spinbox(self.spin_monthly_rent_max)
        price_grid.addWidget(self.spin_monthly_rent_max, 3, 3)
        price_grid.addWidget(_price_label("만원"), 3, 4)

        # Legacy aliases for preset/backward compatibility.
        self.spin_monthly_min = self.spin_monthly_rent_min
        self.spin_monthly_max = self.spin_monthly_rent_max
        
        pl.addLayout(price_grid)
        pg.setLayout(pl)
        layout.addWidget(pg)

    def _setup_complex_list_group(self: Any, layout):
        cg = QGroupBox("단지 목록")
        cl = QVBoxLayout()
        cl.setSpacing(6)

        # ── 불러오기 ──
        load_header = QLabel("불러오기")
        load_header.setStyleSheet("font-size: 10px; color: #888; font-weight: 600; letter-spacing: 0.5px;")
        cl.addWidget(load_header)
        load_btn = QHBoxLayout()
        load_btn.setSpacing(6)
        btn_db = QPushButton("💾 DB에서")
        btn_db.setObjectName("secondaryBtn")
        btn_db.setToolTip("데이터베이스에 저장된 단지 목록에서 불러옵니다.")
        btn_db.clicked.connect(self._show_db_load_dialog)
        btn_grp = QPushButton("📁 그룹에서")
        btn_grp.setObjectName("secondaryBtn")
        btn_grp.setToolTip("저장된 그룹에서 단지 목록을 일괄 불러옵니다.")
        btn_grp.clicked.connect(self._show_group_load_dialog)
        btn_hist = QPushButton("🕐 최근")
        btn_hist.setObjectName("secondaryBtn")
        btn_hist.setToolTip("최근에 검색한 단지 목록을 불러옵니다.")
        btn_hist.clicked.connect(self._show_recent_search_dialog)
        load_btn.addWidget(btn_db)
        load_btn.addWidget(btn_grp)
        load_btn.addWidget(btn_hist)
        cl.addLayout(load_btn)
        
        # ── 직접 입력 ──
        add_header = QLabel("직접 추가")
        add_header.setStyleSheet("font-size: 10px; color: #888; font-weight: 600; letter-spacing: 0.5px; margin-top: 4px;")
        cl.addWidget(add_header)
        input_layout = QHBoxLayout()
        input_layout.setSpacing(4)
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("단지명 (예: 래미안 퍼스티지)")
        self.input_name.setToolTip("아파트 단지명을 입력합니다. (선택사항)")
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("단지 ID")
        self.input_id.setToolTip(
            "네이버 부동산 URL에서 단지 ID를 확인하세요.\n"
            "예: new.land.naver.com/complexes/12345 → ID: 12345"
        )
        self._complex_id_regex = QRegularExpression(r"^\d{5,10}$")
        self.input_id.setValidator(QRegularExpressionValidator(self._complex_id_regex, self))
        btn_add = QPushButton("➕")
        btn_add.setObjectName("iconButton")
        btn_add.setToolTip("단지를 목록에 추가합니다. (Enter 키도 동작)")
        btn_add.setFixedWidth(38)
        btn_add.clicked.connect(self._add_complex)
        # Enter 키로도 추가 가능
        self.input_id.returnPressed.connect(self._add_complex)
        input_layout.addWidget(self.input_name, 2)
        input_layout.addWidget(self.input_id, 1)
        input_layout.addWidget(btn_add)
        cl.addLayout(input_layout)
        
        # ── 목록 ──
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(2)
        self.table_list.setHorizontalHeaderLabels(["단지명", "ID"])
        table_list_header = self.table_list.horizontalHeader()
        if table_list_header is not None:
            table_list_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.setMinimumHeight(120)
        self.table_list.setAlternatingRowColors(True)
        self.table_list.setToolTip("더블클릭하면 네이버 부동산 단지 페이지로 이동합니다.")
        self.table_list.doubleClicked.connect(self._open_complex_url)
        cl.addWidget(self.table_list)
        
        # ── 관리 ──
        manage_btn = QHBoxLayout()
        manage_btn.setSpacing(4)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.setObjectName("dangerBtn")
        btn_del.setToolTip("선택한 단지를 목록에서 제거합니다.")
        btn_del.clicked.connect(self._delete_complex)
        btn_clr = QPushButton("🧹 초기화")
        btn_clr.setObjectName("secondaryBtn")
        btn_clr.setToolTip("목록 전체를 초기화합니다.")
        btn_clr.clicked.connect(self._clear_list)
        btn_sv = QPushButton("💾 DB저장")
        btn_sv.setObjectName("secondaryBtn")
        btn_sv.setToolTip("현재 목록의 단지들을 데이터베이스에 저장합니다.")
        btn_sv.clicked.connect(self._save_to_db)
        btn_url = QPushButton("🔗 URL")
        btn_url.setObjectName("secondaryBtn")
        btn_url.setToolTip("네이버 부동산 URL을 붙여넣어 단지를 일괄 등록합니다.")
        btn_url.clicked.connect(self._show_url_batch_dialog)
        manage_btn.addWidget(btn_del)
        manage_btn.addWidget(btn_clr)
        manage_btn.addWidget(btn_sv)
        manage_btn.addWidget(btn_url)
        cl.addLayout(manage_btn)
        
        cg.setLayout(cl)
        layout.addWidget(cg)

    def _setup_speed_group(self: Any, layout):
        spg = QGroupBox("크롤링 속도")
        spl = QVBoxLayout()
        spl.setSpacing(6)
        engine_row = QHBoxLayout()
        lbl_engine = QLabel("엔진")
        lbl_engine.setStyleSheet("font-size: 11px; color: #888;")
        engine_row.addWidget(lbl_engine)
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["playwright", "selenium"])
        self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.combo_engine.setToolTip(
            "playwright (기본 권장): 빠르고 차단 회피 우수\n"
            "selenium: playwright 실패 시 자동 fallback"
        )
        self.combo_engine.currentTextChanged.connect(lambda text: settings.set("crawl_engine", text))
        engine_row.addWidget(self.combo_engine, 1)
        engine_row.addStretch()
        spl.addLayout(engine_row)

        self.speed_slider = SpeedSlider()
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self.speed_slider.speed_changed.connect(self._on_speed_changed)
        spl.addWidget(self.speed_slider)

        hint = QLabel("💡 느릴수록 차단될 위험이 낮습니다.")
        hint.setObjectName("hintLabel")
        spl.addWidget(hint)
        spg.setLayout(spl)
        layout.addWidget(spg)

    def _setup_action_group(self: Any, layout):
        eg = QGroupBox("실행")
        el = QHBoxLayout()
        el.setSpacing(8)
        self.btn_start = QPushButton("▶ 크롤링 시작")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.setMinimumHeight(44)
        self.btn_start.setToolTip("단지 목록의 모든 단지에서 매물을 수집합니다. (단축키: Ctrl+R)")
        self.btn_start.clicked.connect(self.start_crawling)
        
        self.btn_stop = QPushButton("⏹ 중지")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setToolTip("진행 중인 수집을 중지합니다. (단축키: Ctrl+Shift+R)")
        self.btn_stop.clicked.connect(self.stop_crawling)
        
        self.btn_save = QPushButton("💾 저장")
        self.btn_save.setObjectName("secondaryBtn")
        self.btn_save.setEnabled(False)
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setToolTip("수집된 매물을 Excel/CSV/JSON으로 저장합니다. (단축키: Ctrl+S)")
        self.btn_save.clicked.connect(self.show_save_menu)
        
        el.addWidget(self.btn_start, 2)
        el.addWidget(self.btn_stop, 1)
        el.addWidget(self.btn_save, 1)

        eg.setLayout(el)
        layout.addWidget(eg)

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

    def _load_state(self: Any):
        # Load any persisted state if needed
        logger.debug("CrawlerTab 상태 로드 없음 (기본값 사용)")
        self._restore_splitter_state()
        self.update_runtime_settings()
        self._update_advanced_filter_badge()

    def set_theme(self: Any, theme):
        self.current_theme = theme
        if hasattr(self, 'summary_card'):
            self.summary_card.set_theme(theme)
        if hasattr(self, 'card_view'):
            self.card_view.is_dark = (theme == "dark")

    def _on_speed_changed(self: Any, speed):
        settings.set("crawl_speed", speed)

    def _default_sort_criterion(self: Any):
        column = str(settings.get("default_sort_column", "가격") or "가격")
        order = str(settings.get("default_sort_order", "asc") or "asc").lower()
        if column == "거래":
            column = "거래유형"
        if column not in {"가격", "면적", "단지명", "거래유형"}:
            column = "가격"
        arrow = "↑" if order == "asc" else "↓"
        return f"{column} {arrow}"

    def _apply_default_sort_settings(self: Any):
        criterion = self._default_sort_criterion()
        idx = self.combo_sort.findText(criterion)
        if idx < 0:
            return
        self.combo_sort.blockSignals(True)
        self.combo_sort.setCurrentIndex(idx)
        self.combo_sort.blockSignals(False)
        if self.result_table.rowCount() > 0:
            self._sort_results(self.combo_sort.currentText())

    def update_runtime_settings(self: Any):
        try:
            debounce_ms = max(80, int(settings.get("result_filter_debounce_ms", 220)))
        except (TypeError, ValueError):
            debounce_ms = 220
        self._search_timer.setInterval(debounce_ms)
        if hasattr(self, "combo_engine"):
            self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self._apply_default_sort_settings()

        compact = bool(settings.get("compact_duplicate_listings", True))
        self.check_compact_duplicates.setChecked(compact)
        
    def _toggle_area_filter(self: Any, state):
        enabled = state == Qt.CheckState.Checked.value
        self.spin_area_min.setEnabled(enabled)
        self.spin_area_max.setEnabled(enabled)
        
    def _toggle_price_filter(self: Any, state):
        enabled = state == Qt.CheckState.Checked.value
        for w in [
            self.spin_trade_min,
            self.spin_trade_max,
            self.spin_jeonse_min,
            self.spin_jeonse_max,
            self.spin_monthly_deposit_min,
            self.spin_monthly_deposit_max,
            self.spin_monthly_rent_min,
            self.spin_monthly_rent_max,
        ]:
            w.setEnabled(enabled)

