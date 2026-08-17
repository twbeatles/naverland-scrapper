"""
UI stylesheet facade.
"""

from src.ui.styles_parts.colors import COLORS
from src.ui.styles_parts.generator import _generate_stylesheet
from src.ui.styles_parts.surfaces import apply_theme_surfaces


def get_dark_stylesheet():
    return _generate_stylesheet("dark")


def get_light_stylesheet():
    return _generate_stylesheet("light")


def get_stylesheet(theme="dark"):
    return get_light_stylesheet() if theme == "light" else get_dark_stylesheet()
