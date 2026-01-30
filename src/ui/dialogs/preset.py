from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QHBoxLayout, QPushButton
)

class PresetDialog(QDialog):
    def __init__(self, parent=None, preset_manager=None):
        super().__init__(parent)
        self.preset_manager = preset_manager
        self.selected_preset = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("📁 필터 프리셋")
        self.setMinimumSize(400, 350)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("저장된 프리셋:"))
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(self._load)
        layout.addWidget(self.list)
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("📂 불러오기")
        btn_load.clicked.connect(self._load)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_del)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        self._refresh()
    
    def _refresh(self):
        self.list.clear()
        if self.preset_manager:
            for name in self.preset_manager.get_all_names():
                self.list.addItem(name)
    
    def _load(self):
        if item := self.list.currentItem():
            self.selected_preset = item.text()
            self.accept()
    
    def _delete(self):
        if (item := self.list.currentItem()) and self.preset_manager:
            self.preset_manager.delete(item.text())
            self._refresh()
