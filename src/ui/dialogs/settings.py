from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QComboBox, QLabel, 
    QCheckBox, QDialogButtonBox, QGridLayout, QDoubleSpinBox, QSpinBox,
    QPushButton, QTableWidget, QHeaderView, QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
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
        self.setWindowTitle("?숋툘 ?ㅼ젙")
        self.setMinimumSize(500, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # ?뚮쭏
        tg = QGroupBox("?렓 ?뚮쭏")
        tl = QHBoxLayout()
        tl.setSpacing(10)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        tl.addWidget(QLabel("?뚮쭏:"))
        tl.addWidget(self.combo_theme)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)
        
        # ?쒖뒪??
        sg = QGroupBox("🖥️ 시스템")
        sl = QVBoxLayout()
        sl.setSpacing(10)
        self.check_tray = QCheckBox("닫기 시 트레이로 최소화")
        self.check_notify = QCheckBox("?곗뒪?ы넲 ?뚮┝ ?쒖떆")
        self.check_confirm = QCheckBox("醫낅즺 ???뺤씤")
        self.check_sound = QCheckBox("?щ·留??꾨즺 ???뚮┝???ъ깮")
        sl.addWidget(self.check_tray)
        sl.addWidget(self.check_notify)
        sl.addWidget(self.check_confirm)
        sl.addWidget(self.check_sound)
        sg.setLayout(sl)
        layout.addWidget(sg)
        
        # ?щ·留?
        cg = QGroupBox("🕷️ 크롤링")
        cl = QGridLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        cl.addWidget(QLabel("湲곕낯 ?띾룄:"), 0, 0)
        cl.addWidget(self.combo_speed, 0, 1)

        cl.addWidget(QLabel("湲곕낯 ?붿쭊:"), 1, 0)
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["playwright", "selenium"])
        cl.addWidget(self.combo_engine, 1, 1)

        self.check_retry_on_error = QCheckBox("오류 시 자동 재시도")
        self.check_retry_on_error.toggled.connect(
            lambda checked: self.spin_max_retry_count.setEnabled(bool(checked))
        )
        cl.addWidget(self.check_retry_on_error, 2, 0, 1, 2)

        cl.addWidget(QLabel("理쒕? ?ъ떆???잛닔:"), 3, 0)
        self.spin_max_retry_count = QSpinBox()
        self.spin_max_retry_count.setRange(0, 10)
        cl.addWidget(self.spin_max_retry_count, 3, 1)

        self.check_fallback_engine = QCheckBox("Playwright ?ㅽ뙣 ??Selenium fallback")
        cl.addWidget(self.check_fallback_engine, 4, 0, 1, 2)
        cg.setLayout(cl)
        layout.addWidget(cg)

        # ?깅뒫
        pg = QGroupBox("???깅뒫")
        pl = QGridLayout()
        pl.addWidget(QLabel("?대젰 諛곗튂 ?ш린:"), 0, 0)
        self.spin_history_batch = QSpinBox()
        self.spin_history_batch.setRange(20, 5000)
        self.spin_history_batch.setSingleStep(20)
        pl.addWidget(self.spin_history_batch, 0, 1)

        pl.addWidget(QLabel("寃???붾컮?댁뒪(ms):"), 1, 0)
        self.spin_filter_debounce = QSpinBox()
        self.spin_filter_debounce.setRange(80, 1000)
        self.spin_filter_debounce.setSingleStep(20)
        pl.addWidget(self.spin_filter_debounce, 1, 1)

        pl.addWidget(QLabel("濡쒓렇 理쒕? ?쇱씤:"), 2, 0)
        self.spin_max_log_lines = QSpinBox()
        self.spin_max_log_lines.setRange(200, 20000)
        self.spin_max_log_lines.setSingleStep(100)
        pl.addWidget(self.spin_max_log_lines, 2, 1)

        self.check_lazy_startup = QCheckBox("비핵심 탭 초기 로드 지연")
        pl.addWidget(self.check_lazy_startup, 3, 0, 1, 2)

        self.check_compact_duplicates = QCheckBox("?숈씪 留ㅻЪ 臾띠뼱???쒖떆")
        pl.addWidget(self.check_compact_duplicates, 4, 0, 1, 2)

        pl.addWidget(QLabel("Playwright ?뚯빱 ??"), 5, 0)
        self.spin_playwright_workers = QSpinBox()
        self.spin_playwright_workers.setRange(1, 32)
        pl.addWidget(self.spin_playwright_workers, 5, 1)

        self.check_playwright_headless = QCheckBox("Playwright headless ?ㅽ뻾")
        pl.addWidget(self.check_playwright_headless, 6, 0, 1, 2)

        self.check_block_heavy_resources = QCheckBox("?대?吏/?고듃 ??臾닿굅??由ъ냼??李⑤떒")
        pl.addWidget(self.check_block_heavy_resources, 7, 0, 1, 2)

        pl.addWidget(QLabel("응답 drain timeout(ms):"), 8, 0)
        self.spin_playwright_drain_timeout = QSpinBox()
        self.spin_playwright_drain_timeout.setRange(100, 20000)
        self.spin_playwright_drain_timeout.setSingleStep(100)
        pl.addWidget(self.spin_playwright_drain_timeout, 8, 1)
        pg.setLayout(pl)
        layout.addWidget(pg)

        gg = QGroupBox("?㎛ 吏???먯깋")
        gl = QGridLayout()
        gl.addWidget(QLabel("湲곕낯 以?"), 0, 0)
        self.spin_geo_zoom = QSpinBox()
        self.spin_geo_zoom.setRange(12, 18)
        gl.addWidget(self.spin_geo_zoom, 0, 1)

        gl.addWidget(QLabel("洹몃━??留?"), 1, 0)
        self.spin_geo_rings = QSpinBox()
        self.spin_geo_rings.setRange(0, 6)
        gl.addWidget(self.spin_geo_rings, 1, 1)

        gl.addWidget(QLabel("洹몃━??媛꾧꺽(px):"), 2, 0)
        self.spin_geo_step = QSpinBox()
        self.spin_geo_step.setRange(120, 1600)
        self.spin_geo_step.setSingleStep(40)
        gl.addWidget(self.spin_geo_step, 2, 1)

        gl.addWidget(QLabel("吏???湲?ms):"), 3, 0)
        self.spin_geo_dwell = QSpinBox()
        self.spin_geo_dwell.setRange(100, 5000)
        self.spin_geo_dwell.setSingleStep(100)
        gl.addWidget(self.spin_geo_dwell, 3, 1)

        self.check_geo_asset_apt = QCheckBox("APT")
        self.check_geo_asset_vl = QCheckBox("VL")
        asset_layout = QHBoxLayout()
        asset_layout.addWidget(self.check_geo_asset_apt)
        asset_layout.addWidget(self.check_geo_asset_vl)
        asset_layout.addStretch()
        gl.addWidget(QLabel("?먯궛 ?좏삎:"), 4, 0)
        gl.addLayout(asset_layout, 4, 1)
        gg.setLayout(gl)
        layout.addWidget(gg)
        
        # ?뺣젹
        og = QGroupBox("?뱤 寃곌낵 ?뺣젹")
        ol = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        ol.addWidget(QLabel("湲곗?:"))
        ol.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["?ㅻ쫫李⑥닚", "?대┝李⑥닚"])
        ol.addWidget(self.combo_sort_order)
        ol.addStretch()
        og.setLayout(ol)
        layout.addWidget(og)
        
        layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load(self):
        self.combo_theme.setCurrentText(settings.get("theme", "dark"))
        self.check_tray.setChecked(settings.get("minimize_to_tray", True))
        self.check_notify.setChecked(settings.get("show_notifications", True))
        self.check_confirm.setChecked(settings.get("confirm_before_close", True))
        self.check_sound.setChecked(settings.get("play_sound_on_complete", True))
        self.combo_speed.setCurrentText(settings.get("crawl_speed", "蹂댄넻"))
        self.combo_engine.setCurrentText(settings.get("crawl_engine", "playwright"))
        self.check_retry_on_error.setChecked(bool(settings.get("retry_on_error", True)))
        self.spin_max_retry_count.setValue(int(settings.get("max_retry_count", 3) or 3))
        self.spin_max_retry_count.setEnabled(self.check_retry_on_error.isChecked())
        self.check_fallback_engine.setChecked(bool(settings.get("fallback_engine_enabled", True)))
        self.combo_sort_col.setCurrentText(settings.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentText("?ㅻ쫫李⑥닚" if settings.get("default_sort_order", "asc") == "asc" else "?대┝李⑥닚")
        self.spin_history_batch.setValue(int(settings.get("history_batch_size", 200) or 200))
        self.spin_filter_debounce.setValue(int(settings.get("result_filter_debounce_ms", 220) or 220))
        self.spin_max_log_lines.setValue(int(settings.get("max_log_lines", 1500) or 1500))
        self.check_lazy_startup.setChecked(bool(settings.get("startup_lazy_noncritical_tabs", True)))
        self.check_compact_duplicates.setChecked(bool(settings.get("compact_duplicate_listings", True)))
        self.spin_playwright_workers.setValue(int(settings.get("playwright_detail_workers", 12) or 12))
        self.check_playwright_headless.setChecked(bool(settings.get("playwright_headless", False)))
        self.check_block_heavy_resources.setChecked(bool(settings.get("playwright_block_heavy_resources", True)))
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
            "default_sort_order": "asc" if self.combo_sort_order.currentText() == "?ㅻ쫫李⑥닚" else "desc",
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
        self.setWindowTitle("?뵒 ?뚮┝ ?ㅼ젙")
        self.setMinimumSize(650, 550)
        layout = QVBoxLayout(self)
        
        # 異붽? ??
        add_g = QGroupBox("???뚮┝ 異붽?")
        add_l = QGridLayout()
        add_l.addWidget(QLabel("?⑥?:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, cid, _ in (self.db.get_all_complexes() if self.db else []):
            self.combo_complex.addItem(f"{name} ({cid})", (cid, name))
        add_l.addWidget(self.combo_complex, 0, 1, 1, 3)
        
        add_l.addWidget(QLabel("?좏삎:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["留ㅻℓ", "?꾩꽭", "?붿꽭"])
        add_l.addWidget(self.combo_type, 1, 1)
        
        add_l.addWidget(QLabel("硫댁쟻(??:"), 2, 0)
        self.spin_area_min = QDoubleSpinBox()
        self.spin_area_min.setRange(0, 200)
        add_l.addWidget(self.spin_area_min, 2, 1)
        add_l.addWidget(QLabel("~"), 2, 2)
        self.spin_area_max = QDoubleSpinBox()
        self.spin_area_max.setRange(0, 200)
        self.spin_area_max.setValue(100)
        add_l.addWidget(self.spin_area_max, 2, 3)
        
        add_l.addWidget(QLabel("媛寃?留뚯썝):"), 3, 0)
        self.spin_price_min = QSpinBox()
        self.spin_price_min.setRange(0, 999999)
        self.spin_price_min.setSingleStep(1000)
        add_l.addWidget(self.spin_price_min, 3, 1)
        add_l.addWidget(QLabel("~"), 3, 2)
        self.spin_price_max = QSpinBox()
        self.spin_price_max.setRange(0, 999999)
        self.spin_price_max.setValue(100000)
        self.spin_price_max.setSingleStep(1000)
        add_l.addWidget(self.spin_price_max, 3, 3)
        
        btn_add = QPushButton("??異붽?")
        btn_add.clicked.connect(self._add)
        add_l.addWidget(btn_add, 4, 0, 1, 4)
        add_g.setLayout(add_l)
        layout.addWidget(add_g)
        
        layout.addWidget(QLabel("?ㅼ젙???뚮┝:"))
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["단지", "유형", "면적", "가격", "활성", "삭제"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        btn_close = QPushButton("?リ린")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        self._load()
    
    def _add(self):
        if self.combo_complex.count() == 0: return
        data = self.combo_complex.currentData()
        if not data: return
        cid, name = data
        if self.db.add_alert_setting(cid, name, self.combo_type.currentText(),
            self.spin_area_min.value(), self.spin_area_max.value(),
            self.spin_price_min.value(), self.spin_price_max.value()):
            self._load()
    
    def _load(self):
        self.table.setRowCount(0)
        if not self.db: return
        for aid, cid, name, tt, amin, amax, pmin, pmax, enabled in self.db.get_all_alert_settings():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name or cid))
            self.table.setItem(row, 1, QTableWidgetItem(tt))
            self.table.setItem(row, 2, QTableWidgetItem(f"{amin}~{amax}평"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{pmin:,}~{pmax:,}만"))
            check = QCheckBox()
            check.setChecked(enabled == 1)
            check.stateChanged.connect(lambda s, a=aid: self.db.toggle_alert_setting(a, s == Qt.CheckState.Checked.value))
            self.table.setCellWidget(row, 4, check)
            btn = QPushButton("🗑️ 삭제")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 5, btn)
    
    def _delete(self, aid):
        self.db.delete_alert_setting(aid)
        self._load()

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ 단축키")
        self.setMinimumSize(450, 400)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        tbl = QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["기능", "단축키"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().setDefaultSectionSize(38)
        shortcuts = [
            ("?? ?щ·留??쒖옉", SHORTCUTS["start_crawl"]),
            ("?뱄툘 ?щ·留?以묒?", SHORTCUTS["stop_crawl"]),
            ("💾 Excel 저장", SHORTCUTS["save_excel"]),
            ("📄 CSV 저장", SHORTCUTS["save_csv"]),
            ("?봽 ?덈줈怨좎묠", SHORTCUTS["refresh"]),
            ("🔎 검색", SHORTCUTS["search"]),
            ("?숋툘 ?ㅼ젙", SHORTCUTS["settings"]),
            ("🎨 테마 변경", SHORTCUTS["toggle_theme"]),
            ("🧷 트레이 최소화", SHORTCUTS["minimize_tray"]),
            ("??醫낅즺", SHORTCUTS["quit"])
        ]
        tbl.setRowCount(len(shortcuts))
        for i, (d, k) in enumerate(shortcuts):
            tbl.setItem(i, 0, QTableWidgetItem(d))
            tbl.setItem(i, 1, QTableWidgetItem(k))
        layout.addWidget(tbl)
        btn = QPushButton("?リ린")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
