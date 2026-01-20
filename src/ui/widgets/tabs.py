from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, 
    QTableWidgetItem, QAbstractItemView, QInputDialog, QHeaderView
)
from PyQt6.QtCore import Qt
import webbrowser

class FavoritesTab(QWidget):
    """즐겨찾기 탭 (v13.0)"""
    
    def __init__(self, db, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = theme
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
        layout.addWidget(self.table)
        
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
        except Exception:
            favorites = []
        
        self.table.setRowCount(len(favorites))
        
        for row, fav in enumerate(favorites):
            self.table.setItem(row, 0, QTableWidgetItem(str(fav.get("complex_name", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(fav.get("trade_type", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(fav.get("price_text", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(f"{fav.get('area_pyeong', 0)}평"))
            self.table.setItem(row, 4, QTableWidgetItem(str(fav.get("floor_info", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(fav.get("note", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(str(fav.get("created_at", ""))[:10]))
            
            # 데이터 저장
            item = self.table.item(row, 0)
            if item:
                item.setData(Qt.ItemDataRole.UserRole, fav)
    
    def _edit_note(self):
        """메모 편집"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        item = self.table.item(row, 0)
        if not item:
            return
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        note, ok = QInputDialog.getText(
            self, "메모 편집", "메모:", 
            text=data.get("note", "")
        )
        if ok:
            self.db.update_article_note(
                data.get("article_id", ""),
                data.get("complex_id", ""),
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
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        self.db.toggle_favorite(
            data.get("article_id", ""),
            data.get("complex_id", ""),
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
        
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            url = f"https://new.land.naver.com/complexes/{data.get('complex_id', '')}?articleId={data.get('article_id', '')}"
            webbrowser.open(url)
