"""PyQt6-Fluent-Widgets helpers for the desktop shell."""

from src.ui.fluent.notify import show_info_bar
from src.ui.fluent.theme import apply_app_theme, theme_from_settings
from src.ui.fluent.tab_bridge import TabCompatBridge

__all__ = [
    "TabCompatBridge",
    "apply_app_theme",
    "show_info_bar",
    "theme_from_settings",
]
