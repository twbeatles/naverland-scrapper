from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QCheckBox,
)
import webbrowser

from src.utils.helpers import get_complex_url
from src.ui.widgets.components import SearchBar, EmptyStateWidget
from src.utils.logger import get_logger


logger = get_logger("DatabaseTab")


class DatabaseTab(QWidget):
    """단지 DB 관리 탭"""

    COL_ID = 0
    COL_ASSET = 1
    COL_NAME = 2
    COL_COMPLEX_ID = 3
    COL_MEMO = 4

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        self.btn_refresh_db = QPushButton("🔄 새로고침")
        self.btn_refresh_db.setObjectName("primaryBtn")
        self.btn_refresh_db.setToolTip("데이터베이스에서 단지 목록을 다시 불러옵니다.")
        self.btn_refresh_db.clicked.connect(self.load_data) # Changed from _load_complexes to load_data to match existing method
        self.btn_delete_db = QPushButton("🗑 삭제")
        self.btn_delete_db.setObjectName("dangerBtn")
        self.btn_delete_db.setToolTip("선택한 단지와 해당 매물 데이터를 데이터베이스에서 삭제합니다.")
        self.btn_delete_db.clicked.connect(self._delete_complex) # Changed from _delete_selected to _delete_complex to match existing method

        btn_delete_multi = QPushButton("다중 삭제")
        btn_delete_multi.setObjectName("dangerBtn")
        btn_delete_multi.clicked.connect(self._delete_complexes_multi)
        btn_memo = QPushButton("메모 수정")
        btn_memo.setObjectName("secondaryBtn")
        btn_memo.clicked.connect(self._edit_memo)

        self.btn_delete = self.btn_delete_db # Update reference to the new button
        self.btn_delete_multi = btn_delete_multi
        self.btn_memo = btn_memo

        button_layout.addWidget(self.btn_refresh_db)
        button_layout.addWidget(self.btn_delete_db)
        button_layout.addWidget(btn_delete_multi)
        button_layout.addWidget(btn_memo)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.search_bar = SearchBar("단지 검색...")
        self.search_bar.search_changed.connect(self._filter_table)
        layout.addWidget(self.search_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "자산", "단지명", "단지ID", "메모"])
        self.table.setColumnHidden(self.COL_ID, True)
        table_header = self.table.horizontalHeader()
        if table_header is not None:
            table_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_complex_url)
        layout.addWidget(self.table)

        self.empty_label = EmptyStateWidget(
            icon="📭",
            title="등록된 단지가 없습니다",
            description="크롤러 탭에서 단지를 추가하거나 DB로 저장해 주세요.",
        )
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        self.table.itemSelectionChanged.connect(self._update_action_state)

    def _normalize_complex_row(self, row):
        try:
            seq = list(row)
        except Exception:
            seq = []

        if len(seq) >= 5:
            db_id, name, asset_type, complex_id, memo = seq[0], seq[1], seq[2], seq[3], seq[4]
        elif len(seq) >= 4:
            # Backward compatibility (old schema tuple)
            db_id, name, complex_id, memo = seq[0], seq[1], seq[2], seq[3]
            asset_type = "APT"
        else:
            db_id = getattr(row, "id", "")
            name = getattr(row, "name", "")
            asset_type = getattr(row, "asset_type", "APT")
            complex_id = getattr(row, "complex_id", "")
            memo = getattr(row, "memo", "")

        return db_id, name, asset_type, complex_id, memo

    def load_data(self):
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        prev_sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        try:
            complexes = self.db.get_all_complexes()
            self._update_empty_state(len(complexes))
            self.table.setRowCount(len(complexes))
            for row_idx, row_data in enumerate(complexes):
                db_id, name, asset_type, complex_id, memo = self._normalize_complex_row(row_data)
                self.table.setItem(row_idx, self.COL_ID, QTableWidgetItem(str(db_id)))
                self.table.setItem(row_idx, self.COL_ASSET, QTableWidgetItem(str(asset_type or "")))
                self.table.setItem(row_idx, self.COL_NAME, QTableWidgetItem(str(name or "")))
                self.table.setItem(row_idx, self.COL_COMPLEX_ID, QTableWidgetItem(str(complex_id or "")))
                self.table.setItem(row_idx, self.COL_MEMO, QTableWidgetItem(str(memo) if memo else ""))
        except Exception as e:
            logger.error(f"load failed: {e}")
            self._update_empty_state(0)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(prev_sorting)
        self._update_action_state()

    def _update_empty_state(self, count):
        is_empty = count == 0
        self.empty_label.setVisible(is_empty)
        self.table.setEnabled(not is_empty)

    def _update_action_state(self):
        has_selection = self.table.currentRow() >= 0
        has_rows = self.table.rowCount() > 0
        self.btn_delete.setEnabled(has_selection)
        self.btn_delete_multi.setEnabled(has_rows)
        self.btn_memo.setEnabled(has_selection)

    def _confirm_delete(self, *, title: str, text: str) -> tuple[bool, bool]:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setInformativeText("기본값은 단지/그룹매핑만 삭제이며, 이력 삭제는 선택 옵션입니다.")
        purge_check = QCheckBox("관련 이력까지 삭제")
        purge_check.setChecked(False)
        msg.setCheckBox(purge_check)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        accepted = msg.exec() == QMessageBox.StandardButton.Yes
        return accepted, bool(purge_check.isChecked())

    def _delete_complex(self):
        row = self.table.currentRow()
        if row < 0:
            return

        db_id_item = self.table.item(row, self.COL_ID)
        name_item = self.table.item(row, self.COL_NAME)
        asset_item = self.table.item(row, self.COL_ASSET)
        cid_item = self.table.item(row, self.COL_COMPLEX_ID)

        if not db_id_item:
            return
        db_id = int(db_id_item.text())
        name = name_item.text() if name_item else ""
        asset_type = asset_item.text() if asset_item else ""
        complex_id = cid_item.text() if cid_item else ""

        ok, purge_related = self._confirm_delete(
            title="삭제 확인",
            text=f"{name} ({asset_type}:{complex_id}) 단지를 삭제하시겠습니까?",
        )
        if not ok:
            return

        if self.db.delete_complex(db_id, purge_related=purge_related):
            self.load_data()

    def _delete_complexes_multi(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()))
        if not rows:
            QMessageBox.information(self, "안내", "삭제할 행을 먼저 선택해 주세요.")
            return

        ids = []
        for row in rows:
            id_item = self.table.item(row, self.COL_ID)
            if not id_item:
                continue
            try:
                ids.append(int(id_item.text()))
            except ValueError:
                continue

        if not ids:
            return

        ok, purge_related = self._confirm_delete(
            title="다중 삭제 확인",
            text=f"선택된 {len(ids)}개 단지를 삭제하시겠습니까?",
        )
        if not ok:
            return

        cnt = self.db.delete_complexes_bulk(ids, purge_related=purge_related)
        QMessageBox.information(self, "삭제 완료", f"{cnt}개 단지 삭제")
        self.load_data()

    def _edit_memo(self):
        row = self.table.currentRow()
        if row < 0:
            return

        db_id_item = self.table.item(row, self.COL_ID)
        old_item = self.table.item(row, self.COL_MEMO)
        if not db_id_item:
            return

        db_id = int(db_id_item.text())
        old = old_item.text() if old_item else ""
        new, ok = QInputDialog.getText(self, "메모 수정", "메모:", text=old)
        if ok:
            self.db.update_complex_memo(db_id, new)
            self.load_data()

    def _filter_table(self, text):
        token = str(text or "").lower()
        for row in range(self.table.rowCount()):
            def _cell_text(col: int) -> str:
                cell = self.table.item(row, col)
                return cell.text().lower() if cell is not None else ""

            match = any(token in _cell_text(col) for col in range(self.table.columnCount()))
            self.table.setRowHidden(row, not match)

    def _open_complex_url(self):
        row = self.table.currentRow()
        if row < 0:
            return
        cid_item = self.table.item(row, self.COL_COMPLEX_ID)
        if cid_item:
            webbrowser.open(get_complex_url(cid_item.text()))
