from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QInputDialog, QMessageBox, QListWidget, 
    QListWidgetItem, QLabel, QSplitter, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.ui.dialogs import MultiSelectDialog

class GroupTab(QWidget):
    """그룹 관리 탭"""
    
    groups_updated = pyqtSignal()  # 그룹 변경 시 시그널 발송
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()
        self.load_groups()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 그룹 목록 (왼쪽)
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.addWidget(QLabel("📁 그룹 목록"))
        
        gl = QHBoxLayout()
        btn_new = QPushButton("➕ 새 그룹")
        btn_new.clicked.connect(self._create_group)
        btn_del = QPushButton("🗑️ 삭제")
        btn_del.clicked.connect(self._delete_group)
        gl.addWidget(btn_new)
        gl.addWidget(btn_del)
        left_l.addLayout(gl)
        
        self.group_list = QListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.itemClicked.connect(self._load_group_complexes)
        left_l.addWidget(self.group_list)
        splitter.addWidget(left_w)
        
        # 그룹 내 단지 (오른쪽)
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.addWidget(QLabel("📋 그룹 내 단지"))
        
        rl = QHBoxLayout()
        btn_add = QPushButton("➕ 단지 추가")
        btn_add.clicked.connect(self._add_to_group)
        btn_add_multi = QPushButton("➕ 다중 추가")
        btn_add_multi.clicked.connect(self._add_to_group_multi)
        btn_rm = QPushButton("➖ 제거")
        btn_rm.clicked.connect(self._remove_from_group)
        rl.addWidget(btn_add)
        rl.addWidget(btn_add_multi)
        rl.addWidget(btn_rm)
        right_l.addLayout(rl)
        
        self.complex_table = QTableWidget()
        self.complex_table.setColumnCount(4)
        self.complex_table.setHorizontalHeaderLabels(["ID", "단지명", "단지ID", "메모"])
        self.complex_table.setColumnHidden(0, True)
        self.complex_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.complex_table.setAlternatingRowColors(True)
        right_l.addWidget(self.complex_table)
        splitter.addWidget(right_w)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

    def load_groups(self):
        """그룹 목록 로드"""
        self.group_list.clear()
        for gid, name, desc in self.db.get_all_groups():
            item = QListWidgetItem(f"{name} ({desc})" if desc else name)
            item.setData(Qt.ItemDataRole.UserRole, gid)
            self.group_list.addItem(item)

    def _create_group(self):
        name, ok = QInputDialog.getText(self, "새 그룹", "그룹 이름:")
        if ok and name:
            if self.db.create_group(name):
                self.load_groups()
                self.groups_updated.emit()

    def _delete_group(self):
        item = self.group_list.currentItem()
        if item:
            gid = item.data(Qt.ItemDataRole.UserRole)
            if self.db.delete_group(gid):
                self.load_groups()
                self.groups_updated.emit()
                self.complex_table.setRowCount(0)

    def _load_group_complexes(self, item):
        gid = item.data(Qt.ItemDataRole.UserRole)
        self.complex_table.setRowCount(0)
        for db_id, name, cid, memo in self.db.get_complexes_in_group(gid):
            row = self.complex_table.rowCount()
            self.complex_table.insertRow(row)
            self.complex_table.setItem(row, 0, QTableWidgetItem(str(db_id)))
            self.complex_table.setItem(row, 1, QTableWidgetItem(name))
            self.complex_table.setItem(row, 2, QTableWidgetItem(cid))
            self.complex_table.setItem(row, 3, QTableWidgetItem(memo or ""))

    def _add_to_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QMessageBox.warning(self, "알림", "그룹을 선택해주세요.")
            return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "알림", "DB에 저장된 단지가 없습니다.")
            return
        items = [(f"{name} ({cid})", db_id) for db_id, name, cid, _ in complexes]
        dlg = MultiSelectDialog("단지 추가", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_complexes_to_group(gid, dlg.selected_items())
            self._load_group_complexes(group_item)
            
    def _add_to_group_multi(self):
        self._add_to_group()

    def _remove_from_group(self):
        group_item = self.group_list.currentItem()
        if not group_item: return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        row = self.complex_table.currentRow()
        if row >= 0:
            db_id = int(self.complex_table.item(row, 0).text())
            self.db.remove_complex_from_group(gid, db_id)
            self._load_group_complexes(group_item)
