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
from src.utils.logger import get_logger


logger = get_logger("GroupTab")


class GroupTab(QWidget):
    """그룹 관리 탭"""

    groups_updated = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()

    def _init_ui(self):
        from src.ui.fluent.design_tokens import SPACE_SM as _SM, SPACE_XS as _XS
        from src.ui.widgets.components import (
            EmptyStateWidget,
            build_page_header,
            install_token_labels,
        )
        from src.utils.ui_labels import asset_label

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(_SM)
        outer.addWidget(
            build_page_header(
                "단지 묶음",
                "자주 함께 보는 단지를 묶어 두면 한 번에 불러오거나 예약 수집에 쓸 수 있습니다.",
            )
        )
        splitter = QSplitter(Qt.Orientation.Horizontal)

        gl = QGroupBox("묶음 목록")
        gl_layout = QVBoxLayout(gl)
        gl_layout.setSpacing(_XS)

        self.group_list = QListWidget()
        self.group_list.setAlternatingRowColors(True)
        self.group_list.setToolTip("묶음을 고르면 오른쪽에 들어 있는 단지가 보입니다.")
        self.group_list.currentItemChanged.connect(self._on_group_changed)
        gl_layout.addWidget(self.group_list, 1)

        self.group_empty_label = QLabel("아직 묶음이 없습니다.\n아래 「새 묶음」으로 만들어 보세요.")
        self.group_empty_label.setObjectName("listPlaceholder")
        self.group_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.group_empty_label.setWordWrap(True)
        gl_layout.addWidget(self.group_empty_label, 1)

        group_btns = QHBoxLayout()
        group_btns.setSpacing(_XS)
        self.btn_create_group = QPushButton("새 묶음")
        self.btn_create_group.setObjectName("primaryBtn")
        self.btn_create_group.setToolTip("새 단지 묶음을 만듭니다.")
        self.btn_create_group.clicked.connect(self._create_group)
        self.btn_delete_group = QPushButton("묶음 삭제")
        self.btn_delete_group.setObjectName("dangerBtn")
        self.btn_delete_group.setToolTip("고른 묶음을 지웁니다. 안에 든 단지 자체는 「내 단지」에 그대로 남습니다.")
        self.btn_delete_group.clicked.connect(self._delete_group)
        group_btns.addWidget(self.btn_create_group, 1)
        group_btns.addWidget(self.btn_delete_group)
        gl_layout.addLayout(group_btns)
        splitter.addWidget(gl)

        right_w = QGroupBox("묶음에 든 단지")
        self.complex_box = right_w
        right_l = QVBoxLayout(right_w)
        right_l.setSpacing(_XS)

        right_btn = QHBoxLayout()
        right_btn.setSpacing(_XS)
        self.btn_add_complex = QPushButton("단지 넣기")
        self.btn_add_complex.setObjectName("secondaryBtn")
        self.btn_add_complex.setToolTip("「내 단지」에 저장된 단지 중에서 골라 이 묶음에 넣습니다.")
        self.btn_add_complex.clicked.connect(self._add_to_group)
        self.btn_remove_complex = QPushButton("선택 빼기")
        self.btn_remove_complex.setObjectName("secondaryBtn")
        self.btn_remove_complex.setToolTip("고른 단지를 이 묶음에서만 뺍니다. 단지 자체는 지워지지 않습니다.")
        self.btn_remove_complex.clicked.connect(self._remove_from_group)
        right_btn.addWidget(self.btn_add_complex)
        right_btn.addWidget(self.btn_remove_complex)
        right_btn.addStretch()
        right_l.addLayout(right_btn)

        self.complex_table = QTableWidget()
        self.complex_table.setColumnCount(5)
        self.complex_table.setHorizontalHeaderLabels(["ID", "종류", "단지 이름", "단지 번호", "메모"])
        self.complex_table.setColumnHidden(0, True)
        complex_header = self.complex_table.horizontalHeader()
        if complex_header is not None:
            complex_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.complex_table.setAlternatingRowColors(True)
        self.complex_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.complex_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        install_token_labels(self.complex_table, 1, asset_label)
        self.complex_table.itemSelectionChanged.connect(self._update_action_state)
        right_l.addWidget(self.complex_table, 1)

        self.complex_empty = EmptyStateWidget(icon="FOLDER")
        right_l.addWidget(self.complex_empty, 1)
        splitter.addWidget(right_w)

        splitter.setSizes([300, 700])
        outer.addWidget(splitter, 1)
        self._update_action_state()

    def _current_group_id(self):
        item = self.group_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _update_action_state(self):
        has_groups = self.group_list.count() > 0
        has_group = self.group_list.currentItem() is not None
        rows = int(self.complex_table.rowCount() or 0)
        self.group_list.setVisible(has_groups)
        self.group_empty_label.setVisible(not has_groups)
        self.btn_delete_group.setEnabled(has_group)
        self.btn_add_complex.setEnabled(has_group)
        self.btn_remove_complex.setEnabled(has_group and self.complex_table.currentRow() >= 0)
        if not has_group:
            self.complex_empty.set_text(
                "묶음을 먼저 골라 주세요" if has_groups else "묶음을 먼저 만들어 주세요",
                "왼쪽에서 묶음을 고르면 들어 있는 단지가 여기에 보입니다."
                if has_groups
                else "왼쪽 아래 「새 묶음」을 눌러 시작합니다.",
            )
        else:
            self.complex_empty.set_text(
                "이 묶음은 아직 비어 있습니다",
                "「단지 넣기」로 「내 단지」에 저장한 단지를 넣어 주세요.",
            )
        show_table = has_group and rows > 0
        self.complex_table.setVisible(show_table)
        self.complex_empty.setVisible(not show_table)

    def _on_group_changed(self, current, _previous=None):
        if current is None:
            self.complex_table.setRowCount(0)
            self._update_action_state()
            return
        self._load_group_complexes(current)

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
        try:
            groups = self.db.get_all_groups()
        except Exception as e:
            logger.error(f"group load failed: {e}")
            return
        previous_gid = self._current_group_id()
        self.group_list.blockSignals(True)
        self.group_list.clear()
        target_row = 0 if groups else -1
        for row, (gid, name, desc) in enumerate(groups):
            item = QListWidgetItem(f"{name} ({desc})" if desc else name)
            item.setData(Qt.ItemDataRole.UserRole, gid)
            self.group_list.addItem(item)
            if gid == previous_gid:
                target_row = row
        self.group_list.blockSignals(False)
        # 묶음이 있으면 항상 하나를 골라 둔다 (빈 오른쪽 화면을 줄인다).
        self.group_list.setCurrentRow(target_row)
        self._on_group_changed(self.group_list.currentItem())

    def _create_group(self):
        name, ok = QInputDialog.getText(self, "새 묶음", "묶음 이름 (예: 관심 단지, 강남권)")
        name = str(name or "").strip()
        if not ok or not name:
            return
        if self.db.create_group(name):
            self.load_groups()
            for row in range(self.group_list.count()):
                item = self.group_list.item(row)
                if item is not None and item.text().split(" (")[0] == name:
                    self.group_list.setCurrentRow(row)
                    break
            self.groups_updated.emit()
        else:
            QMessageBox.warning(self, "만들지 못했습니다", "같은 이름의 묶음이 이미 있는지 확인해 주세요.")

    def _delete_group(self):
        item = self.group_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self,
            "묶음 삭제",
            f"'{item.text()}' 묶음을 지울까요?\n안에 든 단지는 「내 단지」에 그대로 남습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.db.delete_group(gid):
            self.complex_table.setRowCount(0)
            self.load_groups()
            self.groups_updated.emit()

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
        self.complex_box.setTitle(f"묶음에 든 단지 · {len(rows)}곳" if rows else "묶음에 든 단지")
        self._update_action_state()

    def _add_to_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            QMessageBox.information(self, "묶음을 골라 주세요", "왼쪽에서 단지를 넣을 묶음을 먼저 골라 주세요.")
            return

        gid = group_item.data(Qt.ItemDataRole.UserRole)
        complexes = self.db.get_all_complexes()
        if not complexes:
            QMessageBox.information(
                self,
                "「내 단지」가 비어 있습니다",
                "묶음에는 「내 단지」에 저장한 단지를 넣을 수 있습니다.\n"
                "「매물 수집」에서 단지를 추가한 뒤 「내 단지에 저장」을 눌러 주세요.",
            )
            return

        from src.utils.ui_labels import asset_label

        items = []
        for row_data in complexes:
            db_id, name, asset_type, _cid, _memo = self._normalize_complex_row(row_data)
            items.append((f"{name}  ·  {asset_label(asset_type)}", db_id))

        dlg = MultiSelectDialog("묶음에 넣을 단지 고르기", items, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_complexes_to_group(gid, dlg.selected_items())
            self._load_group_complexes(group_item)
            self.groups_updated.emit()

    def _add_to_group_multi(self):
        self._add_to_group()

    def _remove_from_group(self):
        group_item = self.group_list.currentItem()
        if not group_item:
            return
        gid = group_item.data(Qt.ItemDataRole.UserRole)
        rows = sorted({idx.row() for idx in self.complex_table.selectedIndexes()})
        if not rows and self.complex_table.currentRow() >= 0:
            rows = [self.complex_table.currentRow()]
        for row in rows:
            db_id_item = self.complex_table.item(row, 0)
            if not db_id_item:
                continue
            try:
                self.db.remove_complex_from_group(gid, int(db_id_item.text()))
            except ValueError:
                continue
        if rows:
            self._load_group_complexes(group_item)
            self.groups_updated.emit()
