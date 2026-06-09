from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox,
    QScrollArea, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from typing import Optional
import time

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    FigureCanvas = None
    Figure = None
    MATPLOTLIB_AVAILABLE = False

from src.utils.constants import TRADE_COLORS
from src.core.managers import SettingsManager
from src.utils.helpers import PriceConverter
from src.utils.logger import get_logger
from src.utils.plot import setup_korean_font, sanitize_text_for_matplotlib
from src.ui.styles import COLORS
from src.ui.widgets.components import EmptyStateWidget

logger = get_logger("Dashboard")
settings = SettingsManager()


class StatCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value_label: Optional[QLabel] = None

class ArticleCard(QFrame):
    """매물 카드 위젯 (v13.0)"""
    clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)
    
    def __init__(self, data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(280, 210)
        
        # 거래유형별 색상
        trade_type = self.data.get("거래유형", "매매")
        colors = TRADE_COLORS.get(trade_type, TRADE_COLORS["매매"])
        bg_color = colors["dark_bg"] if self.is_dark else colors["bg"]
        fg_color = colors["dark_fg"] if self.is_dark else colors["fg"]
        
        # 다크/라이트 모드에 따른 호버 배경
        hover_bg = f"{bg_color}" if self.is_dark else f"{fg_color}10"
        
        self.setStyleSheet(f"""
            ArticleCard {{
                background-color: {bg_color};
                border: 1px solid {fg_color}40;
                border-radius: 14px;
                padding: 14px;
            }}
            ArticleCard:hover {{
                border: 2px solid {fg_color};
                background-color: {hover_bg};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # 상단: 거래유형 칩 + 즐겨찾기
        top_layout = QHBoxLayout()
        type_label = QLabel(trade_type)
        type_label.setStyleSheet(
            f"color: {fg_color}; background-color: {fg_color}22; padding: 4px 10px; "
            "border-radius: 999px; font-weight: 700; font-size: 11px;"
        )
        top_layout.addWidget(type_label)
        top_layout.addStretch()
        
        # 신규/가격변동 배지
        duplicate_count = int(self.data.get("duplicate_count", 1) or 1)
        if duplicate_count > 1:
            dup_badge = QLabel(f"{duplicate_count}건")
            dup_badge.setStyleSheet("color: #06b6d4; font-weight: 700; font-size: 11px;")
            top_layout.addWidget(dup_badge)
        if self.data.get("is_new") or self.data.get("신규여부"):
            new_badge = QLabel("NEW")
            new_badge.setStyleSheet("color: #f59e0b; font-weight: 800; font-size: 11px;")
            top_layout.addWidget(new_badge)
        price_change = self.data.get("price_change", 0)
        if isinstance(price_change, str):
            try:
                price_change = int(price_change.replace(",", "").replace("만", ""))
            except ValueError:
                price_change = 0
        if price_change > 0:
            change_badge = QLabel("▲")
            change_badge.setStyleSheet("color: #ef4444; font-weight: 800;")
            top_layout.addWidget(change_badge)
        elif price_change < 0:
            change_badge = QLabel("▼")
            change_badge.setStyleSheet("color: #22c55e; font-weight: 800;")
            top_layout.addWidget(change_badge)
        
        # 즐겨찾기 버튼
        theme_key = "dark" if self.is_dark else "light"
        accent = COLORS[theme_key]["accent"]
        self.fav_btn = QPushButton("★" if self.data.get("is_favorite") else "☆")
        self.fav_btn.setFixedSize(30, 30)
        self.fav_btn.setStyleSheet(
            f"border: none; font-size: 18px; background: transparent; color: {accent};"
        )
        self.fav_btn.clicked.connect(self._toggle_favorite)
        top_layout.addWidget(self.fav_btn)
        
        layout.addLayout(top_layout)
        
        # 단지명
        name_label = QLabel(self.data.get("단지명", ""))
        name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # 가격
        price_text = self.data.get("매매가") or self.data.get("보증금") or ""
        if self.data.get("월세"):
            price_text += f" / {self.data.get('월세')}"
        price_label = QLabel(price_text)
        price_label.setStyleSheet(f"color: {fg_color}; font-size: 18px; font-weight: 800;")
        layout.addWidget(price_label)

        # 가격 변동 텍스트
        if price_change != 0:
            sign = "+" if price_change > 0 else "-"
            change_text = PriceConverter.to_string(abs(price_change))
            change_label = QLabel(f"변동 {sign}{change_text}")
            change_color = "#ef4444" if price_change > 0 else "#22c55e"
            change_label.setStyleSheet(f"font-size: 11px; color: {change_color}; font-weight: 700;")
            layout.addWidget(change_label)
        
        # 면적 + 층/방향
        area = self.data.get("면적(평)", 0)
        floor = self.data.get("층/방향", "")
        info_label = QLabel(f"📐 {area}평  •  {floor}")
        info_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(info_label)
        
        # 평당가
        if self.data.get("평당가_표시"):
            pprice_label = QLabel(f"📊 {self.data.get('평당가_표시')}")
            pprice_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(pprice_label)

        # 특징 요약
        feature = self.data.get("타입/특징", "")
        if feature:
            feature_label = QLabel(feature[:30])
            feature_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
            feature_label.setWordWrap(True)
            layout.addWidget(feature_label)
        
        layout.addStretch()
    
    def _toggle_favorite(self):
        article_id = self.data.get("매물ID", "")
        complex_id = self.data.get("단지ID", "")
        asset_type = str(self.data.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        is_fav = self.fav_btn.text() == "☆"
        self.fav_btn.setText("★" if is_fav else "☆")
        self.favorite_toggled.emit(article_id, complex_id, asset_type, is_fav)
    
    def mousePressEvent(self, a0):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(a0)
