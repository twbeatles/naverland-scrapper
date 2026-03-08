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
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core.managers import SettingsManager
from src.utils.constants import CRAWL_SPEED_PRESETS, SHORTCUTS

settings = SettingsManager()


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(500, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        theme_group = QGroupBox("🎨 테마")
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(10)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        theme_layout.addWidget(QLabel("테마:"))
        theme_layout.addWidget(self.combo_theme)
        theme_layout.addStretch()
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        system_group = QGroupBox("🖥️ 시스템")
        system_layout = QVBoxLayout()
        system_layout.setSpacing(10)
        self.check_tray = QCheckBox("닫기 시 트레이로 최소화")
        self.check_notify = QCheckBox("시스템 알림 표시")
        self.check_confirm = QCheckBox("종료 전 확인")
        self.check_sound = QCheckBox("크롤링 완료 시 알림음 재생")
        system_layout.addWidget(self.check_tray)
        system_layout.addWidget(self.check_notify)
        system_layout.addWidget(self.check_confirm)
        system_layout.addWidget(self.check_sound)
        system_group.setLayout(system_layout)
        layout.addWidget(system_group)

        crawl_group = QGroupBox("🕷️ 크롤링")
        crawl_layout = QGridLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        crawl_layout.addWidget(QLabel("기본 속도:"), 0, 0)
        crawl_layout.addWidget(self.combo_speed, 0, 1)

        crawl_layout.addWidget(QLabel("기본 엔진:"), 1, 0)
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["playwright", "selenium"])
        crawl_layout.addWidget(self.combo_engine, 1, 1)

        self.check_retry_on_error = QCheckBox("오류 시 자동 재시도")
        self.check_retry_on_error.toggled.connect(
            lambda checked: self.spin_max_retry_count.setEnabled(bool(checked))
        )
        crawl_layout.addWidget(self.check_retry_on_error, 2, 0, 1, 2)

        crawl_layout.addWidget(QLabel("최대 재시도 횟수:"), 3, 0)
        self.spin_max_retry_count = QSpinBox()
        self.spin_max_retry_count.setRange(0, 10)
        crawl_layout.addWidget(self.spin_max_retry_count, 3, 1)

        self.check_fallback_engine = QCheckBox("Playwright 실패 시 Selenium fallback")
        crawl_layout.addWidget(self.check_fallback_engine, 4, 0, 1, 2)
        crawl_group.setLayout(crawl_layout)
        layout.addWidget(crawl_group)

        perf_group = QGroupBox("⚡ 성능")
        perf_layout = QGridLayout()
        perf_layout.addWidget(QLabel("이력 배치 크기:"), 0, 0)
        self.spin_history_batch = QSpinBox()
        self.spin_history_batch.setRange(20, 5000)
        self.spin_history_batch.setSingleStep(20)
        perf_layout.addWidget(self.spin_history_batch, 0, 1)

        perf_layout.addWidget(QLabel("검색 디바운스(ms):"), 1, 0)
        self.spin_filter_debounce = QSpinBox()
        self.spin_filter_debounce.setRange(80, 1000)
        self.spin_filter_debounce.setSingleStep(20)
        perf_layout.addWidget(self.spin_filter_debounce, 1, 1)

        perf_layout.addWidget(QLabel("로그 최대 라인:"), 2, 0)
        self.spin_max_log_lines = QSpinBox()
        self.spin_max_log_lines.setRange(200, 20000)
        self.spin_max_log_lines.setSingleStep(100)
        perf_layout.addWidget(self.spin_max_log_lines, 2, 1)

        self.check_lazy_startup = QCheckBox("비핵심 탭 초기 로드 지연")
        perf_layout.addWidget(self.check_lazy_startup, 3, 0, 1, 2)

        self.check_compact_duplicates = QCheckBox("동일 매물 묶어서 표시")
        perf_layout.addWidget(self.check_compact_duplicates, 4, 0, 1, 2)

        perf_layout.addWidget(QLabel("Playwright 워커 수"), 5, 0)
        self.spin_playwright_workers = QSpinBox()
        self.spin_playwright_workers.setRange(1, 32)
        perf_layout.addWidget(self.spin_playwright_workers, 5, 1)

        self.check_playwright_headless = QCheckBox("Playwright headless 실행")
        perf_layout.addWidget(self.check_playwright_headless, 6, 0, 1, 2)

        self.check_block_heavy_resources = QCheckBox("이미지/폰트 등 무거운 리소스 차단")
        perf_layout.addWidget(self.check_block_heavy_resources, 7, 0, 1, 2)

        perf_layout.addWidget(QLabel("응답 drain timeout(ms):"), 8, 0)
        self.spin_playwright_drain_timeout = QSpinBox()
        self.spin_playwright_drain_timeout.setRange(100, 20000)
        self.spin_playwright_drain_timeout.setSingleStep(100)
        perf_layout.addWidget(self.spin_playwright_drain_timeout, 8, 1)
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        geo_group = QGroupBox("🗺 지도 탐색")
        geo_layout = QGridLayout()
        geo_layout.addWidget(QLabel("기본 줌"), 0, 0)
        self.spin_geo_zoom = QSpinBox()
        self.spin_geo_zoom.setRange(12, 18)
        geo_layout.addWidget(self.spin_geo_zoom, 0, 1)

        geo_layout.addWidget(QLabel("그리드 링"), 1, 0)
        self.spin_geo_rings = QSpinBox()
        self.spin_geo_rings.setRange(0, 6)
        geo_layout.addWidget(self.spin_geo_rings, 1, 1)

        geo_layout.addWidget(QLabel("그리드 간격(px):"), 2, 0)
        self.spin_geo_step = QSpinBox()
        self.spin_geo_step.setRange(120, 1600)
        self.spin_geo_step.setSingleStep(40)
        geo_layout.addWidget(self.spin_geo_step, 2, 1)

        geo_layout.addWidget(QLabel("지연 대기(ms):"), 3, 0)
        self.spin_geo_dwell = QSpinBox()
        self.spin_geo_dwell.setRange(100, 5000)
        self.spin_geo_dwell.setSingleStep(100)
        geo_layout.addWidget(self.spin_geo_dwell, 3, 1)

        self.check_geo_asset_apt = QCheckBox("APT")
        self.check_geo_asset_vl = QCheckBox("VL")
        asset_layout = QHBoxLayout()
        asset_layout.addWidget(self.check_geo_asset_apt)
        asset_layout.addWidget(self.check_geo_asset_vl)
        asset_layout.addStretch()
        geo_layout.addWidget(QLabel("자산 유형:"), 4, 0)
        geo_layout.addLayout(asset_layout, 4, 1)
        geo_group.setLayout(geo_layout)
        layout.addWidget(geo_group)

        sort_group = QGroupBox("📊 결과 정렬")
        sort_layout = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        sort_layout.addWidget(QLabel("기준:"))
        sort_layout.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["오름차순", "내림차순"])
        sort_layout.addWidget(self.combo_sort_order)
        sort_layout.addStretch()
        sort_group.setLayout(sort_layout)
        layout.addWidget(sort_group)

        layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self):
        self.combo_theme.setCurrentText(settings.get("theme", "dark"))
        self.check_tray.setChecked(settings.get("minimize_to_tray", True))
        self.check_notify.setChecked(settings.get("show_notifications", True))
        self.check_confirm.setChecked(settings.get("confirm_before_close", True))
        self.check_sound.setChecked(settings.get("play_sound_on_complete", True))
        self.combo_speed.setCurrentText(settings.get("crawl_speed", "보통"))
        self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.check_retry_on_error.setChecked(bool(settings.get("retry_on_error", True)))
        self.spin_max_retry_count.setValue(int(settings.get("max_retry_count", 3) or 3))
        self.spin_max_retry_count.setEnabled(self.check_retry_on_error.isChecked())
        self.check_fallback_engine.setChecked(
            bool(settings.get("fallback_engine_enabled", True))
        )
        self.combo_sort_col.setCurrentText(settings.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentText(
            "오름차순"
            if settings.get("default_sort_order", "asc") == "asc"
            else "내림차순"
        )
        self.spin_history_batch.setValue(int(settings.get("history_batch_size", 200) or 200))
        self.spin_filter_debounce.setValue(
            int(settings.get("result_filter_debounce_ms", 220) or 220)
        )
        self.spin_max_log_lines.setValue(int(settings.get("max_log_lines", 1500) or 1500))
        self.check_lazy_startup.setChecked(
            bool(settings.get("startup_lazy_noncritical_tabs", True))
        )
        self.check_compact_duplicates.setChecked(
            bool(settings.get("compact_duplicate_listings", True))
        )
        self.spin_playwright_workers.setValue(
            int(settings.get("playwright_detail_workers", 12) or 12)
        )
        self.check_playwright_headless.setChecked(
            bool(settings.get("playwright_headless", False))
        )
        self.check_block_heavy_resources.setChecked(
            bool(settings.get("playwright_block_heavy_resources", True))
        )
        self.spin_playwright_drain_timeout.setValue(
            int(settings.get("playwright_response_drain_timeout_ms", 3000) or 3000)
        )
        self.spin_geo_zoom.setValue(int(settings.get("geo_default_zoom", 15) or 15))
        self.spin_geo_rings.setValue(int(settings.get("geo_grid_rings", 1) or 1))
        self.spin_geo_step.setValue(int(settings.get("geo_grid_step_px", 480) or 480))
        self.spin_geo_dwell.setValue(int(settings.get("geo_sweep_dwell_ms", 600) or 600))
        asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        self.check_geo_asset_apt.setChecked("APT" in asset_types)
        self.check_geo_asset_vl.setChecked("VL" in asset_types)

    def _save(self):
        asset_types = []
        if self.check_geo_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_geo_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            asset_types = ["APT", "VL"]

        new = {
            "theme": self.combo_theme.currentText(),
            "minimize_to_tray": self.check_tray.isChecked(),
            "show_notifications": self.check_notify.isChecked(),
            "confirm_before_close": self.check_confirm.isChecked(),
            "play_sound_on_complete": self.check_sound.isChecked(),
            "crawl_speed": self.combo_speed.currentText(),
            "crawl_engine": self.combo_engine.currentText(),
            "retry_on_error": self.check_retry_on_error.isChecked(),
            "max_retry_count": self.spin_max_retry_count.value(),
            "fallback_engine_enabled": self.check_fallback_engine.isChecked(),
            "default_sort_column": self.combo_sort_col.currentText(),
            "default_sort_order": (
                "asc" if self.combo_sort_order.currentText() == "오름차순" else "desc"
            ),
            "history_batch_size": self.spin_history_batch.value(),
            "result_filter_debounce_ms": self.spin_filter_debounce.value(),
            "max_log_lines": self.spin_max_log_lines.value(),
            "startup_lazy_noncritical_tabs": self.check_lazy_startup.isChecked(),
            "compact_duplicate_listings": self.check_compact_duplicates.isChecked(),
            "playwright_detail_workers": self.spin_playwright_workers.value(),
            "playwright_headless": self.check_playwright_headless.isChecked(),
            "playwright_block_heavy_resources": self.check_block_heavy_resources.isChecked(),
            "playwright_response_drain_timeout_ms": self.spin_playwright_drain_timeout.value(),
            "geo_default_zoom": self.spin_geo_zoom.value(),
            "geo_grid_rings": self.spin_geo_rings.value(),
            "geo_grid_step_px": self.spin_geo_step.value(),
            "geo_sweep_dwell_ms": self.spin_geo_dwell.value(),
            "geo_asset_types": asset_types,
        }
        settings.update(new)
        self.settings_changed.emit(new)
        self.accept()


class AlertSettingDialog(QDialog):
    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("🔔 알림 설정")
        self.setMinimumSize(650, 550)
        layout = QVBoxLayout(self)

        add_group = QGroupBox("➕ 알림 추가")
        add_layout = QGridLayout()
        add_layout.addWidget(QLabel("단지:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, _asset_type, cid, _ in (self.db.get_all_complexes() if self.db else []):
            self.combo_complex.addItem(f"{name} ({cid})", (cid, name))
        add_layout.addWidget(self.combo_complex, 0, 1, 1, 3)

        add_layout.addWidget(QLabel("유형:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매매", "전세", "월세"])
        add_layout.addWidget(self.combo_type, 1, 1)

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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["단지", "유형", "면적", "가격", "활성", "삭제"])
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
        cid, name = data
        if self.db.add_alert_setting(
            cid,
            name,
            self.combo_type.currentText(),
            self.spin_area_min.value(),
            self.spin_area_max.value(),
            self.spin_price_min.value(),
            self.spin_price_max.value(),
        ):
            self._load()

    def _load(self):
        self.table.setRowCount(0)
        if not self.db:
            return
        for aid, cid, name, tt, amin, amax, pmin, pmax, enabled in self.db.get_all_alert_settings():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name or cid))
            self.table.setItem(row, 1, QTableWidgetItem(tt))
            self.table.setItem(row, 2, QTableWidgetItem(f"{amin}~{amax}평"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{pmin:,}~{pmax:,}만"))
            check = QCheckBox()
            check.setChecked(enabled == 1)
            if self.db:
                check.stateChanged.connect(
                    lambda s, a=aid, db=self.db: db.toggle_alert_setting(
                        a, s == Qt.CheckState.Checked.value
                    )
                )
            self.table.setCellWidget(row, 4, check)
            btn = QPushButton("🗑️ 삭제")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 5, btn)

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
