"""Fluent theme helpers (primary theme source for the app shell)."""

from __future__ import annotations

from typing import Any

from qfluentwidgets import Theme, setTheme, setThemeColor


def theme_from_settings(theme_name: str | None) -> Theme:
    name = str(theme_name or "dark").strip().lower()
    if name == "light":
        return Theme.LIGHT
    if name in {"auto", "system"}:
        return Theme.AUTO
    return Theme.DARK


def apply_app_theme(theme_name: str | None = "dark", *, accent: str | None = None) -> Theme:
    """Apply qfluentwidgets theme. Returns the resolved Theme enum."""
    theme = theme_from_settings(theme_name)
    setTheme(theme)
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        if hints is not None:
            scheme = Qt.ColorScheme.Light if theme == Theme.LIGHT else Qt.ColorScheme.Dark
            hints.setColorScheme(scheme)
    except Exception:
        pass
    # Amber accent aligns with the previous dark palette; sky-like for light is optional.
    if accent:
        setThemeColor(accent)
    elif theme == Theme.LIGHT:
        setThemeColor("#0ea5e9")
    else:
        setThemeColor("#f59e0b")
    return theme


def is_dark_theme(theme_name: str | None) -> bool:
    return theme_from_settings(theme_name) != Theme.LIGHT
