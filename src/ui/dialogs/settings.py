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
        self.setWindowTitle("⚙️ 설정")
        self.setMinimumSize(450, 450)
        layout = QVBoxLayout(self)
        
        # 테마
        tg = QGroupBox("🎨 테마")
        tl = QHBoxLayout()
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["dark", "light"])
        tl.addWidget(QLabel("테마:"))
        tl.addWidget(self.combo_theme)
        tl.addStretch()
        tg.setLayout(tl)
        layout.addWidget(tg)
        
        # 시스템
        sg = QGroupBox("🖥️ 시스템")
        sl = QVBoxLayout()
        self.check_tray = QCheckBox("닫기 시 트레이로 최소화")
        self.check_notify = QCheckBox("데스크톱 알림 표시")
        self.check_confirm = QCheckBox("종료 전 확인")
        self.check_sound = QCheckBox("크롤링 완료 시 알림음 재생")
        sl.addWidget(self.check_tray)
        sl.addWidget(self.check_notify)
        sl.addWidget(self.check_confirm)
        sl.addWidget(self.check_sound)
        sg.setLayout(sl)
        layout.addWidget(sg)
        
        # 크롤링
        cg = QGroupBox("🔄 크롤링")
        cl = QHBoxLayout()
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(list(CRAWL_SPEED_PRESETS.keys()))
        cl.addWidget(QLabel("기본 속도:"))
        cl.addWidget(self.combo_speed)
        cl.addStretch()
        cg.setLayout(cl)
        layout.addWidget(cg)
        
        # 정렬
        og = QGroupBox("📊 결과 정렬")
        ol = QHBoxLayout()
        self.combo_sort_col = QComboBox()
        self.combo_sort_col.addItems(["가격", "면적", "단지명", "거래유형"])
        ol.addWidget(QLabel("기준:"))
        ol.addWidget(self.combo_sort_col)
        self.combo_sort_order = QComboBox()
        self.combo_sort_order.addItems(["오름차순", "내림차순"])
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
        self.combo_speed.setCurrentText(settings.get("crawl_speed", "보통"))
        self.combo_sort_col.setCurrentText(settings.get("default_sort_column", "가격"))
        self.combo_sort_order.setCurrentText("오름차순" if settings.get("default_sort_order", "asc") == "asc" else "내림차순")
    
    def _save(self):
        new = {
            "theme": self.combo_theme.currentText(),
            "minimize_to_tray": self.check_tray.isChecked(),
            "show_notifications": self.check_notify.isChecked(),
            "confirm_before_close": self.check_confirm.isChecked(),
            "play_sound_on_complete": self.check_sound.isChecked(),
            "crawl_speed": self.combo_speed.currentText(),
            "default_sort_column": self.combo_sort_col.currentText(),
            "default_sort_order": "asc" if self.combo_sort_order.currentText() == "오름차순" else "desc"
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
        
        # 추가 폼
        add_g = QGroupBox("새 알림 추가")
        add_l = QGridLayout()
        add_l.addWidget(QLabel("단지:"), 0, 0)
        self.combo_complex = QComboBox()
        for _, name, cid, _ in (self.db.get_all_complexes() if self.db else []):
            self.combo_complex.addItem(f"{name} ({cid})", (cid, name))
        add_l.addWidget(self.combo_complex, 0, 1, 1, 3)
        
        add_l.addWidget(QLabel("유형:"), 1, 0)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["매매", "전세", "월세"])
        add_l.addWidget(self.combo_type, 1, 1)
        
        add_l.addWidget(QLabel("면적(평):"), 2, 0)
        self.spin_area_min = QDoubleSpinBox()
        self.spin_area_min.setRange(0, 200)
        add_l.addWidget(self.spin_area_min, 2, 1)
        add_l.addWidget(QLabel("~"), 2, 2)
        self.spin_area_max = QDoubleSpinBox()
        self.spin_area_max.setRange(0, 200)
        self.spin_area_max.setValue(100)
        add_l.addWidget(self.spin_area_max, 2, 3)
        
        add_l.addWidget(QLabel("가격(만원):"), 3, 0)
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
        
        btn_add = QPushButton("➕ 추가")
        btn_add.clicked.connect(self._add)
        add_l.addWidget(btn_add, 4, 0, 1, 4)
        add_g.setLayout(add_l)
        layout.addWidget(add_g)
        
        layout.addWidget(QLabel("설정된 알림:"))
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["단지", "유형", "면적", "가격", "활성", "삭제"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        btn_close = QPushButton("닫기")
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
            btn = QPushButton("🗑️")
            btn.clicked.connect(lambda _, a=aid: self._delete(a))
            self.table.setCellWidget(row, 5, btn)
    
    def _delete(self, aid):
        self.db.delete_alert_setting(aid)
        self._load()

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ 단축키")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        tbl = QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels(["기능", "단축키"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setAlternatingRowColors(True)
        shortcuts = [
            ("🚀 크롤링 시작", SHORTCUTS["start_crawl"]),
            ("⏹️ 크롤링 중지", SHORTCUTS["stop_crawl"]),
            ("💾 Excel 저장", SHORTCUTS["save_excel"]),
            ("📄 CSV 저장", SHORTCUTS["save_csv"]),
            ("🔄 새로고침", SHORTCUTS["refresh"]),
            ("🔍 검색", SHORTCUTS["search"]),
            ("🎨 테마 변경", SHORTCUTS["toggle_theme"]),
            ("📥 트레이 최소화", SHORTCUTS["minimize_tray"]),
            ("❌ 종료", SHORTCUTS["quit"])
        ]
        tbl.setRowCount(len(shortcuts))
        for i, (d, k) in enumerate(shortcuts):
            tbl.setItem(i, 0, QTableWidgetItem(d))
            tbl.setItem(i, 1, QTableWidgetItem(k))
        layout.addWidget(tbl)
        btn = QPushButton("닫기")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
