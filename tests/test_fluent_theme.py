"""Fluent theme + design token contract (DESKTOP_UI_DESIGN_RULES §5/§8)."""

import importlib.util
import os
import unittest

# Ensure headless-friendly Qt platform for CI runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestFluentTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_theme_from_settings_mapping(self):
        from qfluentwidgets import Theme

        from src.ui.fluent.theme import theme_from_settings

        self.assertEqual(theme_from_settings("dark"), Theme.DARK)
        self.assertEqual(theme_from_settings("light"), Theme.LIGHT)
        self.assertEqual(theme_from_settings("auto"), Theme.AUTO)
        self.assertEqual(theme_from_settings("system"), Theme.AUTO)

    def test_apply_app_theme_resolves_and_applies(self):
        from qfluentwidgets import Theme

        from src.ui.fluent.theme import apply_app_theme

        self.assertEqual(apply_app_theme("dark"), Theme.DARK)
        self.assertEqual(apply_app_theme("light"), Theme.LIGHT)
        self.assertEqual(apply_app_theme("auto"), Theme.AUTO)
        # Existing stored default keeps working.
        self.assertEqual(apply_app_theme("dark"), Theme.DARK)

    def test_setup_app_theme_installs_watcher(self):
        from qfluentwidgets import Theme

        from src.ui.fluent.theme import setup_app_theme

        theme = setup_app_theme(self._qt_app, "dark")
        self.assertEqual(theme, Theme.DARK)
        # A second call must not duplicate-fail (timer re-install is idempotent).
        self.assertEqual(setup_app_theme(self._qt_app, "dark"), Theme.DARK)
        self._qt_app.processEvents()


class TestDesignTokens(unittest.TestCase):
    def test_spacing_scale(self):
        from src.ui.fluent import design_tokens as t

        self.assertEqual(
            (t.SPACE_XXS, t.SPACE_XS, t.SPACE_SM, t.SPACE_MD, t.SPACE_LG, t.SPACE_XL),
            (4, 8, 12, 16, 24, 32),
        )
        self.assertEqual(t.PAGE_MARGIN, 24)
        self.assertEqual(t.SECTION_GAP, 24)
        self.assertEqual(t.CARD_RADIUS, 8)

    def test_preferred_window_size_clamps_to_available_geometry(self):
        from src.ui.fluent.design_tokens import (
            MIN_WINDOW_HEIGHT,
            MIN_WINDOW_WIDTH,
            preferred_window_size,
        )

        w, h = preferred_window_size(1920, 1080)
        self.assertLessEqual(w, 1920)
        self.assertLessEqual(h, 1080)
        w_small, h_small = preferred_window_size(800, 600)
        self.assertGreaterEqual(w_small, MIN_WINDOW_WIDTH)
        self.assertGreaterEqual(h_small, MIN_WINDOW_HEIGHT)

    def test_secondary_color_helpers_use_semantic_tokens(self):
        from src.ui.fluent.design_tokens import (
            TEXT_SECONDARY_DARK,
            TEXT_SECONDARY_LIGHT,
            empty_state_qss,
            secondary_label_qss,
            secondary_text_color,
        )

        self.assertEqual(secondary_text_color("dark"), TEXT_SECONDARY_DARK)
        self.assertEqual(secondary_text_color("light"), TEXT_SECONDARY_LIGHT)
        self.assertIn(TEXT_SECONDARY_DARK, secondary_label_qss("dark"))
        self.assertIn(TEXT_SECONDARY_LIGHT, empty_state_qss("light", padding=40))


def _close_app_window(w, qt_app):
    if hasattr(w, "schedule_timer") and w.schedule_timer:
        w.schedule_timer.stop()
    if hasattr(w, "tray_icon") and w.tray_icon:
        w.tray_icon.hide()
    if hasattr(w, "db") and w.db:
        w.db.close()
    w.deleteLater()
    qt_app.processEvents()


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestNavigationExpanded(unittest.TestCase):
    """Left navigation must start expanded with labels (srtgo parity)."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _make_window(self, theme):
        from src.core.managers import settings

        settings.set("theme", theme)
        from src.ui.app import RealEstateApp

        w = RealEstateApp()
        w.resize(1200, 800)
        w.show()
        self._qt_app.processEvents()
        self.addCleanup(_close_app_window, w, self._qt_app)
        return w

    def test_nav_expanded_dark(self):
        from qfluentwidgets import NavigationDisplayMode

        w = self._make_window("dark")
        nav = w.navigationInterface
        self.assertGreaterEqual(nav.width(), 200)
        self.assertEqual(nav.panel.displayMode, NavigationDisplayMode.EXPAND)

    def test_nav_expanded_light(self):
        from qfluentwidgets import NavigationDisplayMode

        w = self._make_window("light")
        nav = w.navigationInterface
        self.assertGreaterEqual(nav.width(), 200)
        self.assertEqual(nav.panel.displayMode, NavigationDisplayMode.EXPAND)

    def test_nav_labels_present(self):
        w = self._make_window("light")
        items = w.navigationInterface.panel.items
        from src.ui.fluent.navigation import ROUTE_CRAWLER, ROUTE_SETTINGS
        self.assertIn(ROUTE_CRAWLER, items)
        self.assertIn(ROUTE_SETTINGS, items)
        text_of = lambda w: getattr(w, "text", lambda: "")()
        labels = [text_of(entry.widget) for entry in items.values()]
        self.assertIn("매물 수집", labels)
        self.assertIn("설정", labels)


if __name__ == "__main__":
    unittest.main()
