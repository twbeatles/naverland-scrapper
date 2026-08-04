from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.managers import settings
from src.utils.constants import CRAWL_SPEED_PRESETS, SHORTCUTS
from src.utils.result_columns import RESULT_EXTRA_COLUMN_DEFS
from src.utils.ui_labels import (
    SETTINGS_TAB_COLLECT,
    SETTINGS_TAB_DISPLAY,
    SETTINGS_TAB_GENERAL,
    SETTINGS_TAB_GEO,
    SETTINGS_TAB_PERF,
)


def _scroll_wrap(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(widget)
    return area


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extra_column_checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        self.setWindowTitle("설정")
        self.setMinimumSize(560, 480)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(_scroll_wrap(self._build_general_tab()), SETTINGS_TAB_GENERAL)
        tabs.addTab(_scroll_wrap(self._build_collect_tab()), SETTINGS_TAB_COLLECT)
        tabs.addTab(_scroll_wrap(self._build_perf_tab()), SETTINGS_TAB_PERF)
        tabs.addTab(_scroll_wrap(self._build_geo_tab()), SETTINGS_TAB_GEO)
        tabs.addTab(_scroll_wrap(self._build_display_tab()), SETTINGS_TAB_DISPLAY)
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        theme_group = QGroupBox("화면 테마")
        theme_layout = QHBoxLayout()
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("어두운 테마", "dark")
        self.combo_theme.addItem("밝은 테마", "light")
        theme_layout.addWidget(QLabel("테마:"))
        theme_layout.addWidget(self.combo_theme)
        theme_layout.addStretch()
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        system_group = QGroupBox("앱 동작")
        system_layout = QVBoxLayout()
        self.check_tray = QCheckBox("창을 닫을 때 트레이로 최소화")
        self.check_notify = QCheckBox("알림 메시지 표시")
        self.check_confirm = QCheckBox("종료 전 확인 창 띄우기")
        self.check_sound = QCheckBox("수집 완료 시 알림음")
        system_layout.addWidget(self.check_tray)
        system_layout.addWidget(self.check_notify)
        system_layout.addWidget(self.check_confirm)
        system_layout.addWidget(self.check_sound)
        system_group.setLayout(system_layout)
        layout.addWidget(system_group)
        layout.addStretch()
        return page

    def _build_collect_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        crawl_group = QGroupBox("기본 수집 방식")
        crawl_layout = QGridLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        crawl_layout.addWidget(QLabel("수집 속도:"), 0, 0)
        crawl_layout.addWidget(self.combo_speed, 0, 1)

        crawl_layout.addWidget(QLabel("수집 엔진:"), 1, 0)
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Playwright (권장)", "playwright")
        self.combo_engine.addItem("Selenium (보조)", "selenium")
        crawl_layout.addWidget(self.combo_engine, 1, 1)

        self.check_retry_on_error = QCheckBox("실패 시 자동으로 다시 시도")
        self.check_retry_on_error.toggled.connect(
            lambda checked: self.spin_max_retry_count.setEnabled(bool(checked))
        )
        crawl_layout.addWidget(self.check_retry_on_error, 2, 0, 1, 2)

        crawl_layout.addWidget(QLabel("다시 시도 횟수:"), 3, 0)
        self.spin_max_retry_count = QSpinBox()
        self.spin_max_retry_count.setRange(0, 10)
        crawl_layout.addWidget(self.spin_max_retry_count, 3, 1)

        self.check_fallback_engine = QCheckBox("Playwright 실패 시 Selenium으로 이어 수집")
        crawl_layout.addWidget(self.check_fallback_engine, 4, 0, 1, 2)
        crawl_group.setLayout(crawl_layout)
        layout.addWidget(crawl_group)

        naver_group = QGroupBox("매물 정보 범위 (가벼운 기본값)")
        naver_layout = QGridLayout()
        self.check_include_pre = QCheckBox("분양권 매물도 함께 수집")
        self.check_include_pre.setToolTip(
            "켜면 분양권 매물까지 목록에 포함됩니다. 건수가 늘어날 수 있어 기본은 꺼져 있습니다."
        )
        naver_layout.addWidget(self.check_include_pre, 0, 0, 1, 2)

        self.check_detail_enrichment = QCheckBox("중개사·기전세 등 상세 정보 가져오기")
        self.check_detail_enrichment.setToolTip(
            "조건에 맞는 매물만 상세 정보를 추가로 조회합니다. 끄면 훨씬 빠르게 끝납니다."
        )
        naver_layout.addWidget(self.check_detail_enrichment, 1, 0, 1, 2)

        self.check_detail_front_api = QCheckBox("상세 정보 보완 조회 사용")
        self.check_detail_front_api.setToolTip(
            "상세 페이지가 비어 있어도 중개 정보를 보충합니다. 네트워크 요청이 조금 늘어납니다."
        )
        naver_layout.addWidget(self.check_detail_front_api, 2, 0, 1, 2)

        naver_layout.addWidget(QLabel("단지마다 상세 조회 한도:"), 3, 0)
        self.spin_detail_max = QSpinBox()
        self.spin_detail_max.setRange(0, 500)
        self.spin_detail_max.setSpecialValueText("제한 없음")
        self.spin_detail_max.setToolTip("0=제한 없음. 매물이 많은 단지에서 상세 조회를 줄일 때 사용합니다.")
        naver_layout.addWidget(self.spin_detail_max, 3, 1)

        naver_layout.addWidget(QLabel("목록 페이지 사이 대기(ms):"), 4, 0)
        self.spin_article_page_delay = QSpinBox()
        self.spin_article_page_delay.setRange(0, 2000)
        self.spin_article_page_delay.setSingleStep(50)
        self.spin_article_page_delay.setToolTip(
            "연속 요청이 막히지 않도록 페이지 사이에 잠깐 쉽니다. 0이면 대기하지 않습니다."
        )
        naver_layout.addWidget(self.spin_article_page_delay, 4, 1)
        naver_group.setLayout(naver_layout)
        layout.addWidget(naver_group)
        layout.addStretch()
        return page

    def _build_perf_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        perf_group = QGroupBox("속도와 안정성")
        perf_layout = QGridLayout()
        perf_layout.addWidget(QLabel("가격 이력 일괄 저장 크기:"), 0, 0)
        self.spin_history_batch = QSpinBox()
        self.spin_history_batch.setRange(20, 5000)
        self.spin_history_batch.setSingleStep(20)
        perf_layout.addWidget(self.spin_history_batch, 0, 1)

        perf_layout.addWidget(QLabel("결과 검색 반응 지연(ms):"), 1, 0)
        self.spin_filter_debounce = QSpinBox()
        self.spin_filter_debounce.setRange(80, 1000)
        self.spin_filter_debounce.setSingleStep(20)
        perf_layout.addWidget(self.spin_filter_debounce, 1, 1)

        perf_layout.addWidget(QLabel("로그 최대 줄 수:"), 2, 0)
        self.spin_max_log_lines = QSpinBox()
        self.spin_max_log_lines.setRange(200, 20000)
        self.spin_max_log_lines.setSingleStep(100)
        perf_layout.addWidget(self.spin_max_log_lines, 2, 1)

        self.check_compact_duplicates = QCheckBox("같은 매물은 하나로 묶어 보기")
        perf_layout.addWidget(self.check_compact_duplicates, 3, 0, 1, 2)

        perf_layout.addWidget(QLabel("상세 정보 동시 조회 수"), 4, 0)
        self.spin_playwright_workers = QSpinBox()
        self.spin_playwright_workers.setRange(1, 16)
        self.spin_playwright_workers.setToolTip(
            "동시에 열어볼 상세 페이지 수입니다. 너무 높이면 차단되거나 PC 부담이 커질 수 있습니다."
        )
        perf_layout.addWidget(self.spin_playwright_workers, 4, 1)

        self.check_playwright_headless = QCheckBox("브라우저 창 숨기고 수집 (백그라운드)")
        perf_layout.addWidget(self.check_playwright_headless, 5, 0, 1, 2)

        self.check_block_heavy_resources = QCheckBox("이미지·글꼴 등 무거운 리소스 불러오지 않기")
        perf_layout.addWidget(self.check_block_heavy_resources, 6, 0, 1, 2)

        perf_layout.addWidget(QLabel("응답 대기 제한(ms):"), 7, 0)
        self.spin_playwright_drain_timeout = QSpinBox()
        self.spin_playwright_drain_timeout.setRange(100, 20000)
        self.spin_playwright_drain_timeout.setSingleStep(100)
        perf_layout.addWidget(self.spin_playwright_drain_timeout, 7, 1)

        perf_layout.addWidget(QLabel("페이지 이동 제한 시간(ms):"), 8, 0)
        self.spin_playwright_navigation_timeout = QSpinBox()
        self.spin_playwright_navigation_timeout.setRange(1000, 60000)
        self.spin_playwright_navigation_timeout.setSingleStep(1000)
        perf_layout.addWidget(self.spin_playwright_navigation_timeout, 8, 1)

        self.check_article_api_fast_path = QCheckBox("빠른 목록 조회 사용 (권장)")
        self.check_article_api_fast_path.setToolTip(
            "브라우저 화면을 모두 기다리지 않고 목록 API로 먼저 가져옵니다."
        )
        perf_layout.addWidget(self.check_article_api_fast_path, 9, 0, 1, 2)

        perf_layout.addWidget(QLabel("빠른 목록 조회 제한 시간(ms):"), 10, 0)
        self.spin_article_api_timeout = QSpinBox()
        self.spin_article_api_timeout.setRange(300, 20000)
        self.spin_article_api_timeout.setSingleStep(100)
        perf_layout.addWidget(self.spin_article_api_timeout, 10, 1)

        perf_layout.addWidget(QLabel("목록 응답 조기 종료 대기(ms):"), 11, 0)
        self.spin_article_response_wait = QSpinBox()
        self.spin_article_response_wait.setRange(100, 20000)
        self.spin_article_response_wait.setSingleStep(100)
        perf_layout.addWidget(self.spin_article_response_wait, 11, 1)
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        layout.addStretch()
        return page

    def _build_geo_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        geo_group = QGroupBox("지도에서 주변 단지 찾기")
        geo_layout = QGridLayout()
        geo_layout.addWidget(QLabel("지도 확대 단계"), 0, 0)
        self.spin_geo_zoom = QSpinBox()
        self.spin_geo_zoom.setRange(12, 18)
        geo_layout.addWidget(self.spin_geo_zoom, 0, 1)

        geo_layout.addWidget(QLabel("탐색 범위(칸 수)"), 1, 0)
        self.spin_geo_rings = QSpinBox()
        self.spin_geo_rings.setRange(0, 6)
        self.spin_geo_rings.setToolTip("0이면 현재 위치만, 숫자가 클수록 주변을 더 넓게 훑습니다.")
        geo_layout.addWidget(self.spin_geo_rings, 1, 1)

        geo_layout.addWidget(QLabel("칸 간격(px):"), 2, 0)
        self.spin_geo_step = QSpinBox()
        self.spin_geo_step.setRange(120, 1600)
        self.spin_geo_step.setSingleStep(40)
        geo_layout.addWidget(self.spin_geo_step, 2, 1)

        geo_layout.addWidget(QLabel("칸마다 머무는 시간(ms):"), 3, 0)
        self.spin_geo_dwell = QSpinBox()
        self.spin_geo_dwell.setRange(100, 5000)
        self.spin_geo_dwell.setSingleStep(100)
        geo_layout.addWidget(self.spin_geo_dwell, 3, 1)

        self.check_geo_asset_apt = QCheckBox("아파트")
        self.check_geo_asset_apt.setToolTip("아파트·분양·재건축 등 단지형 매물")
        self.check_geo_asset_vl = QCheckBox("빌라·연립")
        self.check_geo_asset_vl.setToolTip("빌라, 연립, 다세대 등")
        asset_layout = QHBoxLayout()
        asset_layout.addWidget(self.check_geo_asset_apt)
        asset_layout.addWidget(self.check_geo_asset_vl)
        asset_layout.addStretch()
        geo_layout.addWidget(QLabel("찾을 주택 종류:"), 4, 0)
        geo_layout.addLayout(asset_layout, 4, 1)
        self.check_geo_incomplete_safety_mode = QCheckBox("탐색이 끊기면 자동 저장·이력 반영 보류")
        self.check_geo_incomplete_safety_mode.setToolTip(
            "지도 탐색이 불완전할 때 잘못된 이력/자동 등록을 막습니다."
        )
        geo_layout.addWidget(self.check_geo_incomplete_safety_mode, 5, 0, 1, 2)
        note = QLabel("오피스텔은 앱을 가볍게 유지하기 위해 아직 포함하지 않습니다.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 11px;")
        geo_layout.addWidget(note, 6, 0, 1, 2)
        geo_group.setLayout(geo_layout)
        layout.addWidget(geo_group)
        layout.addStretch()
        return page

    def _build_display_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        sort_group = QGroupBox("기본 정렬")
        sort_layout = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        sort_layout.addWidget(QLabel("정렬 기준:"))
        sort_layout.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["낮은 순 / 가나다 순", "높은 순 / 역순"])
        sort_layout.addWidget(self.combo_sort_order)
        sort_layout.addStretch()
        sort_group.setLayout(sort_layout)
        layout.addWidget(sort_group)

        badge_group = QGroupBox("강조 표시")
        badge_layout = QVBoxLayout()
        self.check_show_new_badge = QCheckBox("새로 나온 매물 표시")
        self.check_show_price_change = QCheckBox("가격 변동 표시")
        badge_layout.addWidget(self.check_show_new_badge)
        badge_layout.addWidget(self.check_show_price_change)
        badge_group.setLayout(badge_layout)
        layout.addWidget(badge_group)

        extra_group = QGroupBox("표에 더 보여줄 항목 (기본 숨김)")
        extra_layout = QVBoxLayout()
        hint = QLabel(
            "체크한 항목만 결과 표에 나타납니다. 저장 DB에는 넣지 않고, 화면·엑셀 내보내기에만 씁니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        extra_layout.addWidget(hint)
        self._extra_column_checks = {}
        for defn in RESULT_EXTRA_COLUMN_DEFS:
            cb = QCheckBox(str(defn["header"]))
            cb.setToolTip(f"필드: {defn['key']}")
            self._extra_column_checks[defn["id"]] = cb
            extra_layout.addWidget(cb)
        extra_group.setLayout(extra_layout)
        layout.addWidget(extra_group)

        card_group = QGroupBox("카드 보기")
        card_layout = QVBoxLayout()
        self.check_card_extra_meta = QCheckBox("카드에 동·타입 한 줄 보여 주기")
        self.check_card_extra_meta.setToolTip(
            "카드에 짧은 정보만 붙입니다. 중개사 연락처는 표시하지 않습니다."
        )
        card_layout.addWidget(self.check_card_extra_meta)
        card_group.setLayout(card_layout)
        layout.addWidget(card_group)
        layout.addStretch()
        return page

    def _load(self):
        def _int_setting(key, default):
            raw = settings.get(key, default)
            if raw is None:
                return int(default)
            try:
                return int(raw)
            except (TypeError, ValueError):
                return int(default)

        theme_token = str(settings.get("theme", "dark") or "dark")
        theme_idx = self.combo_theme.findData(theme_token)
        self.combo_theme.setCurrentIndex(theme_idx if theme_idx >= 0 else 0)
        self.check_tray.setChecked(settings.get("minimize_to_tray", True))
        self.check_notify.setChecked(settings.get("show_notifications", True))
        self.check_confirm.setChecked(settings.get("confirm_before_close", True))
        self.check_sound.setChecked(settings.get("play_sound_on_complete", True))
        self.combo_speed.setCurrentText(settings.get("crawl_speed", "보통"))
        engine_token = str(settings.get("crawl_engine", "playwright") or "playwright")
        engine_idx = self.combo_engine.findData(engine_token)
        self.combo_engine.setCurrentIndex(engine_idx if engine_idx >= 0 else 0)
        self.check_retry_on_error.setChecked(bool(settings.get("retry_on_error", True)))
        self.spin_max_retry_count.setValue(max(0, _int_setting("max_retry_count", 3)))
        self.spin_max_retry_count.setEnabled(self.check_retry_on_error.isChecked())
        self.check_fallback_engine.setChecked(bool(settings.get("fallback_engine_enabled", True)))
        self.check_include_pre.setChecked(bool(settings.get("include_pre_sale_rights", False)))
        self.check_detail_enrichment.setChecked(bool(settings.get("detail_enrichment_enabled", True)))
        self.check_detail_front_api.setChecked(bool(settings.get("detail_front_api_enabled", True)))
        self.spin_detail_max.setValue(max(0, _int_setting("detail_enrichment_max_per_complex", 0)))
        self.spin_article_page_delay.setValue(max(0, _int_setting("article_api_page_delay_ms", 150)))
        self.combo_sort_col.setCurrentText(settings.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentIndex(
            0 if settings.get("default_sort_order", "asc") == "asc" else 1
        )
        self.spin_history_batch.setValue(int(settings.get("history_batch_size", 200) or 200))
        self.spin_filter_debounce.setValue(int(settings.get("result_filter_debounce_ms", 220) or 220))
        self.spin_max_log_lines.setValue(int(settings.get("max_log_lines", 1500) or 1500))
        self.check_compact_duplicates.setChecked(bool(settings.get("compact_duplicate_listings", True)))
        self.spin_playwright_workers.setValue(int(settings.get("playwright_detail_workers", 12) or 12))
        self.check_playwright_headless.setChecked(bool(settings.get("playwright_headless", False)))
        self.check_block_heavy_resources.setChecked(
            bool(settings.get("playwright_block_heavy_resources", True))
        )
        self.spin_playwright_drain_timeout.setValue(
            int(settings.get("playwright_response_drain_timeout_ms", 3000) or 3000)
        )
        self.spin_playwright_navigation_timeout.setValue(
            int(settings.get("playwright_navigation_timeout_ms", 15000) or 15000)
        )
        self.check_article_api_fast_path.setChecked(
            bool(settings.get("playwright_article_api_fast_path", True))
        )
        self.spin_article_api_timeout.setValue(
            int(settings.get("playwright_article_api_timeout_ms", 2500) or 2500)
        )
        self.spin_article_response_wait.setValue(
            int(settings.get("playwright_article_response_wait_ms", 1200) or 1200)
        )
        self.spin_geo_zoom.setValue(int(settings.get("geo_default_zoom", 15) or 15))
        self.spin_geo_rings.setValue(max(0, _int_setting("geo_grid_rings", 1)))
        self.spin_geo_step.setValue(int(settings.get("geo_grid_step_px", 480) or 480))
        self.spin_geo_dwell.setValue(int(settings.get("geo_sweep_dwell_ms", 600) or 600))
        asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        self.check_geo_asset_apt.setChecked("APT" in asset_types)
        self.check_geo_asset_vl.setChecked("VL" in asset_types)
        self.check_geo_incomplete_safety_mode.setChecked(
            bool(settings.get("geo_incomplete_safety_mode", True))
        )
        self.check_show_new_badge.setChecked(bool(settings.get("show_new_badge", True)))
        self.check_show_price_change.setChecked(bool(settings.get("show_price_change", True)))
        self.check_card_extra_meta.setChecked(bool(settings.get("card_show_extra_meta", True)))
        enabled_extra = set(settings.get("result_extra_columns", []) or [])
        for col_id, cb in self._extra_column_checks.items():
            cb.setChecked(col_id in enabled_extra)

    def _save(self):
        asset_types = []
        if self.check_geo_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_geo_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            QMessageBox.warning(self, "경고", "아파트 또는 빌라·연립 중 하나 이상 선택해 주세요.")
            return

        extra_cols = [col_id for col_id, cb in self._extra_column_checks.items() if cb.isChecked()]
        theme_data = self.combo_theme.currentData()
        engine_data = self.combo_engine.currentData()
        new = {
            "theme": str(theme_data or "dark"),
            "minimize_to_tray": self.check_tray.isChecked(),
            "show_notifications": self.check_notify.isChecked(),
            "confirm_before_close": self.check_confirm.isChecked(),
            "play_sound_on_complete": self.check_sound.isChecked(),
            "crawl_speed": self.combo_speed.currentText(),
            "crawl_engine": str(engine_data or "playwright"),
            "retry_on_error": self.check_retry_on_error.isChecked(),
            "max_retry_count": self.spin_max_retry_count.value(),
            "fallback_engine_enabled": self.check_fallback_engine.isChecked(),
            "include_pre_sale_rights": self.check_include_pre.isChecked(),
            "detail_enrichment_enabled": self.check_detail_enrichment.isChecked(),
            "detail_front_api_enabled": self.check_detail_front_api.isChecked(),
            "detail_enrichment_max_per_complex": self.spin_detail_max.value(),
            "article_api_page_delay_ms": self.spin_article_page_delay.value(),
            "default_sort_column": self.combo_sort_col.currentText(),
            "default_sort_order": "asc" if self.combo_sort_order.currentIndex() == 0 else "desc",
            "history_batch_size": self.spin_history_batch.value(),
            "result_filter_debounce_ms": self.spin_filter_debounce.value(),
            "max_log_lines": self.spin_max_log_lines.value(),
            "startup_lazy_noncritical_tabs": False,
            "compact_duplicate_listings": self.check_compact_duplicates.isChecked(),
            "playwright_detail_workers": self.spin_playwright_workers.value(),
            "playwright_headless": self.check_playwright_headless.isChecked(),
            "playwright_block_heavy_resources": self.check_block_heavy_resources.isChecked(),
            "playwright_response_drain_timeout_ms": self.spin_playwright_drain_timeout.value(),
            "playwright_navigation_timeout_ms": self.spin_playwright_navigation_timeout.value(),
            "playwright_article_api_fast_path": self.check_article_api_fast_path.isChecked(),
            "playwright_article_api_timeout_ms": self.spin_article_api_timeout.value(),
            "playwright_article_response_wait_ms": self.spin_article_response_wait.value(),
            "geo_default_zoom": self.spin_geo_zoom.value(),
            "geo_grid_rings": self.spin_geo_rings.value(),
            "geo_grid_step_px": self.spin_geo_step.value(),
            "geo_sweep_dwell_ms": self.spin_geo_dwell.value(),
            "geo_asset_types": asset_types,
            "geo_incomplete_safety_mode": self.check_geo_incomplete_safety_mode.isChecked(),
            "show_new_badge": self.check_show_new_badge.isChecked(),
            "show_price_change": self.check_show_price_change.isChecked(),
            "result_extra_columns": extra_cols,
            "card_show_extra_meta": self.check_card_extra_meta.isChecked(),
        }
        settings.update(new)
        self.settings_changed.emit(new)
        self.accept()




class AlertSettingDialog(QDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    @staticmethod
    def _format_alert_scope(asset_type):
        scope = str(asset_type or "ALL").strip().upper() or "ALL"
        if scope == "ALL":
            return "공통"
        return scope

    def _setup_ui(self):
        self.setWindowTitle("🔔 알림 설정")
        self.setMinimumSize(650, 550)
        layout = QVBoxLayout(self)

        add_group = QGroupBox("➕ 알림 추가")
        add_layout = QGridLayout()
        add_layout.addWidget(QLabel("단지:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, asset_type, cid, _ in (self.db.get_all_complexes() if self.db else []):
            asset_token = str(asset_type or "APT").strip().upper() or "APT"
            self.combo_complex.addItem(
                f"{name} ({asset_token}:{cid})",
                {"cid": str(cid or ""), "name": str(name or ""), "asset_type": asset_token},
            )
        add_layout.addWidget(self.combo_complex, 0, 1, 1, 3)

        add_layout.addWidget(QLabel("유형:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매매", "전세", "월세"])
        add_layout.addWidget(self.combo_type, 1, 1)
        self.check_common_scope = QCheckBox("공통 적용(APT/VL)")
        add_layout.addWidget(self.check_common_scope, 1, 2, 1, 2)

        add_layout.addWidget(QLabel("면적(평):"), 2, 0)
        self.spin_area_min = QDoubleSpinBox()
        self.spin_area_min.setRange(0, 200)
        add_layout.addWidget(self.spin_area_min, 2, 1)
        add_layout.addWidget(QLabel("~"), 2, 2)
        self.spin_area_max = QDoubleSpinBox()
        self.spin_area_max.setRange(0, 200)
        self.spin_area_max.setValue(100)
        add_layout.addWidget(self.spin_area_max, 2, 3)

        add_layout.addWidget(QLabel("가격(만원):"), 3, 0)
        self.spin_price_min = QSpinBox()
        self.spin_price_min.setRange(0, 999999)
        self.spin_price_min.setSingleStep(1000)
        add_layout.addWidget(self.spin_price_min, 3, 1)
        add_layout.addWidget(QLabel("~"), 3, 2)
        self.spin_price_max = QSpinBox()
        self.spin_price_max.setRange(0, 999999)
        self.spin_price_max.setValue(100000)
        self.spin_price_max.setSingleStep(1000)
        add_layout.addWidget(self.spin_price_max, 3, 3)

        btn_add = QPushButton("➕ 추가")
        btn_add.clicked.connect(self._add)
        add_layout.addWidget(btn_add, 4, 0, 1, 4)
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        layout.addWidget(QLabel("설정된 알림:"))
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["단지", "자산 범위", "유형", "면적", "가격", "활성", "삭제"])
        alert_header = self.table.horizontalHeader()
        if alert_header is not None:
            alert_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        self._load()

    def _add(self):
        if not self.db:
            return
        if self.combo_complex.count() == 0:
            return
        data = self.combo_complex.currentData()
        if not data:
            return
        cid = str(data.get("cid", "") or "")
        name = str(data.get("name", "") or "")
        asset_type = "ALL" if self.check_common_scope.isChecked() else str(data.get("asset_type", "APT") or "APT")
        if self.db.add_alert_setting(
            cid,
            name,
            self.combo_type.currentText(),
            self.spin_area_min.value(),
            self.spin_area_max.value(),
            self.spin_price_min.value(),
            self.spin_price_max.value(),
            asset_type=asset_type,
        ):
            self._load()

    def _load(self):
        self.table.setRowCount(0)
        if not self.db:
            return
        for aid, cid, name, asset_type, tt, amin, amax, pmin, pmax, enabled in self.db.get_all_alert_settings():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"{name or cid} ({cid})"))
            self.table.setItem(row, 1, QTableWidgetItem(self._format_alert_scope(asset_type)))
            self.table.setItem(row, 2, QTableWidgetItem(tt))
            self.table.setItem(row, 3, QTableWidgetItem(f"{amin}~{amax}평"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{pmin:,}~{pmax:,}만"))
            check = QCheckBox()
            check.setChecked(enabled == 1)
            if self.db:
                check.stateChanged.connect(
                    lambda s, a=aid, db=self.db: db.toggle_alert_setting(
                        a, s == Qt.CheckState.Checked.value
                    )
                )
            self.table.setCellWidget(row, 5, check)
            btn = QPushButton("🗑️ 삭제")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 6, btn)

    def _delete(self, aid):
        if self.db:
            self.db.delete_alert_setting(aid)
            self._load()


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ 단축키")
        self.setMinimumSize(450, 400)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["기능", "단축키"])
        shortcuts_header = table.horizontalHeader()
        if shortcuts_header is not None:
            shortcuts_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        shortcuts_vheader = table.verticalHeader()
        if shortcuts_vheader is not None:
            shortcuts_vheader.setDefaultSectionSize(38)

        shortcuts = [
            ("▶ 크롤링 시작", SHORTCUTS["start_crawl"]),
            ("⏹ 크롤링 중지", SHORTCUTS["stop_crawl"]),
            ("💾 Excel 저장", SHORTCUTS["save_excel"]),
            ("📄 CSV 저장", SHORTCUTS["save_csv"]),
            ("🔄 새로고침", SHORTCUTS["refresh"]),
            ("🔎 검색", SHORTCUTS["search"]),
            ("⚙️ 설정", SHORTCUTS["settings"]),
            ("🎨 테마 변경", SHORTCUTS["toggle_theme"]),
            ("🧷 트레이 최소화", SHORTCUTS["minimize_tray"]),
            ("❌ 종료", SHORTCUTS["quit"]),
        ]
        table.setRowCount(len(shortcuts))
        for i, (desc, key) in enumerate(shortcuts):
            table.setItem(i, 0, QTableWidgetItem(desc))
            table.setItem(i, 1, QTableWidgetItem(key))

        layout.addWidget(table)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
