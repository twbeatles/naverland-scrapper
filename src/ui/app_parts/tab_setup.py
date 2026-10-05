from __future__ import annotations

import time

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


def _secondary_label_qss(theme_name) -> str:
    from src.ui.fluent.design_tokens import secondary_label_qss
    return secondary_label_qss(theme_name)


def _empty_state_qss(theme_name, padding: int = 20) -> str:
    from src.ui.fluent.design_tokens import empty_state_qss
    return empty_state_qss(theme_name, padding=padding)


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
            from src.ui.fluent.design_tokens import NAV_EXPAND_WIDTH as _NAV_W
            self.navigationInterface.setExpandWidth(_NAV_W)
        except Exception:
            pass

        content = QWidget()
        content_layout = QVBoxLayout(content)
        from src.ui.fluent.design_tokens import GROUP_GAP as _GG, PAGE_MARGIN as _PM
        content_layout.setContentsMargins(_PM, _GG, _PM, _GG)
        from src.ui.fluent.design_tokens import GROUP_GAP as _GG2
        content_layout.setSpacing(_GG2)

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

        # Panel starts COMPACT (48px icons); expand for labeled nav after the
        # window is shown so item animations/opacity settle (srtgo parity).
        try:
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(
                0, lambda: self.navigationInterface.expand(useAni=False)
            )
        except Exception:
            pass
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
            region_open_handler=self._open_geo_region,
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
        from src.ui.fluent.design_tokens import GROUP_GAP as _GG, SPACE_SM as _SM, SPACE_XS as _XS
        from src.ui.widgets.components import build_page_header
        from src.utils.ui_labels import SCHEDULE_MODE_LABELS

        self.schedule_tab = QWidget()
        layout = QVBoxLayout(self.schedule_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SM)
        layout.addWidget(
            build_page_header(
                "예약 수집",
                "매일 정한 시간에 자동으로 수집합니다. 앱이 켜져 있어야 하며, 창을 닫아 트레이에 두어도 됩니다.",
            )
        )

        def _label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("fieldLabel")
            return lbl

        sg = QGroupBox("자동 수집 설정")
        form = QGridLayout()
        form.setHorizontalSpacing(_SM)
        form.setVerticalSpacing(_SM)
        form.setColumnStretch(2, 1)

        self.check_schedule = QCheckBox("매일 자동으로 수집하기")
        self.check_schedule.setToolTip("켜 두면 아래에 정한 시간마다 자동으로 수집을 시작합니다.")
        form.addWidget(self.check_schedule, 0, 0, 1, 3)

        form.addWidget(_label("시작 시간"), 1, 0)
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(9, 0))
        self.time_edit.setMinimumWidth(140)
        self.time_edit.setToolTip("매일 이 시간에 수집을 시작합니다.")
        form.addWidget(self.time_edit, 1, 1)

        form.addWidget(_label("수집 방법"), 2, 0)
        self.schedule_mode_combo = QComboBox()
        self.schedule_mode_combo.addItem(SCHEDULE_MODE_LABELS["complex"], "complex")
        self.schedule_mode_combo.addItem(SCHEDULE_MODE_LABELS["geo_sweep"], "geo_sweep")
        self.schedule_mode_combo.setMinimumWidth(200)
        self.schedule_mode_combo.setToolTip(
            "단지 묶음 수집: 미리 묶어 둔 단지들을 수집합니다.\n"
            "지도 범위 수집: 정한 위치 주변을 지도로 훑어 수집합니다."
        )
        form.addWidget(self.schedule_mode_combo, 2, 1)
        sg.setLayout(form)

        self.schedule_group_widget = QWidget()
        gl = QHBoxLayout(self.schedule_group_widget)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(_SM)
        gl.addWidget(_label("수집할 묶음"))
        self.schedule_group_combo = QComboBox()
        self.schedule_group_combo.setMinimumWidth(200)
        self.schedule_group_combo.setToolTip("예약 시간에 수집할 단지 묶음을 고릅니다.")
        gl.addWidget(self.schedule_group_combo)
        gl.addStretch(1)
        form.addWidget(self.schedule_group_widget, 3, 0, 1, 3)

        self.schedule_geo_widget = QWidget()
        geo_layout = QGridLayout(self.schedule_geo_widget)
        geo_layout.setContentsMargins(0, 0, 0, 0)
        geo_layout.setHorizontalSpacing(_SM)
        geo_layout.setVerticalSpacing(_XS)
        geo_layout.setColumnStretch(4, 1)

        self.btn_schedule_geo_copy = QPushButton("「지도로 찾기」에서 정한 위치 가져오기")
        self.btn_schedule_geo_copy.setObjectName("secondaryBtn")
        self.btn_schedule_geo_copy.setToolTip(
            "「지도로 찾기」 화면에서 지역을 고른 뒤 누르면 그 위치와 범위를 그대로 가져옵니다."
        )
        self.btn_schedule_geo_copy.clicked.connect(self._copy_geo_tab_to_schedule)
        geo_layout.addWidget(self.btn_schedule_geo_copy, 0, 0, 1, 4)

        geo_layout.addWidget(_label("위도"), 1, 0)
        self.schedule_geo_lat = QDoubleSpinBox()
        self.schedule_geo_lat.setRange(33.0, 39.5)
        self.schedule_geo_lat.setDecimals(6)
        self.schedule_geo_lat.setValue(37.5608)
        geo_layout.addWidget(self.schedule_geo_lat, 1, 1)
        geo_layout.addWidget(_label("경도"), 1, 2)
        self.schedule_geo_lon = QDoubleSpinBox()
        self.schedule_geo_lon.setRange(124.0, 132.1)
        self.schedule_geo_lon.setDecimals(6)
        self.schedule_geo_lon.setValue(126.9888)
        geo_layout.addWidget(self.schedule_geo_lon, 1, 3)

        geo_layout.addWidget(_label("주변까지 넓히기"), 2, 0)
        self.schedule_geo_rings = QSpinBox()
        self.schedule_geo_rings.setRange(0, 6)
        self.schedule_geo_rings.setValue(1)
        self.schedule_geo_rings.setSuffix(" 단계")
        self.schedule_geo_rings.setToolTip("0단계는 정한 위치만, 숫자가 클수록 주변을 더 넓게 훑습니다.")
        geo_layout.addWidget(self.schedule_geo_rings, 2, 1)
        geo_layout.addWidget(_label("지도 확대 단계"), 2, 2)
        self.schedule_geo_zoom = QSpinBox()
        self.schedule_geo_zoom.setRange(12, 18)
        self.schedule_geo_zoom.setValue(15)
        geo_layout.addWidget(self.schedule_geo_zoom, 2, 3)

        geo_layout.addWidget(_label("지도 이동 간격"), 3, 0)
        self.schedule_geo_step = QSpinBox()
        self.schedule_geo_step.setRange(120, 1600)
        self.schedule_geo_step.setSingleStep(40)
        self.schedule_geo_step.setValue(480)
        self.schedule_geo_step.setToolTip("기본값을 권장합니다.")
        geo_layout.addWidget(self.schedule_geo_step, 3, 1)
        geo_layout.addWidget(_label("옮길 때마다 대기"), 3, 2)
        self.schedule_geo_dwell = QSpinBox()
        self.schedule_geo_dwell.setRange(100, 5000)
        self.schedule_geo_dwell.setSingleStep(100)
        self.schedule_geo_dwell.setValue(600)
        self.schedule_geo_dwell.setSuffix(" ms")
        self.schedule_geo_dwell.setToolTip("기본값을 권장합니다. (1000ms = 1초)")
        geo_layout.addWidget(self.schedule_geo_dwell, 3, 3)

        geo_layout.addWidget(_label("주택 종류"), 4, 0)
        asset_row = QHBoxLayout()
        self.schedule_geo_asset_apt = QCheckBox("아파트")
        self.schedule_geo_asset_vl = QCheckBox("빌라·연립")
        self.schedule_geo_asset_apt.setChecked(True)
        self.schedule_geo_asset_vl.setChecked(True)
        asset_row.addWidget(self.schedule_geo_asset_apt)
        asset_row.addWidget(self.schedule_geo_asset_vl)
        asset_row.addStretch()
        geo_layout.addLayout(asset_row, 4, 1, 1, 3)
        form.addWidget(self.schedule_geo_widget, 4, 0, 1, 3)

        layout.addWidget(sg)

        self.schedule_empty_label = QLabel(
            "아직 단지 묶음이 없어 예약할 수 없습니다.\n"
            "왼쪽 메뉴 「단지 묶음」에서 자주 보는 단지를 먼저 묶어 주세요."
        )
        self.schedule_empty_label.setObjectName("listPlaceholder")
        self.schedule_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

    def _copy_geo_tab_to_schedule(self: Any):
        """「지도로 찾기」에서 정한 위치·범위를 예약 설정으로 한 번에 옮긴다."""
        geo_tab = getattr(self, "geo_tab", None)
        if geo_tab is None:
            return
        previous_hydrating = bool(getattr(self, "_schedule_hydrating", False))
        self._schedule_hydrating = True
        try:
            self.schedule_geo_lat.setValue(float(geo_tab.spin_lat.value()))
            self.schedule_geo_lon.setValue(float(geo_tab.spin_lon.value()))
            self.schedule_geo_zoom.setValue(int(geo_tab.spin_zoom.value()))
            self.schedule_geo_rings.setValue(int(geo_tab.spin_rings.value()))
            self.schedule_geo_step.setValue(int(geo_tab.spin_step.value()))
            self.schedule_geo_dwell.setValue(int(geo_tab.spin_dwell.value()))
            apt = bool(geo_tab.check_asset_apt.isChecked())
            vl = bool(geo_tab.check_asset_vl.isChecked())
            if apt or vl:
                self.schedule_geo_asset_apt.setChecked(apt)
                self.schedule_geo_asset_vl.setChecked(vl)
        finally:
            self._schedule_hydrating = previous_hydrating
        self._save_schedule_config()
        place = str(getattr(geo_tab, "_geo_place_name", "") or "").strip()
        self.show_toast(
            f"'{place}' 위치를 예약 설정으로 가져왔습니다." if place else "지도 위치를 예약 설정으로 가져왔습니다.",
            toast_type="success",
        )

    def _setup_history_tab(self: Any):
        from src.ui.fluent.design_tokens import SPACE_SM as _SM
        from src.ui.widgets.components import EmptyStateWidget, build_page_header, install_token_labels
        from src.utils.ui_labels import asset_label, crawl_mode_label, history_status_label

        self.history_tab = QWidget()
        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SM)

        bl = QHBoxLayout()
        bl.addWidget(build_page_header("수집 기록", "언제 어떤 단지를 수집했고 매물이 몇 건이었는지 보여 줍니다."), 1)
        btn_rf = QPushButton("새로고침")
        btn_rf.setObjectName("secondaryBtn")
        btn_rf.setToolTip("수집 기록을 다시 불러옵니다. (F5)")
        btn_rf.clicked.connect(self._load_history)
        bl.addWidget(btn_rf, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(bl)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels(
            ["단지 이름", "단지 번호", "종류", "엔진", "수집 방식", "결과", "거래 종류", "매물 수", "수집 시각"]
        )
        history_header = self.history_table.horizontalHeader()
        if history_header is not None:
            history_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # 내부 값(APT, complex, success …)은 그대로 두고 화면에만 쉬운 말로 보여 준다.
        install_token_labels(self.history_table, 2, asset_label)
        install_token_labels(self.history_table, 4, crawl_mode_label)
        install_token_labels(self.history_table, 5, history_status_label)
        self.history_table.setColumnHidden(3, True)  # 엔진은 문제 진단용이라 숨긴다
        layout.addWidget(self.history_table, 1)

        self.history_empty_label = EmptyStateWidget(
            icon="HISTORY",
            title="아직 수집 기록이 없습니다",
            description="「매물 수집」이나 「지도로 찾기」에서 수집하면 여기에 기록이 쌓입니다.",
        )
        layout.addWidget(self.history_empty_label, 1)
        self.history_empty_label.hide()
        history_model = self.history_table.model()
        if history_model is not None:
            history_model.rowsInserted.connect(lambda *_: self._update_history_empty_state())
            history_model.rowsRemoved.connect(lambda *_: self._update_history_empty_state())
            history_model.modelReset.connect(lambda *_: self._update_history_empty_state())
        self._update_history_empty_state()

        prepare_page(self.history_tab, ROUTE_HISTORY)
        self.tabs.addTab(self.history_tab, TAB_HISTORY)

    def _update_history_empty_state(self: Any):
        table = getattr(self, "history_table", None)
        empty = getattr(self, "history_empty_label", None)
        if table is None or empty is None:
            return
        has_rows = int(table.rowCount() or 0) > 0
        empty.setVisible(not has_rows)
        table.setVisible(has_rows)

    def _setup_stats_tab(self: Any):
        from src.ui.fluent.design_tokens import SPACE_SM as _SM, SPACE_XS as _XS
        from src.ui.widgets.components import build_page_header

        self.stats_tab = QWidget()
        layout = QVBoxLayout(self.stats_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SM)
        layout.addWidget(
            build_page_header(
                "가격 통계",
                "수집할 때마다 쌓인 기록으로 단지별 최저·최고·평균 가격의 흐름을 봅니다.",
            )
        )

        def _label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("fieldLabel")
            return lbl

        fl = QHBoxLayout()
        fl.setSpacing(_XS)
        fl.addWidget(_label("단지"))
        self.stats_complex_combo = QComboBox()
        self.stats_complex_combo.setMinimumWidth(220)
        self.stats_complex_combo.setToolTip("가격 흐름을 볼 단지를 고릅니다.")
        fl.addWidget(self.stats_complex_combo)
        fl.addSpacing(_XS)
        fl.addWidget(_label("거래 종류"))
        self.stats_type_combo = QComboBox()
        self.stats_type_combo.addItems(["전체", "매매", "전세", "월세"])
        fl.addWidget(self.stats_type_combo)
        self.stats_metric_label = _label("기준")
        fl.addWidget(self.stats_metric_label)
        self.stats_metric_combo = QComboBox()
        self.stats_metric_combo.addItem("월세 금액", "rent")
        self.stats_metric_combo.addItem("보증금", "deposit")
        self.stats_metric_combo.setToolTip("월세는 매달 내는 금액과 보증금 중 무엇을 기준으로 볼지 고릅니다.")
        fl.addWidget(self.stats_metric_combo)
        self.stats_type_combo.currentIndexChanged.connect(self._on_stats_type_changed)
        self.stats_metric_combo.currentIndexChanged.connect(self._load_stats)
        fl.addSpacing(_XS)
        fl.addWidget(_label("면적"))
        self.stats_pyeong_combo = QComboBox()
        self.stats_pyeong_combo.addItem("전체")
        fl.addWidget(self.stats_pyeong_combo)
        btn_load = QPushButton("보기")
        btn_load.setObjectName("primaryBtn")
        btn_load.setToolTip("고른 조건으로 가격 기록을 불러옵니다.")
        btn_load.clicked.connect(self._load_stats)
        fl.addWidget(btn_load)
        fl.addStretch()
        layout.addLayout(fl)
        self.stats_metric_label.hide()
        self.stats_metric_combo.hide()

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["날짜", "거래 종류", "평형", "최저가", "최고가", "평균가"])
        stats_header = self.stats_table.horizontalHeader()
        if stats_header is not None:
            stats_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # v10.0: Chart Integration
        self.stats_splitter = QSplitter(Qt.Orientation.Vertical)
        self.stats_splitter.addWidget(self.stats_table)
        self.chart_widget = None
        self.chart_placeholder = QLabel(
            "단지를 고르고 「보기」를 누르면 가격 흐름 그래프가 여기에 나타납니다.\n"
            "같은 단지를 여러 날 수집할수록 흐름이 또렷해집니다."
        )
        self.chart_placeholder.setObjectName("listPlaceholder")
        self.chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_splitter.addWidget(self.chart_placeholder)
        self.stats_splitter.setSizes([320, 280])
        layout.addWidget(self.stats_splitter, 1)
        prepare_page(self.stats_tab, ROUTE_STATS)
        self.tabs.addTab(self.stats_tab, TAB_STATS)

    def _setup_dashboard_tab(self: Any):
        self.dashboard_tab = QWidget()
        self.dashboard_layout = QVBoxLayout(self.dashboard_tab)
        self.dashboard_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_widget = None
        self.dashboard_placeholder = QLabel("요약 화면을 준비하고 있습니다…")
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
        from src.ui.fluent.design_tokens import SPACE_SM as _SM
        from src.ui.widgets.components import build_page_header

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SM)
        layout.addWidget(build_page_header("가이드", "처음 쓰는 분을 위한 사용 방법과 화면 안내입니다."))
        browser = QTextBrowser()
        browser.setObjectName("guideBrowser")
        browser.setFrameShape(QFrame.Shape.NoFrame)
        guide_doc = browser.document()
        if guide_doc is not None:
            guide_doc.setDocumentMargin(0)
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
        # ISSUE-018: currentChanged 연발 시 동기 DB 조회를 때리지 않도록
        # 0.5s 디바운스. 명시적 새로고침(force)은 항상 통과.
        if not force:
            try:
                _last_map = getattr(self, "_last_tab_refresh_at", None)
                if not isinstance(_last_map, dict):
                    _last_map = {}
                    self._last_tab_refresh_at = _last_map
                _now = time.monotonic()
                if _now - float(_last_map.get(index, 0.0)) < 0.5:
                    return
                _last_map[index] = _now
            except Exception:
                pass
        if index == self.TAB_GEO:
            return
        if index == self.TAB_DB:
            self.db_tab.load_data()
        elif index == self.TAB_GROUP:
            try:
                self._ensure_group_tab().load_groups()
            except Exception as e:
                ui_logger.exception(f"그룹 탭 로드 실패: {e}")
                self.status_bar.showMessage("단지 묶음을 불러오지 못했습니다.")
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
                self.status_bar.showMessage("가격 통계를 불러오지 못했습니다.")
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


