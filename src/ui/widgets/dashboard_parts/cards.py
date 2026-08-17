"""Dashboard stat cards. Article cards live in src.ui.widgets.cards."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.ui.styles import COLORS

# Keep public re-export path stable for dashboard facade / older imports.
from src.ui.widgets.cards import ArticleCard  # noqa: F401


class StatCard(QFrame):
    """대시보드 KPI 카드 (Fluent-like surface)."""

    def __init__(
        self,
        title: str = "",
        value: str = "0",
        color: str = "#3b82f6",
        theme: str = "dark",
        parent=None,
    ):
        super().__init__(parent)
        self._color = color
        self._theme = theme
        self._value_label: Optional[QLabel] = None
        self._title_label: Optional[QLabel] = None
        self.setObjectName("statCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self.setMinimumWidth(160)
        self.setMinimumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("statCardTitle")
        layout.addWidget(self._title_label)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("statCardValue")
        layout.addWidget(self._value_label)
        layout.addStretch(1)
        self._apply_style()

    def set_value(self, text: str) -> None:
        if self._value_label is not None:
            self._value_label.setText(str(text))

    def set_title(self, text: str) -> None:
        if self._title_label is not None:
            self._title_label.setText(str(text))

    def set_theme(self, theme: str) -> None:
        self._theme = str(theme or "dark")
        self._apply_style()

    def _apply_style(self) -> None:
        c = COLORS.get(self._theme, COLORS["dark"])
        color = self._color
        self.setStyleSheet(
            f"""
            QFrame#statCard {{
                background-color: {c.get("stat_card_bg", c["bg_card"])};
                border: 1px solid {color}55;
                border-left: 4px solid {color};
                border-radius: 12px;
            }}
            QFrame#statCard:hover {{
                border: 1px solid {color}99;
                border-left: 4px solid {color};
                background-color: {color}18;
            }}
            QLabel#statCardTitle {{
                font-size: 12px;
                font-weight: 600;
                color: {c["text_secondary"]};
                background: transparent;
                border: none;
            }}
            QLabel#statCardValue {{
                font-size: 28px;
                font-weight: 800;
                color: {color};
                letter-spacing: -0.5px;
                background: transparent;
                border: none;
            }}
            """
        )
