"""Force opaque surfaces on native widgets.

Windows styles often ignore QSS ``background-color`` on QFrame / QGroupBox
unless ``WA_StyledBackground`` is set and the palette Window/Base roles match.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QListWidget,
    QScrollArea,
    QTableWidget,
    QWidget,
)

from src.ui.styles_parts.colors import COLORS


def _fill_widget(widget: QWidget, color: QColor) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, color)
    palette.setColor(QPalette.ColorRole.Base, color)
    palette.setColor(QPalette.ColorRole.Button, color)
    widget.setPalette(palette)


def apply_theme_surfaces(root: QWidget, theme: str) -> None:
    """Paint crawler/geo panel cards with the active theme's opaque tokens."""
    token = theme if theme in COLORS else "dark"
    colors = COLORS[token]
    page = QColor(colors["bg_primary"])
    card = QColor(colors["bg_card"])
    table = QColor(colors["bg_table"])

    _fill_widget(root, page)

    group_qss = (
        f"QGroupBox {{"
        f"background-color: {colors['bg_card']};"
        f"color: {colors['text_primary']};"
        f"border: 1px solid {colors['border_subtle']};"
        f"border-radius: 12px;"
        f"margin-top: 0.8em;"
        f"padding: 10px;"
        f"padding-top: 22px;"
        f"font-weight: 600;"
        f"}}"
        f"QGroupBox::title {{"
        f"subcontrol-origin: margin;"
        f"subcontrol-position: top left;"
        f"padding: 4px 12px;"
        f"color: {colors['accent']};"
        f"background: transparent;"
        f"font-weight: 700;"
        f"}}"
    )
    for box in root.findChildren(QGroupBox):
        box.setStyleSheet(group_qss)
        _fill_widget(box, card)

    list_qss = (
        f"QListWidget {{"
        f"background-color: {colors['bg_table']};"
        f"color: {colors['text_primary']};"
        f"border: 1px solid {colors['border_subtle']};"
        f"border-radius: 8px;"
        f"}}"
    )
    for lst in root.findChildren(QListWidget):
        lst.setStyleSheet(list_qss)
        _fill_widget(lst, table)

    table_qss = (
        f"QTableWidget {{"
        f"background-color: {colors['bg_table']};"
        f"color: {colors['text_primary']};"
        f"alternate-background-color: {colors['bg_table_alt']};"
        f"gridline-color: {colors['border_faint']};"
        f"}}"
    )
    for tbl in root.findChildren(QTableWidget):
        existing = tbl.styleSheet() or ""
        if "QTableWidget {" not in existing:
            tbl.setStyleSheet(table_qss)
        _fill_widget(tbl, table)

    for frame in root.findChildren(QFrame):
        name = frame.objectName()
        if name in {"articleCard", "summaryCard", "statCard"}:
            _fill_widget(frame, card)

    for scroll in root.findChildren(QScrollArea):
        _fill_widget(scroll, page)
        inner = scroll.widget()
        if inner is not None:
            _fill_widget(inner, page)
