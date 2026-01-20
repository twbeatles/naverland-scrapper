from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QListWidgetItem
)
from PyQt6.QtCore import Qt

class RecentSearchDialog(QDialog):
    """최근 검색 기록 다이얼로그"""
    def __init__(self, parent=None, history_manager=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.selected_search = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("🕐 최근 검색 기록")
        self.setMinimumSize(500, 400)
        layout = QVBoxLayout(self)
        
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_clear = QPushButton("🗑️ 기록 지우기")
        btn_clear.clicked.connect(self._clear)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.history_manager:
            for h in self.history_manager.get_recent():
                complexes = h.get('complexes', [])
                types = h.get('trade_types', [])
                timestamp = h.get('timestamp', '')
                text = f"[{timestamp}] {len(complexes)}개 단지 - {', '.join(types)}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, h)
                self.list.addItem(item)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_search = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    
    def _clear(self):
        if self.history_manager:
            self.history_manager.clear()
            self._refresh()
