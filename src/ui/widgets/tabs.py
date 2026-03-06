from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QAbstractItemView, QInputDialog, QHeaderView
)
from PyQt6.QtCore import Qt
import webbrowser
from src.ui.widgets.components import EmptyStateWidget
from src.utils.logger import get_logger
from src.utils.helpers import get_article_url

logger = get_logger("FavoritesTab")

class FavoritesTab(QWidget):
    """즐겨찾기 탭 (v13.0)"""
    
    def __init__(self, db, theme="dark", parent=None, favorite_toggled=None):
        super().__init__(parent)
        self.db = db
        self._theme = theme
        self._favorite_toggled = favorite_toggled
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 헤더
        header = QHBoxLayout()
        title = QLabel("⭐ 즐겨찾기 매물")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 새로고침")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "단지명", "거래유형", "가격", "면적", "층/방향", "메모", "추가일", "링크"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._update_action_state)
        layout.addWidget(self.table)

        # 빈 상태
        self.empty_label = EmptyStateWidget(
            icon="⭐",
            title="즐겨찾기 매물이 없습니다",
            description="카드/테이블에서 ⭐을 눌러 추가하세요."
        )
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        
        # 하단 버튼
        btn_layout = QHBoxLayout()
        
        self.note_btn = QPushButton("📝 메모 편집")
        self.note_btn.clicked.connect(self._edit_note)
        btn_layout.addWidget(self.note_btn)
        
        self.remove_btn = QPushButton("❌ 즐겨찾기 해제")
        self.remove_btn.clicked.connect(self._remove_favorite)
        btn_layout.addWidget(self.remove_btn)
        
        btn_layout.addStretch()
        
        self.open_btn = QPushButton("🔗 매물 페이지 열기")
        self.open_btn.clicked.connect(self._open_article)
        btn_layout.addWidget(self.open_btn)
        
        layout.addLayout(btn_layout)
    
    def set_theme(self, theme: str):
        """테마 변경"""
        self._theme = theme
    
    def refresh(self):
        """즐겨찾기 목록 새로고침"""
        try:
            favorites = self.db.get_favorites()
            if favorites is None:
                favorites = []
        except Exception as e:
            logger.error(f"즐겨찾기 로드 실패: {e}")
            favorites = []
        
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(favorites))
        self._update_empty_state(len(favorites))
        
        for row, fav in enumerate(favorites):
            self.table.setItem(row, 0, QTableWidgetItem(str(fav.get("complex_name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(fav.get("trade_type", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(fav.get("price_text", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(f"{fav.get('area_pyeong', 0)}평"))
            self.table.setItem(row, 4, QTableWidgetItem(str(fav.get("floor_info", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(fav.get("note", ""))))
            created = fav.get("favorite_created_at") or fav.get("created_at") or fav.get("first_seen", "")
            self.table.setItem(row, 6, QTableWidgetItem(str(created)[:10]))
            
            # 데이터 저장
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, fav)
        self.table.setUpdatesEnabled(True)

        # selection actions
        self._update_action_state()

    def _update_action_state(self):
        has_selection = self.table.currentRow() >= 0
        has_rows = self.table.rowCount() > 0
        self.note_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)
        self.open_btn.setEnabled(has_selection)
        if not has_rows:
            self.note_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self.open_btn.setEnabled(False)

    def _update_empty_state(self, count):
        is_empty = count == 0
        self.empty_label.setVisible(is_empty)
        self.table.setEnabled(not is_empty)
    
    def _edit_note(self):
        """메모 편집"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        note, ok = QInputDialog.getText(
            self, "메모 편집", "메모:", 
            text=item_data.get("note", "")
        )
        if ok:
            self.db.update_article_note(
                item_data.get("article_id", ""),
                item_data.get("complex_id", ""),
                note
            )
            self.refresh()
    
    def _remove_favorite(self):
        """즐겨찾기 해제"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        if self._favorite_toggled:
            self._favorite_toggled(
                item_data.get("article_id", ""),
                item_data.get("complex_id", ""),
                False
            )
        else:
            self.db.toggle_favorite(
                item_data.get("article_id", ""),
                item_data.get("complex_id", ""),
                False
            )
        self.refresh()
    
    def _open_article(self):
        """매물 페이지 열기"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if item_data:
            url = get_article_url(
                item_data.get("complex_id", ""),
                item_data.get("article_id", ""),
                item_data.get("asset_type", "APT"),
            )
            webbrowser.open(url)
