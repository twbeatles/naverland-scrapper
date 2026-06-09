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
from src.ui.widgets.dashboard_parts.cards import ArticleCard


class CardViewWidget(QScrollArea):
    """카드 뷰 위젯 (v13.0)"""
    article_clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)
    
    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self._cards = []
        self._all_data = []
        self._search_text_cache = []
        self._filtered_data = []
        self._filter_text = ""
        self._card_width = 280
        self._card_spacing = 15
        self._page_size = 120
        self._render_cursor = 0
        self._last_columns = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.container = QWidget()
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.setWidget(self.container)

        self.empty_label = QLabel("조건에 맞는 매물이 없습니다.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 40px;")
        self.grid_layout.addWidget(self.empty_label, 0, 0)
        self.empty_label.hide()
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.valueChanged.connect(self._on_scroll)

    @staticmethod
    def _build_search_text(article: dict) -> str:
        if not isinstance(article, dict):
            return ""
        return " ".join(
            [
                str(article.get("단지명", "")),
                str(article.get("타입/특징", "")),
                str(article.get("거래유형", "")),
                str(article.get("매매가", "")),
                str(article.get("보증금", "")),
                str(article.get("월세", "")),
            ]
        ).lower()
    
    def set_data(self, articles: list):
        """매물 데이터를 카드로 표시"""
        self._all_data = list(articles) if articles else []
        self._search_text_cache = [self._build_search_text(a) for a in self._all_data]
        self._apply_filter(reset_view=True)

    def append_data(self, articles: list):
        """기존 데이터에 매물 추가 (실시간 배치 업데이트용)"""
        if not articles:
            return
        new_items = list(articles)
        self._all_data.extend(new_items)
        self._search_text_cache.extend(self._build_search_text(a) for a in new_items)

        if self._filter_text:
            # 필터가 켜져 있으면 정확성을 위해 재적용
            self._apply_filter(reset_view=True)
            return

        had_count = len(self._filtered_data)
        self._filtered_data.extend(new_items)
        self.empty_label.setVisible(False)

        if self._render_cursor >= had_count:
            self._render_next_page()

    def _calc_columns(self) -> int:
        viewport = self.viewport()
        available = max(1, viewport.width() if viewport is not None else self.width())
        cols = max(1, available // (self._card_width + self._card_spacing))
        return cols

    def _clear_cards(self):
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()
        self.grid_layout.setSpacing(self._card_spacing)
        self._render_cursor = 0
        self._last_columns = self._calc_columns()

    def _apply_filter(self, reset_view=False):
        text = (self._filter_text or "").lower()
        if text:
            self._filtered_data = [
                d for d, searchable in zip(self._all_data, self._search_text_cache)
                if text in searchable
            ]
        else:
            self._filtered_data = list(self._all_data)

        if reset_view:
            self._clear_cards()

        if not self._filtered_data:
            self._last_columns = None
            self.empty_label.show()
            return
        self.empty_label.hide()
        if reset_view:
            self._render_next_page()
        else:
            self._relayout_rendered_cards()

    def _on_scroll(self, value: int):
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is None:
            return
        if scroll_bar.maximum() <= 0:
            return
        if value >= (scroll_bar.maximum() - 220):
            self._render_next_page()

    def _relayout_rendered_cards(self):
        cols = self._calc_columns()
        if not self._cards:
            self._last_columns = cols
            return
        for i, card in enumerate(self._cards):
            row, col = divmod(i, cols)
            self.grid_layout.addWidget(card, row, col)
        self._last_columns = cols

    def _render_next_page(self):
        if self._render_cursor >= len(self._filtered_data):
            return
        cols = self._calc_columns()
        end = min(len(self._filtered_data), self._render_cursor + self._page_size)
        for i in range(self._render_cursor, end):
            article = self._filtered_data[i]
            card = ArticleCard(article, self.is_dark)
            card.clicked.connect(self.article_clicked.emit)
            card.favorite_toggled.connect(self.favorite_toggled.emit)

            row, col = divmod(i, cols)
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)
        self._render_cursor = end
        self._last_columns = cols

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        if self._filtered_data:
            cols = self._calc_columns()
            if cols != self._last_columns:
                self._relayout_rendered_cards()
    
    def filter_cards(self, text: str):
        """카드 필터링"""
        self._filter_text = text or ""
        self._apply_filter(reset_view=True)
