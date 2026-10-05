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
        spinbox.setMinimumWidth(96)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        spinbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _field_label(self: Any, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _make_disclosure(self: Any, title: str, content: QWidget, *, expanded: bool = False):
        """접었다 펼치는 보조 영역. 닫혀 있을 때는 제목 한 줄만 차지한다."""
        button = QPushButton()
        button.setObjectName("disclosureBtn")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        def _sync(checked: bool):
            button.setText(("▾  " if checked else "▸  ") + title)
            content.setVisible(bool(checked))

        button.toggled.connect(_sync)
        button.setChecked(bool(expanded))
        _sync(bool(expanded))
        return button

    # ── 1. 거래 종류 ────────────────────────────────────────────────
    def _setup_options_group(self: Any, layout):
        tg = QGroupBox("거래 종류")
        tl = QHBoxLayout()
        tl.setSpacing(16)
        self.check_trade = QCheckBox("매매")
        self.check_trade.setChecked(True)
        self.check_trade.setToolTip("매매 매물을 수집합니다.")
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

    # ── 2. 조건·속도 (선택, 기본 접힘) ───────────────────────────────
    def _setup_filter_group(self: Any, layout):
        wrap = QGroupBox("조건과 속도")
        wrap_layout = QVBoxLayout()
        wrap_layout.setSpacing(8)

        hint = QLabel("기본은 모든 매물을 수집합니다. 범위를 좁히고 싶을 때만 켜세요.")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        wrap_layout.addWidget(hint)

        # 면적
        self.check_area_filter = QCheckBox("면적 범위 지정")
        self.check_area_filter.setToolTip("켜면 정한 면적 범위의 매물만 수집합니다.")
        self.check_area_filter.stateChanged.connect(self._toggle_area_filter)
        wrap_layout.addWidget(self.check_area_filter)

        area_input = QHBoxLayout()
        area_input.setContentsMargins(24, 0, 0, 0)
        area_input.setSpacing(8)
        self.spin_area_min = QSpinBox()
        self.spin_area_min.setRange(0, 300)
        self.spin_area_min.setSuffix(" ㎡")
        self.spin_area_min.setEnabled(False)
        self.spin_area_min.setToolTip("최소 면적\n예: 59㎡ = 약 18평")
        self._configure_filter_spinbox(self.spin_area_min)
        self.spin_area_max = QSpinBox()
        self.spin_area_max.setRange(0, 300)
        self.spin_area_max.setValue(200)
        self.spin_area_max.setSuffix(" ㎡")
        self.spin_area_max.setEnabled(False)
        self.spin_area_max.setToolTip("최대 면적\n예: 84㎡ = 약 25평")
        self._configure_filter_spinbox(self.spin_area_max)
        area_input.addWidget(self.spin_area_min, 1)
        area_input.addWidget(self._field_label("~"))
        area_input.addWidget(self.spin_area_max, 1)
        wrap_layout.addLayout(area_input)

        # 가격
        self.check_price_filter = QCheckBox("가격 범위 지정")
        self.check_price_filter.setToolTip(
            "켜면 정한 가격 범위의 매물만 수집합니다.\n단위는 만원입니다. (10,000만원 = 1억)"
        )
        self.check_price_filter.stateChanged.connect(self._toggle_price_filter)
        wrap_layout.addWidget(self.check_price_filter)

        price_grid = QGridLayout()
        price_grid.setContentsMargins(24, 0, 0, 0)
        price_grid.setHorizontalSpacing(8)
        price_grid.setVerticalSpacing(8)
        price_grid.setColumnStretch(1, 1)
        price_grid.setColumnStretch(3, 1)

        def _price_spin(value: int, step: int, tip: str) -> QSpinBox:
            spin = QSpinBox()
            spin.setRange(0, 999999)
            spin.setSingleStep(step)
            spin.setValue(value)
            spin.setGroupSeparatorShown(True)
            spin.setSuffix(" 만원")
            spin.setEnabled(False)
            spin.setToolTip(tip)
            self._configure_filter_spinbox(spin)
            return spin

        def _price_row(row: int, label: str, spin_min: QSpinBox, spin_max: QSpinBox):
            price_grid.addWidget(self._field_label(label), row, 0)
            price_grid.addWidget(spin_min, row, 1)
            price_grid.addWidget(self._field_label("~"), row, 2)
            price_grid.addWidget(spin_max, row, 3)

        self.spin_trade_min = _price_spin(0, 1000, "매매 최소 가격")
        self.spin_trade_max = _price_spin(100000, 1000, "매매 최대 가격 (100,000만원 = 10억)")
        _price_row(0, "매매", self.spin_trade_min, self.spin_trade_max)

        self.spin_jeonse_min = _price_spin(0, 1000, "전세 최소 가격")
        self.spin_jeonse_max = _price_spin(50000, 1000, "전세 최대 가격 (50,000만원 = 5억)")
        _price_row(1, "전세", self.spin_jeonse_min, self.spin_jeonse_max)

        self.spin_monthly_deposit_min = _price_spin(0, 1000, "월세 보증금 최소 금액")
        self.spin_monthly_deposit_max = _price_spin(50000, 1000, "월세 보증금 최대 금액")
        _price_row(2, "월세 보증금", self.spin_monthly_deposit_min, self.spin_monthly_deposit_max)

        self.spin_monthly_rent_min = _price_spin(0, 100, "매달 내는 월세 최소 금액")
        self.spin_monthly_rent_max = _price_spin(5000, 100, "매달 내는 월세 최대 금액")
        _price_row(3, "월세", self.spin_monthly_rent_min, self.spin_monthly_rent_max)

        # Legacy aliases for preset/backward compatibility.
        self.spin_monthly_min = self.spin_monthly_rent_min
        self.spin_monthly_max = self.spin_monthly_rent_max

        wrap_layout.addLayout(price_grid)
        self._setup_speed_group(wrap_layout)
        wrap.setLayout(wrap_layout)

        toggle = self._make_disclosure("조건·속도 설정 (선택)", wrap, expanded=False)
        layout.addWidget(toggle)
        layout.addWidget(wrap)
        self.filter_panel = wrap
        self.btn_filter_toggle = toggle

    # ── 3. 수집할 단지 ───────────────────────────────────────────────
    def _setup_complex_list_group(self: Any, layout):
        cg = QGroupBox("수집할 단지")
        cl = QVBoxLayout()
        cl.setSpacing(8)

        # 추가 방법: 이름으로 찾기(주) + 불러오기(보조)
        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.btn_find_complex = QPushButton("단지 찾기")
        self.btn_find_complex.setIcon(FIF.SEARCH.icon())
        self.btn_find_complex.setObjectName("secondaryBtn")
        self.btn_find_complex.setToolTip("단지 이름이나 지역으로 검색해 목록에 추가합니다. (예: 래미안, 반포자이)")
        self.btn_find_complex.clicked.connect(self._show_keyword_search_dialog)
        add_row.addWidget(self.btn_find_complex, 1)

        self.btn_load_complex = QPushButton("불러오기")
        self.btn_load_complex.setIcon(FIF.FOLDER.icon())
        self.btn_load_complex.setObjectName("secondaryBtn")
        self.btn_load_complex.setToolTip("저장해 둔 단지나 이전에 수집한 목록을 불러옵니다.")
        load_menu = QMenu(self.btn_load_complex)
        load_menu.addAction("내 단지에서 고르기", self._show_db_load_dialog)
        load_menu.addAction("단지 묶음 불러오기", self._show_group_load_dialog)
        load_menu.addAction("최근 수집 조건 불러오기", self._show_recent_search_dialog)
        load_menu.addSeparator()
        load_menu.addAction("네이버 부동산 주소 붙여넣기", self._show_url_batch_dialog)
        self.btn_load_complex.setMenu(load_menu)
        add_row.addWidget(self.btn_load_complex, 1)
        cl.addLayout(add_row)

        # 단지 번호로 직접 추가 (자주 쓰지 않으므로 접어 둔다)
        manual = QWidget()
        input_layout = QHBoxLayout(manual)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("단지 이름 (선택)")
        self.input_name.setToolTip("목록에 표시할 이름입니다. 비워 두면 번호로 표시합니다.")
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("단지 번호")
        self.input_id.setToolTip(
            "네이버 부동산 단지 주소에 들어 있는 숫자입니다.\n"
            "예: land.naver.com/complexes/12345 → 12345"
        )
        self._complex_id_regex = QRegularExpression(r"^\d+$")
        self.input_id.setValidator(QRegularExpressionValidator(self._complex_id_regex, self))
        self.combo_manual_asset = QComboBox()
        self.combo_manual_asset.addItem("아파트", "APT")
        self.combo_manual_asset.addItem("빌라", "VL")
        self.combo_manual_asset.setToolTip("추가할 단지의 주택 종류입니다.")
        self.combo_manual_asset.setFixedWidth(88)
        btn_add = QPushButton()
        btn_add.setIcon(FIF.ADD.icon())
        btn_add.setObjectName("iconButton")
        btn_add.setToolTip("목록에 추가합니다. (Enter 키도 됩니다)")
        btn_add.setFixedWidth(38)
        btn_add.clicked.connect(self._add_complex)
        self.input_id.returnPressed.connect(self._add_complex)
        input_layout.addWidget(self.input_name, 3)
        input_layout.addWidget(self.input_id, 2)
        input_layout.addWidget(self.combo_manual_asset)
        input_layout.addWidget(btn_add)

        self.btn_manual_toggle = self._make_disclosure("단지 번호로 직접 추가", manual, expanded=False)
        cl.addWidget(self.btn_manual_toggle)
        cl.addWidget(manual)

        # 목록
        self.lbl_list_placeholder = QLabel(
            "아직 추가한 단지가 없습니다.\n「단지 찾기」로 이름을 검색해 추가해 보세요."
        )
        self.lbl_list_placeholder.setObjectName("listPlaceholder")
        self.lbl_list_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_list_placeholder.setWordWrap(True)
        cl.addWidget(self.lbl_list_placeholder)

        self.table_list = QTableWidget()
        self.table_list.setColumnCount(3)
        self.table_list.setHorizontalHeaderLabels(["단지 이름", "단지 번호", "종류"])
        table_list_header = self.table_list.horizontalHeader()
        if table_list_header is not None:
            table_list_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_list.setColumnWidth(1, 96)
        self.table_list.setColumnWidth(2, 72)
        self.table_list.setMinimumHeight(140)
        self.table_list.setAlternatingRowColors(True)
        self.table_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        list_vheader = self.table_list.verticalHeader()
        if list_vheader is not None:
            list_vheader.setVisible(False)
        self.table_list.setToolTip("두 번 누르면 네이버 부동산 단지 페이지를 엽니다.")
        self.table_list.doubleClicked.connect(self._open_complex_url)
        from src.ui.widgets.components import install_token_labels
        from src.utils.ui_labels import asset_label

        install_token_labels(self.table_list, 2, asset_label)
        cl.addWidget(self.table_list, 1)

        # 목록 관리
        manage_btn = QHBoxLayout()
        manage_btn.setSpacing(8)
        self.lbl_list_count = QLabel("")
        self.lbl_list_count.setObjectName("countBadge")
        manage_btn.addWidget(self.lbl_list_count)
        manage_btn.addStretch()
        self.btn_list_save = QPushButton("내 단지에 저장")
        self.btn_list_save.setObjectName("secondaryBtn")
        self.btn_list_save.setToolTip("이 목록을 「내 단지」에 저장해 두고 다음에 다시 불러올 수 있습니다.")
        self.btn_list_save.clicked.connect(self._save_to_db)
        self.btn_list_delete = QPushButton("선택 빼기")
        self.btn_list_delete.setObjectName("secondaryBtn")
        self.btn_list_delete.setToolTip("선택한 단지를 목록에서 뺍니다. 저장된 데이터는 지워지지 않습니다.")
        self.btn_list_delete.clicked.connect(self._delete_complex)
        self.btn_list_clear = QPushButton("모두 비우기")
        self.btn_list_clear.setObjectName("secondaryBtn")
        self.btn_list_clear.setToolTip("목록을 비웁니다. 저장된 데이터는 지워지지 않습니다.")
        self.btn_list_clear.clicked.connect(self._clear_list)
        manage_btn.addWidget(self.btn_list_save)
        manage_btn.addWidget(self.btn_list_delete)
        manage_btn.addWidget(self.btn_list_clear)
        cl.addLayout(manage_btn)

        cg.setLayout(cl)
        layout.addWidget(cg, 1)

        model = self.table_list.model()
        if model is not None:
            model.rowsInserted.connect(lambda *_: self._update_task_list_state())
            model.rowsRemoved.connect(lambda *_: self._update_task_list_state())
            model.modelReset.connect(lambda *_: self._update_task_list_state())
        self.table_list.itemSelectionChanged.connect(self._update_task_list_state)
        self._update_task_list_state()

    def _update_task_list_state(self: Any):
        """단지 목록의 개수·안내 문구·버튼 활성 상태를 맞춘다."""
        table = getattr(self, "table_list", None)
        if table is None:
            return
        count = int(table.rowCount() or 0)
        has_rows = count > 0
        placeholder = getattr(self, "lbl_list_placeholder", None)
        if placeholder is not None:
            placeholder.setVisible(not has_rows)
        table.setVisible(has_rows)
        label = getattr(self, "lbl_list_count", None)
        if label is not None:
            label.setText(f"{count}곳" if has_rows else "")
        for name in ("btn_list_save", "btn_list_clear"):
            btn = getattr(self, name, None)
            if btn is not None:
                btn.setEnabled(has_rows)
        btn_delete = getattr(self, "btn_list_delete", None)
        if btn_delete is not None:
            btn_delete.setEnabled(has_rows and table.currentRow() >= 0)

    # ── 수집 속도 (조건 영역 안에 들어간다) ───────────────────────────
    def _setup_speed_group(self: Any, layout):
        # Engine stays in Settings → Advanced. Keep a hidden combo for runtime sync / tests.
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["playwright", "selenium"])
        self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.combo_engine.setVisible(False)
        self.combo_engine.currentTextChanged.connect(
            lambda text: settings.set("crawl_engine", text)
        )
        layout.addWidget(self.combo_engine)

        speed_title = QLabel("수집 속도")
        speed_title.setStyleSheet("font-weight: 600; margin-top: 8px;")
        layout.addWidget(speed_title)
        self.speed_slider = SpeedSlider()
        self.speed_slider.set_speed(settings.get("crawl_speed", "보통"))
        self.speed_slider.speed_changed.connect(self._on_speed_changed)
        layout.addWidget(self.speed_slider)

        hint = QLabel("너무 빠르면 네이버에서 잠시 접속을 막을 수 있습니다. 보통 이하를 권장합니다.")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    # ── 실행 (왼쪽 패널 아래에 항상 보인다) ───────────────────────────
    def _setup_action_group(self: Any, layout):
        bar = QWidget()
        bar.setObjectName("actionBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        el = QHBoxLayout(bar)
        el.setContentsMargins(12, 12, 12, 12)
        el.setSpacing(8)
        self.btn_start = QPushButton("수집 시작")
        self.btn_start.setIcon(FIF.PLAY.icon())
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setToolTip("목록에 있는 단지의 매물을 수집합니다. (Ctrl+R)")
        self.btn_start.clicked.connect(self.start_crawling)

        self.btn_stop = QPushButton("중지")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setToolTip("진행 중인 수집을 멈춥니다. 그때까지 모은 결과는 남습니다. (Ctrl+Shift+R)")
        self.btn_stop.clicked.connect(self.stop_crawling)

        self.btn_save = QPushButton("결과 저장")
        self.btn_save.setIcon(FIF.SAVE.icon())
        self.btn_save.setObjectName("secondaryBtn")
        self.btn_save.setEnabled(False)
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setToolTip("수집한 매물을 엑셀 등 파일로 저장합니다. (Ctrl+S)")
        self.btn_save.clicked.connect(self.show_save_menu)

        el.addWidget(self.btn_start, 2)
        el.addWidget(self.btn_stop, 1)
        el.addWidget(self.btn_save, 1)
        layout.addWidget(bar)

    def _on_speed_changed(self: Any, speed):
        settings.set("crawl_speed", speed)

    def _reveal_filter_panel(self: Any):
        toggle = getattr(self, "btn_filter_toggle", None)
        if toggle is not None and not toggle.isChecked():
            toggle.setChecked(True)

    def _toggle_area_filter(self: Any, state):
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
            self._reveal_filter_panel()
        self.spin_area_min.setEnabled(enabled)
        self.spin_area_max.setEnabled(enabled)

    def _toggle_price_filter(self: Any, state):
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
            self._reveal_filter_panel()
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
