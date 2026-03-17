from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QSplitter,
    QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.ui.dialogs import MultiSelectDialog


class GroupTab(QWidget):
    """그룹 관리 탭"""

    groups_updated = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_w = QWidget()
        left_l = QVBoxLayout(left_w)

        # 그룹 목록 섹션 (QGroupBox로 변경)
        gl = QGroupBox("그룹 목록")
        gl_layout = QVBoxLayout(gl)
        gl_layout.setSpacing(6)

        self.group_list = QListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.setToolTip("선택한 그룹의 단지 목록을 확인할 수 있습니다.") # Tooltip added
        self.group_list.itemClicked.connect(self._load_group_complexes)
        gl_layout.addWidget(self.group_list)

        # 그룹 버튼
        group_btns = QHBoxLayout()
        group_btns.setSpacing(4)
        self.btn_create_group = QPushButton("➕ 생성")
        self.btn_create_group.setObjectName("primaryBtn")
        self.btn_create_group.setToolTip("새 단지 그룹을 생성합니다.") # Tooltip added
        self.btn_create_group.clicked.connect(self._create_group)
        self.btn_delete_group = QPushButton("🗑 삭제")
        self.btn_delete_group.setObjectName("dangerBtn")
        self.btn_delete_group.setToolTip("선택한 그룹을 삭제합니다.") # Tooltip added
        self.btn_delete_group.clicked.connect(self._delete_group)
        group_btns.addWidget(self.btn_create_group)
        group_btns.addWidget(self.btn_delete_group)
        gl_layout.addLayout(group_btns)

        hint_grp = QLabel("💡 그룹을 만들면 예약 구동에도 사용할 수 있습니다.")
        hint_grp.setObjectName("hintLabel")
        gl_layout.addWidget(hint_grp)
        left_l.addWidget(gl) # Add the QGroupBox to the left_l layout
        splitter.addWidget(left_w)

        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.addWidget(QLabel("그룹 내 단지"))

        right_btn = QHBoxLayout()
        btn_add = QPushButton("단지 추가")
        btn_add.setObjectName("secondaryBtn")
        btn_add.clicked.connect(self._add_to_group)
        btn_add_multi = QPushButton("다중 추가")
        btn_add_multi.setObjectName("secondaryBtn")
        btn_add_multi.clicked.connect(self._add_to_group_multi)
        btn_rm = QPushButton("제거")
        btn_rm.setObjectName("dangerBtn")
        btn_rm.clicked.connect(self._remove_from_group)
        right_btn.addWidget(btn_add)
        right_btn.addWidget(btn_add_multi)
        right_btn.addWidget(btn_rm)
        right_l.addLayout(right_btn)

        self.complex_table = QTableWidget()
        self.complex_table.setColumnCount(5)
        self.complex_table.setHorizontalHeaderLabels(["ID", "자산", "단지명", "단지ID", "메모"])
        self.complex_table.setColumnHidden(0, True)
        complex_header = self.complex_table.horizontalHeader()
        if complex_header is not None:
            complex_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.complex_table.setAlternatingRowColors(True)
        right_l.addWidget(self.complex_table)
        splitter.addWidget(right_w)

        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

    @staticmethod
    def _normalize_complex_row(row):
        try:
            seq = list(row)
        except Exception:
            seq = []

        if len(seq) >= 5:
            db_id, name, asset_type, cid, memo = seq[0], seq[1], seq[2], seq[3], seq[4]
        elif len(seq) >= 4:
            db_id, name, cid, memo = seq[0], seq[1], seq[2], seq[3]
            asset_type = "APT"
        else:
            db_id = getattr(row, "id", "")
            name = getattr(row, "name", "")
            asset_type = getattr(row, "asset_type", "APT")
            cid = getattr(row, "complex_id", "")
            memo = getattr(row, "memo", "")

        return db_id, name, asset_type, cid, memo

    def load_groups(self):
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
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        if self.db.delete_group(gid):
            self.load_groups()
            self.groups_updated.emit()
            self.complex_table.setRowCount(0)

    def _load_group_complexes(self, item):
        gid = item.data(Qt.ItemDataRole.UserRole)
        rows = self.db.get_complexes_in_group(gid)
        self.complex_table.setUpdatesEnabled(False)
        self.complex_table.setRowCount(0)
        self.complex_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            db_id, name, asset_type, cid, memo = self._normalize_complex_row(row_data)
            self.complex_table.setItem(row_idx, 0, QTableWidgetItem(str(db_id)))
            self.complex_table.setItem(row_idx, 1, QTableWidgetItem(str(asset_type or "")))
            self.complex_table.setItem(row_idx, 2, QTableWidgetItem(str(name or "")))
            self.complex_table.setItem(row_idx, 3, QTableWidgetItem(str(cid or "")))
            self.complex_table.setItem(row_idx, 4, QTableWidgetItem(str(memo or "")))
        self.complex_table.setUpdatesEnabled(True)

    def _add_to_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QMessageBox.warning(self, "안내", "그룹을 먼저 선택해 주세요.")
            return

        gid = group_item.data(Qt.ItemDataRole.UserRole)
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(self, "안내", "DB에 저장된 단지가 없습니다.")
            return

        items = []
        for row_data in complexes:
            db_id, name, asset_type, cid, _memo = self._normalize_complex_row(row_data)
            items.append((f"{name} ({asset_type}:{cid})", db_id))

        dlg = MultiSelectDialog("단지 추가", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_complexes_to_group(gid, dlg.selected_items())
            self._load_group_complexes(group_item)

    def _add_to_group_multi(self):
        self._add_to_group()

    def _remove_from_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        row = self.complex_table.currentRow()
        if row < 0:
            return
        db_id_item = self.complex_table.item(row, 0)
        if not db_id_item:
            return
        db_id = int(db_id_item.text())
        self.db.remove_complex_from_group(gid, db_id)
        self._load_group_complexes(group_item)
