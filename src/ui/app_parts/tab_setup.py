from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppTabSetupMixin:
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
        
        # 1. 수집기 탭
        self.crawler_tab = CrawlerTab(
            self.db,
            history_manager=self.history_manager,
            theme=self.current_theme,
            maintenance_guard=lambda: self._maintenance_mode,
        )
        self.tabs.addTab(self.crawler_tab, "🏠 데이터 수집")

        self.geo_tab = GeoCrawlerTab(
            self.db,
            history_manager=self.history_manager,
            theme=self.current_theme,
            maintenance_guard=lambda: self._maintenance_mode,
        )
        self.tabs.addTab(self.geo_tab, "🧭 지도 탐색")
        
        # 2. 단지 DB 탭
        self.db_tab = DatabaseTab(self.db)
        self.tabs.addTab(self.db_tab, "💾 단지 DB")
        
        # 3. 그룹 관리 탭
        self.group_tab = GroupTab(self.db)
        self.tabs.addTab(self.group_tab, "📁 그룹 관리")
        
        self._setup_schedule_tab()
        self._setup_history_tab()
        self._setup_stats_tab()
        self._setup_dashboard_tab()
        self._setup_favorites_tab()
        self._setup_guide_tab()
        
        self.status_bar = self.statusBar()
        self.crawler_tab.data_collected.connect(self._on_crawl_data_collected)
        self.crawler_tab.status_message.connect(self.status_bar.showMessage)
        self.crawler_tab.alert_triggered.connect(self._on_alert_triggered)
        self.geo_tab.data_collected.connect(self._on_crawl_data_collected)
        self.geo_tab.status_message.connect(self.status_bar.showMessage)
        self.geo_tab.alert_triggered.connect(self._on_alert_triggered)
        self.group_tab.groups_updated.connect(self._load_schedule_groups)
        
        self.tabs.currentChanged.connect(self._refresh_tab)

    
    
    # Obsolete setup methods removed (replaced by modular widgets)
    # _setup_crawler_tab, _setup_db_tab, _setup_groups_tab removed

    
    def _setup_schedule_tab(self: Any):
        self.schedule_tab = QWidget()
        layout = QVBoxLayout(self.schedule_tab)
        sg = QGroupBox("⏰ 예약 크롤링")
        sl = QVBoxLayout()
        self.check_schedule = QCheckBox("예약 실행 활성화")
        sl.addWidget(self.check_schedule)
        tl = QHBoxLayout()
        tl.addWidget(QLabel("실행 시간:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(9, 0))
        tl.addWidget(self.time_edit)
        tl.addStretch()
        sl.addLayout(tl)
        gl = QHBoxLayout()
        gl.addWidget(QLabel("대상 그룹:"))
        self.schedule_group_combo = QComboBox()
        gl.addWidget(self.schedule_group_combo)
        gl.addStretch()
        sl.addLayout(gl)
        sg.setLayout(sl)
        layout.addWidget(sg)
        self.schedule_empty_label = QLabel("예약할 그룹이 없습니다.\n먼저 그룹을 생성하세요.")
        self.schedule_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schedule_empty_label.setStyleSheet("color: #888; padding: 20px;")
        self.schedule_empty_label.hide()
        layout.addWidget(self.schedule_empty_label)
        layout.addStretch()
        self.tabs.addTab(self.schedule_tab, "⏰ 예약 설정")
    
    def _setup_history_tab(self: Any):
        self.history_tab = QWidget()
        layout = QVBoxLayout(self.history_tab)
        bl = QHBoxLayout()
        btn_rf = QPushButton("🔄 새로고침")
        btn_rf.clicked.connect(self._load_history)
        bl.addWidget(btn_rf)
        bl.addStretch()
        layout.addLayout(bl)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["단지명", "단지ID", "거래유형", "수집건수", "수집시각"])
        history_header = self.history_table.horizontalHeader()
        if history_header is not None:
            history_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)
        self.tabs.addTab(self.history_tab, "📜 히스토리")
    
    def _setup_stats_tab(self: Any):
        self.stats_tab = QWidget()
        layout = QVBoxLayout(self.stats_tab)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("단지:"))
        self.stats_complex_combo = QComboBox()
        fl.addWidget(self.stats_complex_combo)
        fl.addWidget(QLabel("유형:"))
        self.stats_type_combo = QComboBox()
        self.stats_type_combo.addItems(["전체", "매매", "전세", "월세"])
        fl.addWidget(self.stats_type_combo)
        
        fl.addWidget(QLabel("면적:"))
        self.stats_pyeong_combo = QComboBox()
        self.stats_pyeong_combo.addItem("전체")
        fl.addWidget(self.stats_pyeong_combo)
        
        btn_load = QPushButton("📊 조회")
        btn_load.clicked.connect(self._load_stats)
        fl.addWidget(btn_load)
        fl.addStretch()
        layout.addLayout(fl)
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
        """v13.0: 분석 대시보드 탭 (lazy load)"""
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
        self.dashboard_placeholder = QLabel("대시보드는 첫 진입 시 로드됩니다.")
        self.dashboard_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dashboard_layout.addWidget(self.dashboard_placeholder)
        self.dashboard_widget = None
        self.tabs.addTab(self.dashboard_tab, "📊 대시보드")
    
    def _setup_favorites_tab(self: Any):
        """v13.0: 즐겨찾기 탭"""
        self.favorites_tab = FavoritesTab(
            self.db, theme=self.current_theme, favorite_toggled=self._on_favorite_toggled
        )
        self.tabs.addTab(self.favorites_tab, "⭐ 즐겨찾기")
    
    def _setup_guide_tab(self: Any):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml("""
        <h2>📖 사용 가이드</h2>
        <h3>🔍 단지 ID 찾는 방법</h3>
        <ol>
            <li>네이버 부동산 (<a href="https://new.land.naver.com">new.land.naver.com</a>) 접속</li>
            <li>원하는 아파트 단지 검색</li>
            <li>URL에서 <code>/complexes/</code> 뒤의 숫자가 단지 ID입니다</li>
            <li>예: <code>https://new.land.naver.com/complexes/<b>12345</b></code> → ID: 12345</li>
        </ol>
        <h3>⌨️ 단축키</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse;">
            <tr><th>기능</th><th>단축키</th></tr>
            <tr><td>🚀 크롤링 시작</td><td>Ctrl+R</td></tr>
            <tr><td>⏹️ 크롤링 중지</td><td>Ctrl+Shift+R</td></tr>
            <tr><td>💾 Excel 저장</td><td>Ctrl+S</td></tr>
            <tr><td>📄 CSV 저장</td><td>Ctrl+Shift+S</td></tr>
            <tr><td>🔍 검색</td><td>Ctrl+F</td></tr>
            <tr><td>⚙️ 설정</td><td>Ctrl+,</td></tr>
            <tr><td>🎨 테마 변경</td><td>Ctrl+T</td></tr>
            <tr><td>📥 트레이 최소화</td><td>Ctrl+M</td></tr>
        </table>
        <h3>💡 팁</h3>
        <ul>
            <li>🖱️ 결과 테이블에서 <b>더블클릭</b>하면 해당 매물 페이지로 이동합니다</li>
            <li>📊 요약 카드에서 실시간 수집 현황을 확인할 수 있습니다</li>
            <li>⏱️ 예상 남은 시간을 참고하여 작업 시간을 예측하세요</li>
            <li>🔔 알림 설정을 통해 원하는 조건의 매물을 알림받을 수 있습니다</li>
        </ul>
        """)
        layout.addWidget(browser)
        self.tabs.addTab(tab, "📖 가이드")
    
    def _ensure_chart_widget(self: Any):
        if self.chart_widget is not None:
            return
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
        self.dashboard_widget = DashboardWidget(self.db, theme=self.current_theme)
        if hasattr(self.dashboard_widget, "warning_signal"):
            self.dashboard_widget.warning_signal.connect(self._on_dashboard_warning)
        self.dashboard_layout.addWidget(self.dashboard_widget)
        self.dashboard_placeholder.hide()
        self.dashboard_placeholder.deleteLater()
        if self.collected_data:
            self.dashboard_widget.set_data(self.collected_data)

    def _refresh_tab(self: Any):
        current = self.tabs.currentWidget()
        if current is self.db_tab:
            self.db_tab.load_data()
        elif current is self.geo_tab:
            return
        elif current is self.group_tab:
            self.group_tab.load_groups()
        elif current is self.history_tab:
            self._noncritical_loaded["history"] = True
            self._load_history()
        elif current is self.stats_tab:
            try:
                if not self._noncritical_loaded["stats"]:
                    self._load_stats_complexes()
                    self._noncritical_loaded["stats"] = True
                self._load_stats()
            except Exception as e:
                ui_logger.exception(f"통계 탭 로드 실패: {e}")
                self.status_bar.showMessage("⚠️ 통계 탭 로드 중 오류가 발생했습니다.")
        elif current is self.dashboard_tab:
            self._ensure_dashboard_widget()
            self.dashboard_widget.refresh()
        elif current is self.favorites_tab:
            if not self._noncritical_loaded["favorites"]:
                self._refresh_favorite_keys()
                self._noncritical_loaded["favorites"] = True
            self.favorites_tab.refresh()


