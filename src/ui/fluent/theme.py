"""Fluent theme helpers (primary theme source for the app shell).

srtgo/ktrain ``ktrain/gui/theme.py`` parity: OS 다크/라이트 연동이 기본이며,
Fluent component가 제공하는 스타일을 QSS로 다시 그리지 않는다.
PyQt6 바인딩은 유지한다 (DESKTOP_UI_DESIGN_RULES §1.1).
"""

from __future__ import annotations

from typing import Any

from qfluentwidgets import Theme, isDarkTheme, setTheme, setThemeColor

from src.ui.fluent.design_tokens import ACCENT_DARK, ACCENT_LIGHT

_POLL_MS = 3000


def theme_from_settings(theme_name: str | None) -> Theme:
    """저장된 설정값을 Theme enum으로. 미지정(신규 설치)은 OS 연동(AUTO)."""
    name = str(theme_name or "auto").strip().lower()
    if name == "light":
        return Theme.LIGHT
    if name == "dark":
        return Theme.DARK
    return Theme.AUTO


def apply_app_theme(theme_name: str | None = "auto", *, accent: str | None = None) -> Theme:
    """Apply qfluentwidgets theme. Returns the resolved Theme enum."""
    theme = theme_from_settings(theme_name)
    setTheme(theme)
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        if hints is not None and theme != Theme.AUTO:
            scheme = Qt.ColorScheme.Light if theme == Theme.LIGHT else Qt.ColorScheme.Dark
            hints.setColorScheme(scheme)
    except Exception:
        pass
    if accent:
        setThemeColor(accent)
    elif theme == Theme.LIGHT:
        setThemeColor(ACCENT_LIGHT)
    else:
        setThemeColor(ACCENT_DARK)
    return theme


def setup_app_theme(app: Any, theme_name: str | None = "auto") -> Theme:
    """QApplication 생성 직후, 윈도우 생성 전에 호출. OS 테마 변경을 추적한다."""
    theme = apply_app_theme(theme_name)
    _install_theme_watcher(app)
    return theme


def sync_system_theme() -> None:
    """OS 다크/라이트 설정을 qfluentwidgets에 반영 (AUTO 모드 전용 보정)."""
    try:
        import darkdetect

        system = darkdetect.theme()
    except Exception:
        return
    try:
        if system == "Dark":
            setTheme(Theme.DARK)
        elif system == "Light":
            setTheme(Theme.LIGHT)
    except Exception:
        pass


def _install_theme_watcher(app: Any) -> None:
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda _scheme: sync_system_theme())
        timer = QTimer(app)
        timer.timeout.connect(sync_system_theme)
        timer.start(_POLL_MS)
    except Exception:
        pass


def configure_fluent_window(window: Any) -> None:
    """FluentWindow 계열 — Mica/배경 깨짐 완화."""
    set_mica = getattr(window, "setMicaEffectEnabled", None)
    if callable(set_mica):
        try:
            set_mica(False)
        except Exception:
            pass


def apply_native_widget_style(root: Any) -> None:
    """QCheckBox·QListWidget 등 기본 Qt 위젯 다크모드 가독성 보정 (최소 범위)."""
    try:
        if isDarkTheme():
            root.setStyleSheet(
                root.styleSheet()
                + """
                QCheckBox, QLabel, QSpinBox, QDoubleSpinBox, QListWidget, QListWidget::item {
                    color: #E8E8E8;
                    background-color: transparent;
                }
                QSpinBox, QDoubleSpinBox, QListWidget {
                    background-color: #2B2B2B;
                    border: 1px solid #3E3E3E;
                    border-radius: 4px;
                    padding: 2px 4px;
                }
                QListWidget::item:selected {
                    background-color: #3A3A3A;
                }
                QTableWidget {
                    color: #E8E8E8;
                    background-color: #2B2B2B;
                    gridline-color: #3E3E3E;
                }
                QHeaderView::section {
                    color: #E8E8E8;
                    background-color: #333333;
                }
                """
            )
    except Exception:
        pass


def is_dark_theme(theme_name: str | None) -> bool:
    return theme_from_settings(theme_name) != Theme.LIGHT
