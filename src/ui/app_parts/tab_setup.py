from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppTabSetupMixin:
    TAB_CRAWLER = 0
    TAB_GEO = 1
    TAB_DB = 2
    TAB_GROUP = 3
    TAB_SCHEDULE = 4
    TAB_HISTORY = 5
    TAB_STATS = 6
    TAB_DASHBOARD = 7
    TAB_FAVORITES = 8
    TAB_GUIDE = 9

    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _init_ui(self: Any):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(12, 8, 12, 4)
        layout.setSpacing(6)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.status_bar = self.statusBar()

        self.crawler_tab = self._create_crawler_tab()
        self.tabs.addTab(self.crawler_tab, "🏠 데이터 수집")

        self.geo_tab = self._create_geo_tab()
        self.tabs.addTab(self.geo_tab, "🧭 지도 탐색")

        self.db_tab = self._create_db_tab()
        self.tabs.addTab(self.db_tab, "💾 단지 DB")

        self.group_tab = self._create_group_tab()
        self.tabs.addTab(self.group_tab, "📁 그룹 관리")
        
        self._setup_schedule_tab()
        self._setup_history_tab()
        self._setup_stats_tab()
        self._setup_dashboard_tab()
        self._setup_favorites_tab()
        self._setup_guide_tab()
        self.tabs.currentChanged.connect(self._refresh_tab)

    # Obsolete setup methods removed (replaced by modular widgets)
    # _setup_crawler_tab, _setup_db_tab, _setup_groups_tab removed

    def _create_crawler_tab(self: Any):
        from src.ui.widgets.crawler_tab import CrawlerTab

        tab = CrawlerTab(
            self.db,
            history_manager=self.history_manager,
            theme=self.current_theme,
            maintenance_guard=lambda: self._maintenance_mode,
        )
        tab.card_view.favorite_toggled.connect(self._on_favorite_toggled)
        tab.favorite_keys_provider = lambda: set(self.favorite_keys)
        tab.data_collected.connect(self._on_crawl_data_collected)
        tab.status_message.connect(self.status_bar.showMessage)
        tab.alert_triggered.connect(self._on_alert_triggered)
        return tab

    def _create_geo_tab(self: Any):
        from src.ui.widgets.geo_crawler_tab import GeoCrawlerTab

        tab = GeoCrawlerTab(
            self.db,
            history_manager=self.history_manager,
            theme=self.current_theme,
            maintenance_guard=lambda: self._maintenance_mode,
        )
        tab.card_view.favorite_toggled.connect(self._on_favorite_toggled)
        tab.favorite_keys_provider = lambda: set(self.favorite_keys)
        tab.data_collected.connect(self._on_crawl_data_collected)
        tab.status_message.connect(self.status_bar.showMessage)
        tab.alert_triggered.connect(self._on_alert_triggered)
        return tab

    def _create_db_tab(self: Any):
        from src.ui.widgets.database_tab import DatabaseTab

        return DatabaseTab(self.db)

    def _create_group_tab(self: Any):
        from src.ui.widgets.group_tab import GroupTab

        tab = GroupTab(self.db)
        tab.groups_updated.connect(self._load_schedule_groups)
        return tab

    def _ensure_db_tab(self: Any):
        tab = getattr(self, "db_tab", None)
        if tab is None:
            tab = self._create_db_tab()
            self.db_tab = tab
        return tab

    def _ensure_group_tab(self: Any):
        tab = getattr(self, "group_tab", None)
        if tab is not None:
            return tab
        tab = self._create_group_tab()
        self.group_tab = tab
        return tab

    def _ensure_favorites_tab(self: Any):
        tab = getattr(self, "favorites_tab", None)
        if tab is None:
            from src.ui.widgets.tabs import FavoritesTab

            tab = FavoritesTab(self.db, theme=self.current_theme, favorite_toggled=self._on_favorite_toggled)
            self.favorites_tab = tab
        return tab

    
    def _setup_schedule_tab(self: Any):
        self.schedule_tab = QWidget()
        layout = QVBoxLayout(self.schedule_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        sg = QGroupBox("⏰ 예약 크롤링")
        sl = QVBoxLayout()
        sl.setSpacing(10)

        self.check_schedule = QCheckBox("예약 실행 활성화")
        self.check_schedule.setToolTip("설정한 시간에 현재 예약 설정으로 자동 실행합니다.")
        sl.addWidget(self.check_schedule)

        tl = QHBoxLayout()
        lbl_time = QLabel("실행 시간")
        lbl_time.setStyleSheet("font-size: 12px; color: #888;")
        tl.addWidget(lbl_time)
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(9, 0))
        self.time_edit.setToolTip("크롤링을 시작할 시간을 설정합니다.")
        tl.addWidget(self.time_edit)
        tl.addStretch()
        sl.addLayout(tl)

        ml = QHBoxLayout()
        lbl_mode = QLabel("실행 모드")
        lbl_mode.setStyleSheet("font-size: 12px; color: #888;")
        ml.addWidget(lbl_mode)
        self.schedule_mode_combo = QComboBox()
        self.schedule_mode_combo.addItem("complex", "complex")
        self.schedule_mode_combo.addItem("geo_sweep", "geo_sweep")
        self.schedule_mode_combo.setToolTip("예약 실행 시 사용할 수집 모드를 선택합니다.")
        ml.addWidget(self.schedule_mode_combo)
        ml.addStretch()
        sl.addLayout(ml)

        self.schedule_group_widget = QWidget()
        gl = QHBoxLayout(self.schedule_group_widget)
        gl.setContentsMargins(0, 0, 0, 0)
        lbl_grp = QLabel("대상 그룹")
        lbl_grp.setStyleSheet("font-size: 12px; color: #888;")
        gl.addWidget(lbl_grp)
        self.schedule_group_combo = QComboBox()
        self.schedule_group_combo.setToolTip("예약 크롤링을 실행할 단지 그룹을 선택합니다.")
        gl.addWidget(self.schedule_group_combo, 1)
        gl.addStretch()
        sl.addWidget(self.schedule_group_widget)

        self.schedule_geo_widget = QWidget()
        geo_layout = QGridLayout(self.schedule_geo_widget)
        geo_layout.setContentsMargins(0, 0, 0, 0)
        geo_layout.setHorizontalSpacing(8)
        geo_layout.setVerticalSpacing(6)
        geo_layout.addWidget(QLabel("위도"), 0, 0)
        self.schedule_geo_lat = QDoubleSpinBox()
        self.schedule_geo_lat.setRange(33.0, 39.5)
        self.schedule_geo_lat.setDecimals(6)
        self.schedule_geo_lat.setValue(37.5608)
        geo_layout.addWidget(self.schedule_geo_lat, 0, 1)
        geo_layout.addWidget(QLabel("경도"), 1, 0)
        self.schedule_geo_lon = QDoubleSpinBox()
        self.schedule_geo_lon.setRange(124.0, 132.1)
        self.schedule_geo_lon.setDecimals(6)
        self.schedule_geo_lon.setValue(126.9888)
        geo_layout.addWidget(self.schedule_geo_lon, 1, 1)
        geo_layout.addWidget(QLabel("줌"), 0, 2)
        self.schedule_geo_zoom = QSpinBox()
        self.schedule_geo_zoom.setRange(12, 18)
        self.schedule_geo_zoom.setValue(15)
        geo_layout.addWidget(self.schedule_geo_zoom, 0, 3)
        geo_layout.addWidget(QLabel("링 수"), 1, 2)
        self.schedule_geo_rings = QSpinBox()
        self.schedule_geo_rings.setRange(0, 6)
        self.schedule_geo_rings.setValue(1)
        geo_layout.addWidget(self.schedule_geo_rings, 1, 3)
        geo_layout.addWidget(QLabel("간격(px)"), 2, 0)
        self.schedule_geo_step = QSpinBox()
        self.schedule_geo_step.setRange(120, 1600)
        self.schedule_geo_step.setSingleStep(40)
        self.schedule_geo_step.setValue(480)
        geo_layout.addWidget(self.schedule_geo_step, 2, 1)
        geo_layout.addWidget(QLabel("대기(ms)"), 2, 2)
        self.schedule_geo_dwell = QSpinBox()
        self.schedule_geo_dwell.setRange(100, 5000)
        self.schedule_geo_dwell.setSingleStep(100)
        self.schedule_geo_dwell.setValue(600)
        geo_layout.addWidget(self.schedule_geo_dwell, 2, 3)
        geo_layout.addWidget(QLabel("자산"), 3, 0)
        asset_row = QHBoxLayout()
        self.schedule_geo_asset_apt = QCheckBox("APT")
        self.schedule_geo_asset_vl = QCheckBox("VL")
        self.schedule_geo_asset_apt.setChecked(True)
        self.schedule_geo_asset_vl.setChecked(True)
        asset_row.addWidget(self.schedule_geo_asset_apt)
        asset_row.addWidget(self.schedule_geo_asset_vl)
        asset_row.addStretch()
        geo_layout.addLayout(asset_row, 3, 1, 1, 3)
        geo_hint = QLabel("geo_sweep 예약은 좌표와 세부 geo 프로필을 함께 저장해 실행합니다.")
        geo_hint.setObjectName("hintLabel")
        geo_layout.addWidget(geo_hint, 4, 0, 1, 4)
        sl.addWidget(self.schedule_geo_widget)

        hint = QLabel("💡 complex는 그룹을, geo_sweep는 지도 중심 좌표를 사용합니다.")
        hint.setObjectName("hintLabel")
        sl.addWidget(hint)

        sg.setLayout(sl)
        layout.addWidget(sg)

        self.schedule_empty_label = QLabel("예약할 그룹이 없습니다.\n그룹 관리 탭에서 그룹을 먼저 생성하세요.")
        self.schedule_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schedule_empty_label.setStyleSheet("color: #888; padding: 20px; font-size: 13px;")
        self.schedule_empty_label.hide()
        layout.addWidget(self.schedule_empty_label)
        layout.addStretch()
        self.tabs.addTab(self.schedule_tab, "⏰ 예약")

        self.check_schedule.toggled.connect(self._save_schedule_config)
        self.time_edit.timeChanged.connect(self._save_schedule_config)
        self.schedule_mode_combo.currentIndexChanged.connect(self._on_schedule_mode_changed)
        self.schedule_group_combo.currentIndexChanged.connect(self._save_schedule_config)
        self.schedule_geo_lat.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_lon.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_zoom.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_rings.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_step.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_dwell.valueChanged.connect(self._save_schedule_config)
        self.schedule_geo_asset_apt.toggled.connect(self._save_schedule_config)
        self.schedule_geo_asset_vl.toggled.connect(self._save_schedule_config)
    
    def _setup_history_tab(self: Any):
        self.history_tab = QWidget()
        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        bl = QHBoxLayout()
        btn_rf = QPushButton("🔄 새로고침")
        btn_rf.setToolTip("크롤링 이력을 다시 불러옵니다.")
        btn_rf.clicked.connect(self._load_history)
        bl.addWidget(btn_rf)
        bl.addStretch()
        layout.addLayout(bl)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels(
            ["단지명", "단지ID", "자산", "엔진", "모드", "상태", "거래유형", "수집건수", "수집시각"]
        )
        history_header = self.history_table.horizontalHeader()
        if history_header is not None:
            history_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)

        self.history_empty_label = QLabel("크롤링 이력이 없습니다.\n데이터 수집 탭에서 크롤링을 실행해 보세요.")
        self.history_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty_label.setStyleSheet("color: #888; font-size: 13px; padding: 40px;")
        layout.addWidget(self.history_empty_label)
        self.history_empty_label.hide()

        self.tabs.addTab(self.history_tab, "📜 히스토리")
    
    def _setup_stats_tab(self: Any):
        self.stats_tab = QWidget()
        layout = QVBoxLayout(self.stats_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        fl = QHBoxLayout()
        fl.setSpacing(8)
        lbl_cplx = QLabel("단지")
        lbl_cplx.setStyleSheet("font-size: 12px; color: #888;")
        fl.addWidget(lbl_cplx)
        self.stats_complex_combo = QComboBox()
        self.stats_complex_combo.setToolTip("통계를 볼 단지를 선택합니다.")
        fl.addWidget(self.stats_complex_combo)
        lbl_type = QLabel("유형")
        lbl_type.setStyleSheet("font-size: 12px; color: #888;")
        fl.addWidget(lbl_type)
        self.stats_type_combo = QComboBox()
        self.stats_type_combo.addItems(["전체", "매매", "전세", "월세"])
        fl.addWidget(self.stats_type_combo)
        self.stats_metric_label = QLabel("지표")
        self.stats_metric_label.setStyleSheet("font-size: 12px; color: #888;")
        fl.addWidget(self.stats_metric_label)
        self.stats_metric_combo = QComboBox()
        self.stats_metric_combo.addItem("월세 금액", "rent")
        self.stats_metric_combo.addItem("보증금", "deposit")
        self.stats_metric_combo.setToolTip("월세 통계에서 표시할 가격 지표를 선택합니다.")
        fl.addWidget(self.stats_metric_combo)
        self.stats_type_combo.currentIndexChanged.connect(self._on_stats_type_changed)
        self.stats_metric_combo.currentIndexChanged.connect(self._load_stats)
        lbl_area = QLabel("면적")
        lbl_area.setStyleSheet("font-size: 12px; color: #888;")
        fl.addWidget(lbl_area)
        self.stats_pyeong_combo = QComboBox()
        self.stats_pyeong_combo.addItem("전체")
        fl.addWidget(self.stats_pyeong_combo)
        btn_load = QPushButton("📊 조회")
        btn_load.setToolTip("선택한 조건으로 가격 시세 데이터를 불러옵니다.")
        btn_load.clicked.connect(self._load_stats)
        fl.addWidget(btn_load)
        fl.addStretch()
        layout.addLayout(fl)
        self.stats_metric_label.hide()
        self.stats_metric_combo.hide()

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["날짜", "유형", "평형", "최저가", "최고가", "평균가"])
        stats_header = self.stats_table.horizontalHeader()
        if stats_header is not None:
            stats_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setAlternatingRowColors(True)
        
        # v10.0: Chart Integration
        self.stats_splitter = QSplitter(Qt.Orientation.Vertical)
        self.stats_splitter.addWidget(self.stats_table)
        self.chart_widget = None
        self.chart_placeholder = QLabel("차트는 통계 조회 시 로드됩니다.")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_splitter.addWidget(self.chart_placeholder)
        self.stats_splitter.setSizes([320, 280])
        layout.addWidget(self.stats_splitter)
        self.tabs.addTab(self.stats_tab, "📈 통계/변동")
    
    def _setup_dashboard_tab(self: Any):
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
        self.dashboard_layout.setContentsMargins(12, 12, 12, 12)
        self.dashboard_widget = None
        self.dashboard_placeholder = QLabel("대시보드는 첫 진입 시 로드됩니다.")
        self.dashboard_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dashboard_placeholder.setObjectName("hintLabel")
        self.dashboard_layout.addWidget(self.dashboard_placeholder)
        self.tabs.addTab(self.dashboard_tab, "📊 대시보드")
    
    def _setup_favorites_tab(self: Any):
        self.favorites_tab = self._ensure_favorites_tab()
        self.tabs.addTab(self.favorites_tab, "⭐ 즐겨찾기")
    
    def _setup_guide_tab(self: Any):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                    font-size: 13px;
                    line-height: 1.7;
                    color: inherit;
                    background: transparent;
                    padding: 16px 24px;
                    max-width: 800px;
                }
                h2 {
                    font-size: 18px;
                    font-weight: 800;
                    color: #d97706;
                    border-bottom: 2px solid rgba(217,119,6,0.35);
                    padding-bottom: 8px;
                    margin-top: 24px;
                }
                h3 {
                    font-size: 13px;
                    font-weight: 700;
                    color: #6b7280;
                    margin-top: 18px;
                    margin-bottom: 6px;
                }
                .step {
                    background: rgba(217,119,6,0.07);
                    border: 1px solid rgba(217,119,6,0.25);
                    border-radius: 10px;
                    padding: 14px 16px;
                    margin: 10px 0;
                }
                .step-num {
                    background: #d97706;
                    color: #fff;
                    border-radius: 50%;
                    width: 22px;
                    height: 22px;
                    display: inline-block;
                    text-align: center;
                    font-weight: 800;
                    font-size: 12px;
                    line-height: 22px;
                    margin-right: 10px;
                }
                .step-title { font-weight: 700; margin-bottom: 4px; }
                .step-desc { font-size: 12px; color: #6b7280; }
                code {
                    background: rgba(217,119,6,0.12);
                    color: #b45309;
                    padding: 1px 6px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                .shortcut-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 8px 0;
                }
                .shortcut-table th {
                    background: rgba(217,119,6,0.12);
                    color: #d97706;
                    padding: 7px 12px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 700;
                    border-bottom: 1px solid rgba(217,119,6,0.2);
                }
                .shortcut-table td {
                    padding: 6px 12px;
                    border-bottom: 1px solid rgba(128,128,128,0.1);
                    font-size: 12px;
                }
                kbd {
                    background: rgba(128,128,128,0.12);
                    border: 1px solid rgba(128,128,128,0.3);
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                    font-family: monospace;
                }
                .tip {
                    background: rgba(34,197,94,0.07);
                    border-left: 3px solid #16a34a;
                    padding: 8px 14px;
                    border-radius: 0 6px 6px 0;
                    margin: 8px 0;
                    font-size: 12px;
                    color: #6b7280;
                }
                .warn {
                    background: rgba(217,119,6,0.07);
                    border-left: 3px solid #d97706;
                    padding: 8px 14px;
                    border-radius: 0 6px 6px 0;
                    margin: 8px 0;
                    font-size: 12px;
                    color: #6b7280;
                }
                a { color: #2563eb; text-decoration: none; }
                a:hover { text-decoration: underline; }
                ul { padding-left: 20px; color: #6b7280; }
                li { margin: 4px 0; }
            </style>
        </head>
        <body>

        <h2>🚀 빠른 시작 가이드</h2>

        <div class="step">
            <span class="step-num">1</span>
            <span class="step-title">단지 ID 찾기</span><br>
            <span class="step-desc">
                <a href="https://new.land.naver.com">네이버 부동산</a>에서 아파트를 검색하세요.<br>
                URL에서 <code>/complexes/</code> 뒤의 숫자가 <b>단지 ID</b>입니다.<br>
                예시: <code>new.land.naver.com/complexes/<b>123456</b></code>
            </span>
        </div>

        <div class="step">
            <span class="step-num">2</span>
            <span class="step-title">단지 목록에 추가</span><br>
            <span class="step-desc">
                <b>데이터 수집 탭</b> 좌측 패널에서<br>
                ① 단지 ID를 입력하고 ➕ 버튼을 클릭하세요.<br>
                ② 또는 네이버 URL을 붙여넣어 <b>🔗 URL 버튼</b>을 사용하세요.
            </span>
        </div>

        <div class="step">
            <span class="step-num">3</span>
            <span class="step-title">거래 유형 선택</span><br>
            <span class="step-desc">
                수집할 거래 유형(<b>매매/전세/월세</b>)을 체크하세요.<br>
                가격 필터를 설정하면 해당 범위의 매물만 수집합니다.
            </span>
        </div>

        <div class="step">
            <span class="step-num">4</span>
            <span class="step-title">▶ 크롤링 시작</span><br>
            <span class="step-desc">
                <b>▶ 크롤링 시작</b> 버튼을 클릭하세요.<br>
                수집 완료 후 <b>💾 저장</b> 버튼으로 Excel/CSV로 내보내세요.
            </span>
        </div>

        <div class="warn">
            ⚠️ 속도를 너무 빠르게 설정하면 서버에서 차단될 수 있습니다. '보통' 이상을 권장합니다.
        </div>

        <h2>⌨️ 단축키</h2>
        <table class="shortcut-table">
            <tr><th>기능</th><th>단축키</th></tr>
            <tr><td>크롤링 시작</td><td><kbd>Ctrl</kbd>+<kbd>R</kbd></td></tr>
            <tr><td>크롤링 중지</td><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd></td></tr>
            <tr><td>Excel 저장</td><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td></tr>
            <tr><td>CSV 저장</td><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd></td></tr>
            <tr><td>결과 검색</td><td><kbd>Ctrl</kbd>+<kbd>F</kbd></td></tr>
            <tr><td>설정</td><td><kbd>Ctrl</kbd>+<kbd>,</kbd></td></tr>
            <tr><td>테마 변경</td><td><kbd>Ctrl</kbd>+<kbd>T</kbd></td></tr>
            <tr><td>트레이 최소화</td><td><kbd>Ctrl</kbd>+<kbd>M</kbd></td></tr>
        </table>

        <h2>💡 팁</h2>
        <ul>
            <li>결과 테이블에서 <b>더블클릭</b>하면 해당 매물 페이지로 이동합니다</li>
            <li>좌측 패널 슬라이더로 <b>패널 넓이</b>를 조절할 수 있습니다</li>
            <li>예약 실행에는 먼저 <b>그룹 관리 탭</b>에서 단지 그룹을 생성하세요</li>
            <li><b>데이터베이스 저장</b> 후 재실행하면 신규/변동 매물을 추적할 수 있습니다</li>
            <li>대시보드 탭에서 <b>상승/하락/소멸 매물</b> 통계를 확인할 수 있습니다</li>
        </ul>

        <h2>🗂 탭별 안내</h2>
        <div class="step">
            <span class="step-title">🏠 데이터 수집</span><br>
            <span class="step-desc">단지 ID를 직접 넣어 수집하는 기본 탭입니다. 단지 추가, 거래 유형 선택, 크롤링 시작, 저장 순서로 사용합니다.</span>
        </div>
        <div class="step">
            <span class="step-title">🧭 지도 탐색</span><br>
            <span class="step-desc">위도/경도를 기준으로 주변 단지를 자동 탐색합니다. 단지 ID를 모를 때 지역 단위 탐색에 적합합니다.</span>
        </div>
        <div class="step">
            <span class="step-title">💾 단지 DB / 📁 그룹 관리 / ⭐ 즐겨찾기</span><br>
            <span class="step-desc">DB는 저장 단지 관리, 그룹은 예약용 목록 구성, 즐겨찾기는 자주 보는 매물 재확인 용도입니다.</span>
        </div>
        <div class="step">
            <span class="step-title">⏰ 예약 / 📜 히스토리 / 📈 통계·변동 / 📊 대시보드</span><br>
            <span class="step-desc">예약은 자동 실행, 히스토리는 실행 기록, 통계는 시세 추이, 대시보드는 전체 요약을 보는 화면입니다.</span>
        </div>

        <h2>📂 메뉴 안내</h2>
        <ul>
            <li><b>파일</b>: DB 백업, DB 복원, 설정, 종료</li>
            <li><b>보기</b>: 최근 본 매물 확인, 테마 전환</li>
            <li><b>필터</b>: 현재 필터 저장, 프리셋 불러오기, 고급 결과 필터</li>
            <li><b>알림</b>: 조건 매물 알림 설정</li>
            <li><b>도움말</b>: 단축키와 프로그램 정보</li>
        </ul>

        </body>
        </html>
        """)

        layout.addWidget(browser)
        self.tabs.addTab(tab, "📖 가이드")
    
    def _ensure_chart_widget(self: Any):
        if self.chart_widget is not None:
            return
        from src.ui.widgets.chart import ChartWidget

        self.chart_widget = ChartWidget()
        idx = self.stats_splitter.indexOf(self.chart_placeholder)
        if idx >= 0:
            self.stats_splitter.insertWidget(idx, self.chart_widget)
        else:
            self.stats_splitter.addWidget(self.chart_widget)
        self.chart_placeholder.hide()
        self.chart_placeholder.deleteLater()

    def _ensure_dashboard_widget(self: Any):
        if self.dashboard_widget is not None:
            return
        from src.ui.widgets.dashboard import DashboardWidget

        self.dashboard_widget = DashboardWidget(self.db, theme=self.current_theme)
        if hasattr(self.dashboard_widget, "warning_signal"):
            self.dashboard_widget.warning_signal.connect(self._on_dashboard_warning)
        placeholder = getattr(self, "dashboard_placeholder", None)
        if placeholder is not None:
            placeholder.hide()
            placeholder.deleteLater()
            self.dashboard_placeholder = None
        self.dashboard_layout.addWidget(self.dashboard_widget)
        if self.collected_data:
            self.dashboard_widget.set_data(self.collected_data)

    def _refresh_tab(self: Any):
        index = self.tabs.currentIndex()
        if index == self.TAB_GEO:
            return
        if index == self.TAB_DB:
            self.db_tab.load_data()
        elif index == self.TAB_GROUP:
            self._ensure_group_tab().load_groups()
        elif index == self.TAB_HISTORY:
            self._load_history()
        elif index == self.TAB_STATS:
            try:
                self._load_stats()
            except Exception as e:
                ui_logger.exception(f"통계 탭 로드 실패: {e}")
                self.status_bar.showMessage("⚠️ 통계 탭 로드 중 오류가 발생했습니다.")
        elif index == self.TAB_DASHBOARD:
            self._ensure_dashboard_widget()
            if self.dashboard_widget is not None:
                self.dashboard_widget.refresh()
        elif index == self.TAB_FAVORITES:
            self.favorites_tab.refresh()


