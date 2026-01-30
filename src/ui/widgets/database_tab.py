from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QInputDialog, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt
import webbrowser
from src.utils.helpers import get_complex_url
from src.ui.widgets.components import SearchBar
from src.utils.logger import get_logger

logger = get_logger("DatabaseTab")

class DatabaseTab(QWidget):
    """단지 DB 관리 탭"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._init_ui()
        self.load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 버튼 영역
        bl = QHBoxLayout()
        btn_rf = QPushButton("🔄 새로고침")
        btn_rf.clicked.connect(self.load_data)
        btn_dl = QPushButton("🗑️ 선택 삭제")
        btn_dl.clicked.connect(self._delete_complex)
        btn_dlm = QPushButton("🗑️ 다중 삭제")
        btn_dlm.clicked.connect(self._delete_complexes_multi)
        btn_memo = QPushButton("✏️ 메모 수정")
        btn_memo.clicked.connect(self._edit_memo)

        self.btn_delete = btn_dl
        self.btn_delete_multi = btn_dlm
        self.btn_memo = btn_memo
        
        bl.addWidget(btn_rf)
        bl.addWidget(btn_dl)
        bl.addWidget(btn_dlm)
        bl.addWidget(btn_memo)
        bl.addStretch()
        layout.addLayout(bl)
        
        # 검색
        self.search_bar = SearchBar("단지 검색...")
        self.search_bar.search_changed.connect(self._filter_table)
        layout.addWidget(self.search_bar)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "단지명", "단지ID", "메모"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_complex_url)
        layout.addWidget(self.table)

        # 빈 상태
        self.empty_label = QLabel("등록된 단지가 없습니다.\n크롤러 탭에서 단지를 추가한 뒤 DB에 저장하세요.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 30px;")
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        self.table.itemSelectionChanged.connect(self._update_action_state)

    def load_data(self):
        """DB에서 단지 목록 로드"""
        self.table.setRowCount(0)
        try:
            complexes = self.db.get_all_complexes()
            self._update_empty_state(len(complexes))
            for db_id, name, cid, memo in complexes:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(db_id)))
                self.table.setItem(row, 1, QTableWidgetItem(str(name)))
                self.table.setItem(row, 2, QTableWidgetItem(str(cid)))
                self.table.setItem(row, 3, QTableWidgetItem(str(memo) if memo else ""))
        except Exception as e:
            logger.error(f"로드 실패: {e}")
            self._update_empty_state(0)
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

    def _delete_complex(self):
        row = self.table.currentRow()
        if row >= 0:
            db_id = int(self.table.item(row, 0).text())
            if self.db.delete_complex(db_id):
                self.load_data()

    def _delete_complexes_multi(self):
        rows = set(item.row() for item in self.table.selectedItems())
        if rows:
            ids = [int(self.table.item(r, 0).text()) for r in rows]
            cnt = self.db.delete_complexes_bulk(ids)
            QMessageBox.information(self, "삭제 완료", f"{cnt}개 단지 삭제됨")
            self.load_data()

    def _edit_memo(self):
        row = self.table.currentRow()
        if row >= 0:
            db_id = int(self.table.item(row, 0).text())
            old = self.table.item(row, 3).text()
            new, ok = QInputDialog.getText(self, "메모 수정", "메모:", text=old)
            if ok:
                self.db.update_complex_memo(db_id, new)
                self.load_data()

    def _filter_table(self, text):
        for r in range(self.table.rowCount()):
            match = any(text.lower() in (self.table.item(r, c).text().lower() if self.table.item(r, c) else "") for c in range(4))
            self.table.setRowHidden(r, not match)

    def _open_complex_url(self):
        row = self.table.currentRow()
        if row >= 0:
            cid = self.table.item(row, 2).text()
            webbrowser.open(get_complex_url(cid))
