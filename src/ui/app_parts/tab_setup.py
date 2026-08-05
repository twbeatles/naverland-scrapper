from __future__ import annotations

from typing import Any, TYPE_CHECKING

from qfluentwidgets import NavigationInterface

from src.ui.fluent.navigation import (
    ROUTE_CRAWLER,
    ROUTE_DASHBOARD,
    ROUTE_DB,
    ROUTE_FAVORITES,
    ROUTE_GEO,
    ROUTE_GROUP,
    ROUTE_GUIDE,
    ROUTE_HISTORY,
    ROUTE_SCHEDULE,
    ROUTE_STATS,
    prepare_page,
    register_navigation,
    sync_nav_selection,
)
from src.ui.fluent.tab_bridge import TabCompatBridge
from src.utils.ui_labels import (
    TAB_CRAWLER,
    TAB_DASHBOARD,
    TAB_DB,
    TAB_FAVORITES,
    TAB_GEO,
    TAB_GROUP,
    TAB_GUIDE,
    TAB_HISTORY,
    TAB_SCHEDULE,
    TAB_STATS,
)

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppTabSetupMixin:
    # Stable page indices (tests + legacy mixins). Order must match addTab sequence.
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
        root = QHBoxLayout(main_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.navigationInterface = NavigationInterface(
            self, showMenuButton=True, showReturnButton=False
        )
        try:
            self.navigationInterface.setExpandWidth(208)
        except Exception:
            pass

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 4)
        content_layout.setSpacing(4)

        self.stackedWidget = QStackedWidget(content)
        content_layout.addWidget(self.stackedWidget, 1)

        def _on_switch(widget):
            sync_nav_selection(self.navigationInterface, widget)

        self.tabs = TabCompatBridge(
            self.stackedWidget, on_switch=_on_switch, parent=self
        )
        self.status_bar = self.statusBar()

        self.crawler_tab = prepare_page(self._create_crawler_tab(), ROUTE_CRAWLER)
        self.tabs.addTab(self.crawler_tab, TAB_CRAWLER)

        self.geo_tab = prepare_page(self._create_geo_tab(), ROUTE_GEO)
        self.tabs.addTab(self.geo_tab, TAB_GEO)

        self.db_tab = prepare_page(self._create_db_tab(), ROUTE_DB)
        self.tabs.addTab(self.db_tab, TAB_DB)

        self.group_tab = prepare_page(self._create_group_tab(), ROUTE_GROUP)
        self.tabs.addTab(self.group_tab, TAB_GROUP)

        self._setup_schedule_tab()
        self._setup_history_tab()
        self._setup_stats_tab()
        self._setup_dashboard_tab()
        self._setup_favorites_tab()
        self._setup_guide_tab()

        pages = {
            ROUTE_CRAWLER: self.crawler_tab,
            ROUTE_GEO: self.geo_tab,
            ROUTE_DB: self.db_tab,
            ROUTE_GROUP: self.group_tab,
            ROUTE_SCHEDULE: self.schedule_tab,
            ROUTE_HISTORY: self.history_tab,
            ROUTE_STATS: self.stats_tab,
            ROUTE_DASHBOARD: self.dashboard_tab,
            ROUTE_FAVORITES: self.favorites_tab,
            ROUTE_GUIDE: self.guide_tab,
        }
        register_navigation(
            self.navigationInterface,
            pages=pages,
            on_select=self.tabs.setCurrentWidget,
            on_settings=getattr(self, "_show_settings", None),
        )

        root.addWidget(self.navigationInterface)
        root.addWidget(content, 1)

        self.tabs.currentChanged.connect(self._refresh_tab)
        self.tabs.setCurrentWidget(self.crawler_tab)

    # Obsolete setup methods removed (replaced by modular widgets)
    # _setup_crawler_tab, _setup_db_tab, _setup_groups_tab removed

    def _create_crawler_tab(self: Any):
        from src.ui.widgets.crawler_tab import CrawlerTab

        tab = CrawlerTab(
            self.db,
            history_manager=self.history_manager,
            theme=self.current_theme,
            maintenance_guard=lambda: self._maintenance_mode,
            article_open_handler=self._open_article_and_track,
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
            article_open_handler=self._open_article_and_track,
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

            tab = FavoritesTab(
                self.db,
                theme=self.current_theme,
                favorite_toggled=self._on_favorite_toggled,
                article_open_handler=self._open_article_and_track,
            )
            self.favorites_tab = tab
        return tab

    
    def _setup_schedule_tab(self: Any):
        self.schedule_tab = QWidget()
        layout = QVBoxLayout(self.schedule_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        sg = QGroupBox("예약 수집")
        sl = QVBoxLayout()
        sl.setSpacing(10)

        self.check_schedule = QCheckBox("예약 실행 켜기")
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

        self.schedule_empty_label = QLabel(
            "예약할 묶음이 없습니다.\n좌측 네비 「단지 묶음」에서 먼저 만들어 주세요."
        )
        self.schedule_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schedule_empty_label.setStyleSheet("color: #888; padding: 20px; font-size: 13px;")
        self.schedule_empty_label.hide()
        layout.addWidget(self.schedule_empty_label)
        layout.addStretch()
        prepare_page(self.schedule_tab, ROUTE_SCHEDULE)
        self.tabs.addTab(self.schedule_tab, TAB_SCHEDULE)

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
        btn_rf = QPushButton("새로고침")
        btn_rf.setObjectName("secondaryBtn")
        btn_rf.setToolTip("수집 이력을 다시 불러옵니다.")
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

        self.history_empty_label = QLabel(
            "수집 기록이 없습니다.\n「매물 수집」에서 수집을 실행해 보세요."
        )
        self.history_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_empty_label.setStyleSheet("color: #888; font-size: 13px; padding: 40px;")
        layout.addWidget(self.history_empty_label)
        self.history_empty_label.hide()

        prepare_page(self.history_tab, ROUTE_HISTORY)
        self.tabs.addTab(self.history_tab, TAB_HISTORY)
    
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
        btn_load = QPushButton("조회")
        btn_load.setObjectName("primaryBtn")
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
        prepare_page(self.stats_tab, ROUTE_STATS)
        self.tabs.addTab(self.stats_tab, TAB_STATS)
    
    def _setup_dashboard_tab(self: Any):
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
        self.dashboard_layout.setContentsMargins(12, 12, 12, 12)
        self.dashboard_widget = None
        self.dashboard_placeholder = QLabel("대시보드는 첫 진입 시 로드됩니다.")
        self.dashboard_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dashboard_placeholder.setObjectName("hintLabel")
        self.dashboard_layout.addWidget(self.dashboard_placeholder)
        prepare_page(self.dashboard_tab, ROUTE_DASHBOARD)
        self.tabs.addTab(self.dashboard_tab, TAB_DASHBOARD)
    
    def _setup_favorites_tab(self: Any):
        self.favorites_tab = prepare_page(self._ensure_favorites_tab(), ROUTE_FAVORITES)
        self.tabs.addTab(self.favorites_tab, TAB_FAVORITES)
    
    def _setup_guide_tab(self: Any):
        from src.ui.guide_content import build_guide_html

        tab = QWidget()
        self.guide_tab = tab
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        browser = QTextBrowser()
        browser.setObjectName("guideBrowser")
        browser.setOpenExternalLinks(True)
        self.guide_browser = browser
        theme = str(getattr(self, "current_theme", "dark") or "dark")
        browser.setHtml(build_guide_html(theme))
        layout.addWidget(browser)
        prepare_page(tab, ROUTE_GUIDE)
        self.tabs.addTab(tab, TAB_GUIDE)

    def _refresh_guide_theme(self: Any, theme: str | None = None):
        """Re-render guide HTML for dark/light so text stays readable."""
        browser = getattr(self, "guide_browser", None)
        if browser is None:
            return
        try:
            from src.ui.guide_content import build_guide_html

            theme_name = str(theme or getattr(self, "current_theme", "dark") or "dark")
            browser.setHtml(build_guide_html(theme_name))
        except Exception:
            pass
    
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

    def _refresh_tab(self: Any, index=None):
        force = index is None
        if index is None:
            index = self.tabs.currentIndex()
        if index == self.TAB_GEO:
            return
        if index == self.TAB_DB:
            self.db_tab.load_data()
        elif index == self.TAB_GROUP:
            self._ensure_group_tab().load_groups()
        elif index == self.TAB_HISTORY:
            if not force and self._noncritical_loaded.get("history", False):
                return
            self._load_history()
            self._mark_noncritical_loaded("history")
        elif index == self.TAB_STATS:
            if not force and self._noncritical_loaded.get("stats", False):
                return
            try:
                self._load_stats_complexes()
                self._load_stats()
                self._mark_noncritical_loaded("stats")
            except Exception as e:
                ui_logger.exception(f"통계 탭 로드 실패: {e}")
                self.status_bar.showMessage("⚠️ 통계 탭 로드 중 오류가 발생했습니다.")
        elif index == self.TAB_DASHBOARD:
            if not force and self._noncritical_loaded.get("dashboard", False):
                return
            self._ensure_dashboard_widget()
            if self.dashboard_widget is not None:
                self.dashboard_widget.set_data(self.collected_data)
                self._mark_noncritical_loaded("dashboard")
        elif index == self.TAB_FAVORITES:
            if not force and self._noncritical_loaded.get("favorites", False):
                return
            self.favorites_tab.refresh()
            self._mark_noncritical_loaded("favorites")


