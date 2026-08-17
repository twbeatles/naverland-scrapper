from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPalette, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.styles import COLORS
from src.ui.widgets.components import EmptyStateWidget
from src.utils.constants import TRADE_COLORS
from src.utils.helpers import PriceConverter


def _theme_key(is_dark: bool) -> str:
    return "dark" if is_dark else "light"


def _is_dark_theme(theme: str | None) -> bool:
    return str(theme or "dark").strip().lower() != "light"


class ArticleCard(QFrame):
    """매물 카드 위젯 (v13.0)"""

    clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)
    _CARD_STYLE_CACHE = {}
    _TYPE_STYLE_CACHE = {}
    _PRICE_STYLE_CACHE = {}
    _FAVORITE_STYLE_CACHE = {}

    def __init__(self, data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.data = data
        self.is_dark = is_dark
        self.setObjectName("articleCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._setup_ui()

    def _apply_card_chrome(self):
        trade_type = self.data.get("거래유형", "매매")
        colors = TRADE_COLORS.get(trade_type, TRADE_COLORS["매매"])
        fg_color = colors["dark_fg"] if self.is_dark else colors["fg"]
        theme_key = _theme_key(self.is_dark)
        palette = COLORS[theme_key]
        surface = palette.get("card_bg", "#1e1e2e" if self.is_dark else "#ffffff")
        hover_bg = palette.get("card_bg_hover", surface)
        border = palette.get("card_border", f"{fg_color}40")
        hover_border = palette.get("card_border_hover", fg_color)
        text_primary = palette["text_primary"]
        style_key = (surface, border, hover_border, fg_color, hover_bg, text_primary)
        card_style = self._CARD_STYLE_CACHE.get(style_key)
        if card_style is None:
            card_style = (
                "QFrame#articleCard {"
                f"background-color: {surface};"
                f"border: 1px solid {border};"
                f"border-top: 3px solid {fg_color};"
                "border-radius: 12px;"
                "padding: 12px;"
                "}"
                "QFrame#articleCard:hover {"
                f"border: 1px solid {hover_border};"
                f"border-top: 3px solid {fg_color};"
                f"background-color: {hover_bg};"
                "}"
                "QFrame#articleCard QLabel {"
                f"color: {text_primary};"
                "background: transparent;"
                "}"
            )
            self._CARD_STYLE_CACHE[style_key] = card_style
        self.setStyleSheet(card_style)
        fill = QColor(surface)
        if fill.isValid():
            widget_palette = self.palette()
            widget_palette.setColor(QPalette.ColorRole.Window, fill)
            widget_palette.setColor(QPalette.ColorRole.Base, fill)
            self.setPalette(widget_palette)
        return fg_color, palette

    def paintEvent(self, a0):
        theme_key = _theme_key(self.is_dark)
        palette = COLORS[theme_key]
        surface = QColor(palette.get("card_bg", "#ffffff" if not self.is_dark else "#1e1e2e"))
        border = QColor(palette.get("card_border", "#e2e8f0"))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        painter.fillPath(path, surface)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)
        painter.end()

    def _setup_ui(self):
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedSize(280, 210)

        fg_color, palette = self._apply_card_chrome()
        trade_type = self.data.get("거래유형", "매매")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_layout = QHBoxLayout()
        type_label = QLabel(trade_type)
        type_style = self._TYPE_STYLE_CACHE.get(fg_color)
        if type_style is None:
            type_style = (
                f"color: {fg_color}; background-color: {fg_color}22; padding: 4px 10px; "
                "border-radius: 999px; font-weight: 700; font-size: 11px;"
            )
            self._TYPE_STYLE_CACHE[fg_color] = type_style
        type_label.setStyleSheet(type_style)
        top_layout.addWidget(type_label)
        top_layout.addStretch()

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

        accent = palette["accent"]
        self.fav_btn = QPushButton("")
        self.fav_btn.setFixedSize(28, 28)
        self.fav_btn.setToolTip("즐겨찾기")
        fav_style = self._FAVORITE_STYLE_CACHE.get(accent)
        if fav_style is None:
            fav_style = (
                f"border: none; font-size: 16px; background: transparent; color: {accent};"
            )
            self._FAVORITE_STYLE_CACHE[accent] = fav_style
        self.fav_btn.setStyleSheet(fav_style)
        self.set_favorite_state(bool(self.data.get("is_favorite")))
        self.fav_btn.clicked.connect(self._toggle_favorite)
        top_layout.addWidget(self.fav_btn)

        layout.addLayout(top_layout)

        name_label = QLabel(self.data.get("단지명", ""))
        name_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; background: transparent; color: {palette['text_primary']};"
        )
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Lightweight one-line meta (동/타입명) — no broker phones on cards
        try:
            from src.core.managers import settings as _settings

            show_extra = bool(_settings.get("card_show_extra_meta", True))
        except Exception:
            show_extra = True
        if show_extra:
            meta_bits = [
                str(self.data.get("동", "") or "").strip(),
                str(self.data.get("타입명", "") or "").strip(),
                str(self.data.get("확인일", "") or "").strip(),
                str(self.data.get("부동산상호", "") or "").strip(),
            ]
            meta_line = " · ".join(bit for bit in meta_bits if bit)
            if meta_line:
                meta_label = QLabel(meta_line[:56])
                meta_label.setStyleSheet(
                    f"font-size: 11px; color: {palette['text_secondary']}; background: transparent;"
                )
                layout.addWidget(meta_label)

        price_text = self.data.get("매매가") or self.data.get("보증금") or ""
        if self.data.get("월세"):
            price_text += f" / {self.data.get('월세')}"
        price_label = QLabel(price_text)
        price_style = self._PRICE_STYLE_CACHE.get(fg_color)
        if price_style is None:
            price_style = (
                f"color: {fg_color}; font-size: 17px; font-weight: 800; background: transparent;"
            )
            self._PRICE_STYLE_CACHE[fg_color] = price_style
        price_label.setStyleSheet(price_style)
        layout.addWidget(price_label)

        if price_change != 0:
            sign = "+" if price_change > 0 else "-"
            change_text = PriceConverter.to_string(abs(price_change))
            change_label = QLabel(f"변동 {sign}{change_text}")
            change_color = "#ef4444" if price_change > 0 else "#22c55e"
            change_label.setStyleSheet(
                f"font-size: 11px; color: {change_color}; font-weight: 700; background: transparent;"
            )
            layout.addWidget(change_label)

        area = self.data.get("면적(평)", 0)
        floor = self.data.get("층/방향", "")
        info_bits = [f"{area}평"] if area not in (None, "", 0) else []
        if floor:
            info_bits.append(str(floor))
        info_label = QLabel(" · ".join(info_bits) if info_bits else "")
        info_label.setStyleSheet(
            f"font-size: 12px; color: {palette['text_secondary']}; background: transparent;"
        )
        if info_bits:
            layout.addWidget(info_label)

        if self.data.get("평당가_표시"):
            pprice_label = QLabel(str(self.data.get("평당가_표시")))
            pprice_label.setStyleSheet(
                f"font-size: 11px; color: {palette['text_secondary']}; background: transparent;"
            )
            layout.addWidget(pprice_label)

        feature = self.data.get("타입/특징", "")
        if feature:
            feature_label = QLabel(feature[:30])
            feature_label.setStyleSheet(
                f"font-size: 11px; color: {palette['text_secondary']}; background: transparent;"
            )
            feature_label.setWordWrap(True)
            layout.addWidget(feature_label)

        layout.addStretch()

    def set_favorite_state(self, is_favorite: bool):
        self.data["is_favorite"] = bool(is_favorite)
        self.fav_btn.setText("★" if is_favorite else "☆")

    def _toggle_favorite(self):
        article_id = self.data.get("매물ID", "")
        complex_id = self.data.get("단지ID", "")
        asset_type = str(self.data.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        is_fav = self.fav_btn.text() == "☆"
        self.set_favorite_state(is_fav)
        self.favorite_toggled.emit(article_id, complex_id, asset_type, is_fav)

    def mousePressEvent(self, a0):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(a0)


class CardViewWidget(QScrollArea):
    """카드 뷰 위젯 (v13.0)"""

    article_clicked = pyqtSignal(dict)
    favorite_toggled = pyqtSignal(str, str, str, bool)

    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self.setObjectName("cardView")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
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

        self.empty_label = EmptyStateWidget(
            icon="📭",
            title="조건에 맞는 매물이 없습니다",
            description="검색어·필터를 바꾸거나 수집을 다시 실행해 보세요.",
        )
        self.grid_layout.addWidget(self.empty_label, 0, 0)
        self.empty_label.hide()
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.valueChanged.connect(self._on_scroll)
        self._apply_surface_style()

    def _apply_surface_style(self):
        palette = COLORS[_theme_key(self.is_dark)]
        bg = palette.get("bg_primary", "#0f0f1a" if self.is_dark else "#f8fafc")
        self.setStyleSheet(
            f"QScrollArea#cardView {{ background-color: {bg}; border: none; }}"
            f"QScrollArea#cardView > QWidget {{ background-color: {bg}; }}"
        )
        if hasattr(self, "container"):
            self.container.setStyleSheet(f"background-color: {bg};")
        fill = QColor(bg)
        if fill.isValid():
            widget_palette = self.palette()
            widget_palette.setColor(QPalette.ColorRole.Window, fill)
            widget_palette.setColor(QPalette.ColorRole.Base, fill)
            self.setPalette(widget_palette)
            self.setAutoFillBackground(True)
            if hasattr(self, "container"):
                self.container.setAutoFillBackground(True)
                self.container.setPalette(widget_palette)

    def set_theme(self, theme: str) -> None:
        self.is_dark = _is_dark_theme(theme)
        self._apply_surface_style()
        if self._all_data:
            self._apply_filter(reset_view=True)

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
        self._all_data = list(articles) if articles else []
        self._search_text_cache = [self._build_search_text(a) for a in self._all_data]
        self._apply_filter(reset_view=True)

    def append_data(self, articles: list):
        if not articles:
            return
        new_items = list(articles)
        self._all_data.extend(new_items)
        self._search_text_cache.extend(self._build_search_text(a) for a in new_items)

        if self._filter_text:
            self._apply_filter(reset_view=True)
            return

        had_count = len(self._filtered_data)
        self._filtered_data.extend(new_items)
        self.empty_label.setVisible(False)

        if self._render_cursor >= had_count:
            self._render_next_page()

    def update_favorite_state(self, predicate, state_provider):
        if not callable(predicate) or not callable(state_provider):
            return

        changed = False
        for article in self._all_data:
            try:
                if not predicate(article):
                    continue
            except Exception:
                continue
            article["is_favorite"] = bool(state_provider(article))
            changed = True

        if not changed:
            return

        for card in self._cards:
            try:
                if predicate(card.data):
                    card.set_favorite_state(bool(state_provider(card.data)))
            except Exception:
                continue

    def _calc_columns(self) -> int:
        viewport = self.viewport()
        available = max(1, viewport.width() if viewport is not None else self.width())
        return max(1, available // (self._card_width + self._card_spacing))

    def _clear_cards(self):
        self.container.setUpdatesEnabled(False)
        try:
            for card in self._cards:
                card.deleteLater()
            self._cards.clear()
            self.grid_layout.setSpacing(self._card_spacing)
            self._render_cursor = 0
            self._last_columns = self._calc_columns()
        finally:
            self.container.setUpdatesEnabled(True)

    def _apply_filter(self, reset_view=False):
        text = (self._filter_text or "").lower()
        if text:
            self._filtered_data = [
                d for d, searchable in zip(self._all_data, self._search_text_cache) if text in searchable
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
        if scroll_bar is None or scroll_bar.maximum() <= 0:
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
        self.container.setUpdatesEnabled(False)
        try:
            for i in range(self._render_cursor, end):
                article = self._filtered_data[i]
                card = ArticleCard(article, self.is_dark)
                card.clicked.connect(self.article_clicked.emit)
                card.favorite_toggled.connect(self.favorite_toggled.emit)

                row, col = divmod(i, cols)
                self.grid_layout.addWidget(card, row, col)
                self._cards.append(card)
        finally:
            self.container.setUpdatesEnabled(True)
        self._render_cursor = end
        self._last_columns = cols

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        if self._filtered_data:
            cols = self._calc_columns()
            if cols != self._last_columns:
                self._relayout_rendered_cards()

    def filter_cards(self, text: str):
        self._filter_text = text or ""
        self._apply_filter(reset_view=True)
