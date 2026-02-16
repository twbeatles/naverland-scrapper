from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QSpinBox, 
    QDoubleSpinBox, QHBoxLayout, QCheckBox, QLineEdit, QPushButton, 
    QListWidget, QAbstractItemView, QListWidgetItem, QDialogButtonBox
)
from PyQt6.QtCore import pyqtSignal

class MultiSelectDialog(QDialog):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(450, 550)
        self._selected = []
        self._setup_ui(items)
    
    def _setup_ui(self, items):
        layout = QVBoxLayout(self)
        
        # 상단 버튼
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("✅ 전체 선택")
        btn_all.clicked.connect(self._select_all)
        btn_none = QPushButton("⬜ 전체 해제")
        btn_none.clicked.connect(self._deselect_all)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        layout.addLayout(btn_layout)
        
        # 리스트
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for item_data in items:
            text, data = (item_data if isinstance(item_data, tuple) else (str(item_data), item_data))
            item = QListWidgetItem()
            checkbox = QCheckBox(text)
            checkbox.setProperty("data", data)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)
        layout.addWidget(self.list_widget)
        
        # 카운트
        self.count_label = QLabel("선택: 0개")
        self.count_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
        layout.addWidget(self.count_label)
        
        # 버튼
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        for i in range(self.list_widget.count()):
            cb = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(cb, QCheckBox):
                cb.stateChanged.connect(self._update_count)
    
    def _update_count(self):
        count = sum(1 for i in range(self.list_widget.count())
                   if isinstance(w := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and w.isChecked())
        self.count_label.setText(f"선택: {count}개")
    
    def _select_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(True)
    
    def _deselect_all(self):
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox):
                cb.setChecked(False)
    
    def _on_accept(self):
        self._selected = []
        for i in range(self.list_widget.count()):
            if isinstance(cb := self.list_widget.itemWidget(self.list_widget.item(i)), QCheckBox) and cb.isChecked():
                self._selected.append(cb.property("data"))
        self.accept()
    
    def selected_items(self): return self._selected

class AdvancedFilterDialog(QDialog):
    """고급 결과 필터 다이얼로그 (v7.3)"""
    filter_applied = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_filters=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 고급 필터")
        self.setMinimumWidth(450)
        self._filters = None
        self._setup_ui()
        if current_filters:
            self._apply_filters_to_ui(current_filters)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 가격 필터
        price_group = QGroupBox("💰 가격 필터")
        pg = QGridLayout(price_group)
        pg.addWidget(QLabel("최소 가격:"), 0, 0)
        self.price_min = QSpinBox()
        self.price_min.setRange(0, 9999999)
        self.price_min.setSuffix(" 만원")
        self.price_min.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_min, 0, 1)
        pg.addWidget(QLabel("최대 가격:"), 0, 2)
        self.price_max = QSpinBox()
        self.price_max.setRange(0, 9999999)
        self.price_max.setValue(9999999)
        self.price_max.setSuffix(" 만원")
        self.price_max.setSpecialValueText("제한 없음")
        pg.addWidget(self.price_max, 0, 3)
        layout.addWidget(price_group)
        
        # 면적 필터
        area_group = QGroupBox("📐 면적 필터")
        ag = QGridLayout(area_group)
        ag.addWidget(QLabel("최소 면적:"), 0, 0)
        self.area_min = QDoubleSpinBox()
        self.area_min.setRange(0, 500)
        self.area_min.setSuffix(" 평")
        self.area_min.setSpecialValueText("제한 없음")
        ag.addWidget(self.area_min, 0, 1)
        ag.addWidget(QLabel("최대 면적:"), 0, 2)
        self.area_max = QDoubleSpinBox()
        self.area_max.setRange(0, 500)
        self.area_max.setValue(500)
        self.area_max.setSuffix(" 평")
        ag.addWidget(self.area_max, 0, 3)
        layout.addWidget(area_group)
        
        # 층수 필터
        floor_group = QGroupBox("🏢 층수 필터")
        fg = QHBoxLayout(floor_group)
        self.floor_low = QCheckBox("저층")
        self.floor_mid = QCheckBox("중층")
        self.floor_high = QCheckBox("고층")
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        fg.addWidget(self.floor_low)
        fg.addWidget(self.floor_mid)
        fg.addWidget(self.floor_high)
        fg.addStretch()
        layout.addWidget(floor_group)
        
        # 특수 필터
        special_group = QGroupBox("⭐ 특수 필터")
        sg = QHBoxLayout(special_group)
        self.only_new = QCheckBox("🆕 신규 매물만")
        self.only_price_down = QCheckBox("📉 가격 하락만")
        self.only_price_change = QCheckBox("📊 가격 변동만")
        sg.addWidget(self.only_new)
        sg.addWidget(self.only_price_down)
        sg.addWidget(self.only_price_change)
        sg.addStretch()
        layout.addWidget(special_group)
        
        # 키워드 필터
        keyword_group = QGroupBox("🔤 키워드 필터")
        kg = QVBoxLayout(keyword_group)
        kg.addWidget(QLabel("포함 키워드 (쉼표로 구분):"))
        self.include_keywords = QLineEdit()
        self.include_keywords.setPlaceholderText("예: 급매, 역세권, 올수리")
        kg.addWidget(self.include_keywords)
        kg.addWidget(QLabel("제외 키워드 (쉼표로 구분):"))
        self.exclude_keywords = QLineEdit()
        self.exclude_keywords.setPlaceholderText("예: 반지하, 탑층")
        kg.addWidget(self.exclude_keywords)
        layout.addWidget(keyword_group)
        
        # 버튼
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self._reset)
        btn_apply = QPushButton("적용")
        btn_apply.clicked.connect(self._apply)
        btn_apply.setDefault(True)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)
    
    def _reset(self):
        self.price_min.setValue(0)
        self.price_max.setValue(9999999)
        self.area_min.setValue(0)
        self.area_max.setValue(500)
        self.floor_low.setChecked(True)
        self.floor_mid.setChecked(True)
        self.floor_high.setChecked(True)
        self.only_new.setChecked(False)
        self.only_price_down.setChecked(False)
        self.only_price_change.setChecked(False)
        self.include_keywords.clear()
        self.exclude_keywords.clear()
        self._filters = None
    
    def _apply(self):
        filters = {
            'price_min': self.price_min.value(),
            'price_max': self.price_max.value(),
            'area_min': self.area_min.value(),
            'area_max': self.area_max.value(),
            'floor_low': self.floor_low.isChecked(),
            'floor_mid': self.floor_mid.isChecked(),
            'floor_high': self.floor_high.isChecked(),
            'only_new': self.only_new.isChecked(),
            'only_price_down': self.only_price_down.isChecked(),
            'only_price_change': self.only_price_change.isChecked(),
            'include_keywords': [k.strip() for k in self.include_keywords.text().split(',') if k.strip()],
            'exclude_keywords': [k.strip() for k in self.exclude_keywords.text().split(',') if k.strip()],
        }
        self._filters = filters
        self.filter_applied.emit(filters)
        self.accept()

    def _apply_filters_to_ui(self, filters: dict):
        try:
            self.price_min.setValue(int(filters.get("price_min", self.price_min.value())))
            self.price_max.setValue(int(filters.get("price_max", self.price_max.value())))
            self.area_min.setValue(float(filters.get("area_min", self.area_min.value())))
            self.area_max.setValue(float(filters.get("area_max", self.area_max.value())))
            self.floor_low.setChecked(bool(filters.get("floor_low", True)))
            self.floor_mid.setChecked(bool(filters.get("floor_mid", True)))
            self.floor_high.setChecked(bool(filters.get("floor_high", True)))
            self.only_new.setChecked(bool(filters.get("only_new", False)))
            self.only_price_down.setChecked(bool(filters.get("only_price_down", False)))
            self.only_price_change.setChecked(bool(filters.get("only_price_change", False)))
            self.include_keywords.setText(", ".join(filters.get("include_keywords", [])))
            self.exclude_keywords.setText(", ".join(filters.get("exclude_keywords", [])))
        except Exception:
            pass

    def get_filters(self):
        return self._filters
