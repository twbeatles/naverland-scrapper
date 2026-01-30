<<<<<<< HEAD
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QAbstractItemView, 
    QListWidgetItem, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt
from src.core.export import ExcelTemplate

class ExcelTemplateDialog(QDialog):
    """엑셀 내보내기 템플릿 설정 (v7.3)"""
    template_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_template=None):
        super().__init__(parent)
        self.setWindowTitle("📊 엑셀 템플릿 설정")
        self.setMinimumSize(400, 500)
        self._columns, self._order = self._normalize_template(current_template)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel("내보낼 컬럼을 선택하고 순서를 조정하세요:")
        layout.addWidget(info)
        
        # 컬럼 목록
        self.column_list = QListWidget()
        self.column_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        for col_name in self._order:
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self._columns.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
        
        layout.addWidget(self.column_list)
        
        # 순서 조정 버튼
        order_layout = QHBoxLayout()
        btn_up = QPushButton("⬆️ 위로")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("⬇️ 아래로")
        btn_down.clicked.connect(self._move_down)
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addStretch()
        layout.addLayout(order_layout)
        
        # 전체 선택/해제
        select_layout = QHBoxLayout()
        btn_all = QPushButton("전체 선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체 해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_reset = QPushButton("기본값")
        btn_reset.clicked.connect(self._reset)
        select_layout.addWidget(btn_all)
        select_layout.addWidget(btn_none)
        select_layout.addWidget(btn_reset)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)
    
    def _move_up(self):
        row = self.column_list.currentRow()
        if row > 0:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row - 1, item)
            self.column_list.setCurrentRow(row - 1)
    
    def _move_down(self):
        row = self.column_list.currentRow()
        if row < self.column_list.count() - 1:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row + 1, item)
            self.column_list.setCurrentRow(row + 1)
    
    def _set_all(self, checked):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
    
    def _reset(self):
        self.column_list.clear()
        default = ExcelTemplate.get_default_template()
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
    
    def _save(self):
        template = {}
        column_order = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            name = item.text()
            enabled = item.checkState() == Qt.CheckState.Checked
            template[name] = enabled
            column_order.append(name)
        
        result = {'columns': template, 'order': column_order}
        self.template_saved.emit(result)
        self.accept()

    def _normalize_template(self, current_template):
        columns = None
        order = None

        if isinstance(current_template, dict):
            if "columns" in current_template:
                columns = current_template.get("columns", {})
                order = current_template.get("order", [])
            else:
                columns = current_template

        if not order:
            order = list(ExcelTemplate.get_column_order())

        for col in ExcelTemplate.get_column_order():
            if col not in order:
                order.append(col)

        if columns is None:
            columns = ExcelTemplate.get_default_template()
        else:
            default = ExcelTemplate.get_default_template()
            for col in default:
                if col not in columns:
                    columns[col] = default[col]

        return columns, order
=======
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QAbstractItemView, 
    QListWidgetItem, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt
from src.core.export import ExcelTemplate

class ExcelTemplateDialog(QDialog):
    """엑셀 내보내기 템플릿 설정 (v7.3)"""
    template_saved = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_template=None):
        super().__init__(parent)
        self.setWindowTitle("📊 엑셀 템플릿 설정")
        self.setMinimumSize(400, 500)
        self.current_template = current_template or ExcelTemplate.get_default_template()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = QLabel("내보낼 컬럼을 선택하고 순서를 조정하세요:")
        layout.addWidget(info)
        
        # 컬럼 목록
        self.column_list = QListWidget()
        self.column_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if self.current_template.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
        
        layout.addWidget(self.column_list)
        
        # 순서 조정 버튼
        order_layout = QHBoxLayout()
        btn_up = QPushButton("⬆️ 위로")
        btn_up.clicked.connect(self._move_up)
        btn_down = QPushButton("⬇️ 아래로")
        btn_down.clicked.connect(self._move_down)
        order_layout.addWidget(btn_up)
        order_layout.addWidget(btn_down)
        order_layout.addStretch()
        layout.addLayout(order_layout)
        
        # 전체 선택/해제
        select_layout = QHBoxLayout()
        btn_all = QPushButton("전체 선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체 해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_reset = QPushButton("기본값")
        btn_reset.clicked.connect(self._reset)
        select_layout.addWidget(btn_all)
        select_layout.addWidget(btn_none)
        select_layout.addWidget(btn_reset)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)
    
    def _move_up(self):
        row = self.column_list.currentRow()
        if row > 0:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row - 1, item)
            self.column_list.setCurrentRow(row - 1)
    
    def _move_down(self):
        row = self.column_list.currentRow()
        if row < self.column_list.count() - 1:
            item = self.column_list.takeItem(row)
            self.column_list.insertItem(row + 1, item)
            self.column_list.setCurrentRow(row + 1)
    
    def _set_all(self, checked):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
    
    def _reset(self):
        self.column_list.clear()
        default = ExcelTemplate.get_default_template()
        for col_name in ExcelTemplate.get_column_order():
            item = QListWidgetItem(col_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if default.get(col_name, True) else Qt.CheckState.Unchecked)
            self.column_list.addItem(item)
    
    def _save(self):
        template = {}
        column_order = []
        for i in range(self.column_list.count()):
            item = self.column_list.item(i)
            name = item.text()
            enabled = item.checkState() == Qt.CheckState.Checked
            template[name] = enabled
            column_order.append(name)
        
        result = {'columns': template, 'order': column_order}
        self.template_saved.emit(result)
        self.accept()
>>>>>>> d9c1bab01fe7f0174c099636906ac082e1c1c62b
