"""Settings dialog — basic vs advanced progressive disclosure."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
from src.utils.ui_labels import SETTINGS_TAB_ADVANCED, SETTINGS_TAB_BASIC


def _scroll_wrap(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QScrollArea.Shape.NoFrame)
    area.setWidget(widget)
    return area


def _hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setObjectName("hintLabel")
    lbl.setStyleSheet("color: #888; font-size: 11px;")
    return lbl


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extra_column_checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        self.setWindowTitle("설정")
        self.setMinimumSize(560, 520)
        root = QVBoxLayout(self)
        root.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(_scroll_wrap(self._build_basic_tab()), SETTINGS_TAB_BASIC)
        tabs.addTab(_scroll_wrap(self._build_advanced_tab()), SETTINGS_TAB_ADVANCED)
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ── Basic ────────────────────────────────────────────────────────

    def _build_basic_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        theme_group = QGroupBox("화면")
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
        for w in (self.check_tray, self.check_notify, self.check_confirm, self.check_sound):
            system_layout.addWidget(w)
        system_group.setLayout(system_layout)
        layout.addWidget(system_group)

        crawl_group = QGroupBox("수집 (일상)")
        crawl_layout = QGridLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        crawl_layout.addWidget(QLabel("수집 속도:"), 0, 0)
        crawl_layout.addWidget(self.combo_speed, 0, 1)
        crawl_layout.addWidget(
            _hint("너무 빠르면 차단될 수 있습니다. 보통을 권장합니다."), 1, 0, 1, 2
        )

        self.check_include_pre = QCheckBox("분양권 매물도 함께 수집")
        self.check_include_pre.setToolTip("켜면 목록 건수가 늘 수 있습니다.")
        crawl_layout.addWidget(self.check_include_pre, 2, 0, 1, 2)

        self.check_detail_enrichment = QCheckBox("중개사·기전세 등 상세 정보 가져오기")
        self.check_detail_enrichment.setToolTip("끄면 수집이 훨씬 가벼워집니다.")
        crawl_layout.addWidget(self.check_detail_enrichment, 3, 0, 1, 2)

        self.check_compact_duplicates = QCheckBox("같은 매물은 하나로 묶어 보기")
        crawl_layout.addWidget(self.check_compact_duplicates, 4, 0, 1, 2)
        crawl_group.setLayout(crawl_layout)
        layout.addWidget(crawl_group)

        display_group = QGroupBox("결과 화면")
        display_layout = QVBoxLayout()
        sort_row = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["낮은 순 / 가나다 순", "높은 순 / 역순"])
        sort_row.addWidget(QLabel("기본 정렬:"))
        sort_row.addWidget(self.combo_sort_col)
        sort_row.addWidget(self.combo_sort_order)
        sort_row.addStretch()
        display_layout.addLayout(sort_row)
        self.check_show_new_badge = QCheckBox("새로 나온 매물 표시")
        self.check_show_price_change = QCheckBox("가격 변동 표시")
        self.check_card_extra_meta = QCheckBox("카드에 동·타입 한 줄 보여 주기")
        for w in (
            self.check_show_new_badge,
            self.check_show_price_change,
            self.check_card_extra_meta,
        ):
            display_layout.addWidget(w)
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        geo_group = QGroupBox("지도 탐색 (기본)")
        geo_layout = QGridLayout()
        self.spin_geo_zoom = QSpinBox()
        self.spin_geo_zoom.setRange(12, 18)
        self.spin_geo_rings = QSpinBox()
        self.spin_geo_rings.setRange(0, 6)
        self.spin_geo_rings.setToolTip("0이면 현재 위치만, 숫자가 클수록 주변을 더 넓게 훑습니다.")
        geo_layout.addWidget(QLabel("지도 확대 단계"), 0, 0)
        geo_layout.addWidget(self.spin_geo_zoom, 0, 1)
        geo_layout.addWidget(QLabel("탐색 범위(칸 수)"), 1, 0)
        geo_layout.addWidget(self.spin_geo_rings, 1, 1)
        self.check_geo_asset_apt = QCheckBox("아파트")
        self.check_geo_asset_vl = QCheckBox("빌라·연립")
        asset_row = QHBoxLayout()
        asset_row.addWidget(self.check_geo_asset_apt)
        asset_row.addWidget(self.check_geo_asset_vl)
        asset_row.addStretch()
        geo_layout.addWidget(QLabel("찾을 주택 종류:"), 2, 0)
        geo_layout.addLayout(asset_row, 2, 1)
        geo_group.setLayout(geo_layout)
        layout.addWidget(geo_group)

        layout.addWidget(
            _hint("엔진·타임아웃·워커 등 세부 항목은 「고급」 탭에 있습니다.")
        )
        layout.addStretch()
        return page

    # ── Advanced ─────────────────────────────────────────────────────

    def _build_advanced_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        engine_group = QGroupBox("수집 엔진 · 재시도")
        engine_layout = QGridLayout()
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Playwright (권장)", "playwright")
        self.combo_engine.addItem("Selenium (보조)", "selenium")
        engine_layout.addWidget(QLabel("수집 엔진:"), 0, 0)
        engine_layout.addWidget(self.combo_engine, 0, 1)

        self.check_retry_on_error = QCheckBox("실패 시 자동으로 다시 시도")
        self.check_retry_on_error.toggled.connect(
            lambda checked: self.spin_max_retry_count.setEnabled(bool(checked))
        )
        engine_layout.addWidget(self.check_retry_on_error, 1, 0, 1, 2)
        engine_layout.addWidget(QLabel("다시 시도 횟수:"), 2, 0)
        self.spin_max_retry_count = QSpinBox()
        self.spin_max_retry_count.setRange(0, 10)
        engine_layout.addWidget(self.spin_max_retry_count, 2, 1)
        self.check_fallback_engine = QCheckBox("Playwright 실패 시 Selenium으로 이어 수집")
        engine_layout.addWidget(self.check_fallback_engine, 3, 0, 1, 2)
        engine_group.setLayout(engine_layout)
        layout.addWidget(engine_group)

        detail_group = QGroupBox("상세 · 목록 조회")
        detail_layout = QGridLayout()
        self.check_detail_front_api = QCheckBox("상세 정보 보완 조회 사용")
        self.check_detail_front_api.setToolTip(
            "상세 페이지가 비어 있어도 중개 정보를 보충합니다."
        )
        detail_layout.addWidget(self.check_detail_front_api, 0, 0, 1, 2)
        self.check_detail_front_api_only = QCheckBox("상세 HTML 건너뛰고 API만 조회")
        self.check_detail_front_api_only.setToolTip(
            "fin.land 상세 페이지가 404이거나 느릴 때 권장합니다. "
            "HTML 없이 front-api만 호출해 전화·중개 정보를 보충합니다."
        )
        detail_layout.addWidget(self.check_detail_front_api_only, 1, 0, 1, 2)
        detail_layout.addWidget(QLabel("단지마다 상세 조회 한도:"), 2, 0)
        self.spin_detail_max = QSpinBox()
        self.spin_detail_max.setRange(0, 500)
        self.spin_detail_max.setSpecialValueText("제한 없음")
        detail_layout.addWidget(self.spin_detail_max, 2, 1)
        detail_layout.addWidget(QLabel("목록 페이지 사이 대기(ms):"), 3, 0)
        self.spin_article_page_delay = QSpinBox()
        self.spin_article_page_delay.setRange(0, 2000)
        self.spin_article_page_delay.setSingleStep(50)
        detail_layout.addWidget(self.spin_article_page_delay, 3, 1)
        self.check_article_api_fast_path = QCheckBox("빠른 목록 조회 사용 (권장)")
        detail_layout.addWidget(self.check_article_api_fast_path, 4, 0, 1, 2)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        perf_group = QGroupBox("속도 · 안정 (전문가)")
        perf_layout = QGridLayout()
        self.spin_history_batch = QSpinBox()
        self.spin_history_batch.setRange(20, 5000)
        self.spin_history_batch.setSingleStep(20)
        self.spin_filter_debounce = QSpinBox()
        self.spin_filter_debounce.setRange(80, 1000)
        self.spin_filter_debounce.setSingleStep(20)
        self.spin_max_log_lines = QSpinBox()
        self.spin_max_log_lines.setRange(200, 20000)
        self.spin_max_log_lines.setSingleStep(100)
        self.spin_playwright_workers = QSpinBox()
        self.spin_playwright_workers.setRange(1, 16)
        self.spin_playwright_workers.setToolTip("동시에 띄우는 상세 페이지 수입니다. 낮을수록 가볍습니다 (권장 2~4).")
        self.check_playwright_headless = QCheckBox("브라우저 창 숨기고 수집 (백그라운드)")
        self.check_block_heavy_resources = QCheckBox("이미지·글꼴 등 무거운 리소스 불러오지 않기")
        self.spin_playwright_drain_timeout = QSpinBox()
        self.spin_playwright_drain_timeout.setRange(100, 20000)
        self.spin_playwright_drain_timeout.setSingleStep(100)
        self.spin_playwright_navigation_timeout = QSpinBox()
        self.spin_playwright_navigation_timeout.setRange(1000, 60000)
        self.spin_playwright_navigation_timeout.setSingleStep(1000)
        self.spin_article_api_timeout = QSpinBox()
        self.spin_article_api_timeout.setRange(300, 20000)
        self.spin_article_api_timeout.setSingleStep(100)
        self.spin_article_response_wait = QSpinBox()
        self.spin_article_response_wait.setRange(100, 20000)
        self.spin_article_response_wait.setSingleStep(100)

        rows = [
            (0, "가격 이력 일괄 저장 크기:", self.spin_history_batch),
            (1, "결과 검색 반응 지연(ms):", self.spin_filter_debounce),
            (2, "로그 최대 줄 수:", self.spin_max_log_lines),
            (3, "상세 정보 동시 조회 수:", self.spin_playwright_workers),
            (6, "응답 대기 제한(ms):", self.spin_playwright_drain_timeout),
            (7, "페이지 이동 제한 시간(ms):", self.spin_playwright_navigation_timeout),
            (8, "빠른 목록 조회 제한 시간(ms):", self.spin_article_api_timeout),
            (9, "목록 응답 조기 종료 대기(ms):", self.spin_article_response_wait),
        ]
        for row, label, widget in rows:
            perf_layout.addWidget(QLabel(label), row, 0)
            perf_layout.addWidget(widget, row, 1)
        perf_layout.addWidget(self.check_playwright_headless, 4, 0, 1, 2)
        perf_layout.addWidget(self.check_block_heavy_resources, 5, 0, 1, 2)
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        geo_adv = QGroupBox("지도 탐색 (세부)")
        geo_layout = QGridLayout()
        self.spin_geo_step = QSpinBox()
        self.spin_geo_step.setRange(120, 1600)
        self.spin_geo_step.setSingleStep(40)
        self.spin_geo_dwell = QSpinBox()
        self.spin_geo_dwell.setRange(100, 5000)
        self.spin_geo_dwell.setSingleStep(100)
        self.check_geo_incomplete_safety_mode = QCheckBox(
            "탐색이 끊기면 자동 저장·이력 반영 보류"
        )
        geo_layout.addWidget(QLabel("칸 간격(px):"), 0, 0)
        geo_layout.addWidget(self.spin_geo_step, 0, 1)
        geo_layout.addWidget(QLabel("칸마다 머무는 시간(ms):"), 1, 0)
        geo_layout.addWidget(self.spin_geo_dwell, 1, 1)
        geo_layout.addWidget(self.check_geo_incomplete_safety_mode, 2, 0, 1, 2)
        geo_layout.addWidget(
            _hint("오피스텔은 앱을 가볍게 유지하기 위해 아직 포함하지 않습니다."),
            3,
            0,
            1,
            2,
        )
        geo_adv.setLayout(geo_layout)
        layout.addWidget(geo_adv)

        extra_group = QGroupBox("표에 더 보여줄 항목 (기본 숨김)")
        extra_layout = QVBoxLayout()
        extra_layout.addWidget(
            _hint(
                "체크한 항목만 결과 표에 나타납니다. DB에는 넣지 않고 화면·엑셀 내보내기에만 씁니다."
            )
        )
        self._extra_column_checks = {}
        for defn in RESULT_EXTRA_COLUMN_DEFS:
            cb = QCheckBox(str(defn["header"]))
            cb.setToolTip(f"필드: {defn['key']}")
            self._extra_column_checks[defn["id"]] = cb
            extra_layout.addWidget(cb)
        extra_group.setLayout(extra_layout)
        layout.addWidget(extra_group)
        layout.addStretch()
        return page

    # ── load / save (settings keys unchanged) ─────────────────────────

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
        self.check_detail_enrichment.setChecked(
            bool(settings.get("detail_enrichment_enabled", True))
        )
        self.check_detail_front_api.setChecked(
            bool(settings.get("detail_front_api_enabled", True))
        )
        self.check_detail_front_api_only.setChecked(
            bool(settings.get("detail_front_api_only", False))
        )
        self.spin_detail_max.setValue(max(0, _int_setting("detail_enrichment_max_per_complex", 0)))
        self.spin_article_page_delay.setValue(max(0, _int_setting("article_api_page_delay_ms", 150)))
        self.combo_sort_col.setCurrentText(settings.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentIndex(
            0 if settings.get("default_sort_order", "asc") == "asc" else 1
        )
        self.spin_history_batch.setValue(int(settings.get("history_batch_size", 200) or 200))
        self.spin_filter_debounce.setValue(
            int(settings.get("result_filter_debounce_ms", 220) or 220)
        )
        self.spin_max_log_lines.setValue(int(settings.get("max_log_lines", 1500) or 1500))
        self.check_compact_duplicates.setChecked(
            bool(settings.get("compact_duplicate_listings", True))
        )
        self.spin_playwright_workers.setValue(
            int(settings.get("playwright_detail_workers", 4) or 4)
        )
        self.check_playwright_headless.setChecked(bool(settings.get("playwright_headless", True)))
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
            QMessageBox.warning(
                self, "경고", "아파트 또는 빌라·연립 중 하나 이상 선택해 주세요."
            )
            return

        extra_cols = [
            col_id for col_id, cb in self._extra_column_checks.items() if cb.isChecked()
        ]
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
            "detail_front_api_only": self.check_detail_front_api_only.isChecked(),
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
        asset_type = (
            "ALL"
            if self.check_common_scope.isChecked()
            else str(data.get("asset_type", "APT") or "APT")
        )
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
        for (
            aid,
            cid,
            name,
            asset_type,
            tt,
            amin,
            amax,
            pmin,
            pmax,
            enabled,
        ) in self.db.get_all_alert_settings():
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
