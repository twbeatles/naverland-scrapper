from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


FavoriteKey = tuple[str, str, str]
FavoriteKeyProvider = Callable[[], set[FavoriteKey]]
CompactRowKey = tuple[str, str, str, str, str, float, str]
RowPayload = dict[str, Any]
ResultRow = dict[str, Any]


class CrawlerTabControlSetupMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

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
            "네이버 부동산 URL family에 따라 단지 경로가 다를 수 있습니다.\n"
            "예: /complexes/12345 또는 complexNo=12345 → ID: 12345"
        )
        self._complex_id_regex = QRegularExpression(r"^\d+$")
        self.input_id.setValidator(QRegularExpressionValidator(self._complex_id_regex, self))
        self.combo_manual_asset = QComboBox()
        self.combo_manual_asset.addItems(["APT", "VL"])
        self.combo_manual_asset.setToolTip("직접 추가할 대상의 자산 유형을 선택합니다.")
        self.combo_manual_asset.setFixedWidth(72)
        btn_add = QPushButton("➕")
        btn_add.setObjectName("iconButton")
        btn_add.setToolTip("단지를 목록에 추가합니다. (Enter 키도 동작)")
        btn_add.setFixedWidth(38)
        btn_add.clicked.connect(self._add_complex)
        # Enter 키로도 추가 가능
        self.input_id.returnPressed.connect(self._add_complex)
        input_layout.addWidget(self.input_name, 2)
        input_layout.addWidget(self.input_id, 1)
        input_layout.addWidget(self.combo_manual_asset)
        input_layout.addWidget(btn_add)
        cl.addLayout(input_layout)
        
        # ── 목록 ──
        self.table_list = QTableWidget()
        self.table_list.setColumnCount(3)
        self.table_list.setHorizontalHeaderLabels(["단지명", "ID", "자산"])
        table_list_header = self.table_list.horizontalHeader()
        if table_list_header is not None:
            table_list_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.setColumnWidth(1, 110)
        self.table_list.setColumnWidth(2, 70)
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

    def _on_speed_changed(self: Any, speed):
        settings.set("crawl_speed", speed)

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
