import importlib.util
import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


SURFACE_KEYS = (
    "bg_primary",
    "bg_secondary",
    "bg_card",
    "card_bg",
    "card_bg_hover",
    "summary_bg",
    "stat_card_bg",
    "bg_table",
    "bg_input",
)


def _channel_luminance(color: str) -> float:
    token = str(color or "").strip().lower()
    if token.startswith("rgba") or token.startswith("rgb"):
        nums = [float(part) for part in re.findall(r"[\d.]+", token)[:3]]
        if len(nums) < 3:
            raise AssertionError(f"unparsable color: {color}")
        red, green, blue = nums
    elif token.startswith("#"):
        hex_body = token[1:]
        if len(hex_body) == 3:
            hex_body = "".join(ch * 2 for ch in hex_body)
        if len(hex_body) < 6:
            raise AssertionError(f"unparsable color: {color}")
        red = int(hex_body[0:2], 16)
        green = int(hex_body[2:4], 16)
        blue = int(hex_body[4:6], 16)
    else:
        raise AssertionError(f"unparsable color: {color}")
    return (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0


class TestThemeColorSets(unittest.TestCase):
    def test_light_and_dark_share_the_same_token_keys(self):
        from src.ui.styles_parts.colors import COLORS

        self.assertEqual(set(COLORS["dark"]), set(COLORS["light"]))

    def test_surface_tokens_have_theme_appropriate_luminance(self):
        from src.ui.styles_parts.colors import COLORS

        for key in SURFACE_KEYS:
            light_lum = _channel_luminance(COLORS["light"][key])
            dark_lum = _channel_luminance(COLORS["dark"][key])
            self.assertGreater(
                light_lum,
                0.72,
                f"light {key}={COLORS['light'][key]} should be a light surface",
            )
            self.assertLess(
                dark_lum,
                0.35,
                f"dark {key}={COLORS['dark'][key]} should be a dark surface",
            )

    def test_text_tokens_contrast_against_their_surfaces(self):
        from src.ui.styles_parts.colors import COLORS

        self.assertLess(_channel_luminance(COLORS["light"]["text_primary"]), 0.35)
        self.assertGreater(_channel_luminance(COLORS["dark"]["text_primary"]), 0.70)


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestArticleCardTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def _sample(self):
        return {
            "단지명": "테스트단지",
            "거래유형": "매매",
            "매매가": "10억",
            "면적(평)": 30,
            "층/방향": "10/남",
            "타입/특징": "대단지",
        }

    def test_light_article_card_uses_light_surface_and_object_name(self):
        from src.ui.styles_parts.colors import COLORS
        from src.ui.widgets.cards import ArticleCard

        card = ArticleCard(self._sample(), is_dark=False)
        sheet = card.styleSheet()
        self.assertEqual(card.objectName(), "articleCard")
        self.assertIn(COLORS["light"]["card_bg"], sheet)
        self.assertNotIn("rgba(30, 30, 46", sheet)
        self.assertIn(COLORS["light"]["text_primary"], sheet)
        card.deleteLater()

    def test_dark_article_card_keeps_dark_surface(self):
        from src.ui.styles_parts.colors import COLORS
        from src.ui.widgets.cards import ArticleCard

        card = ArticleCard(self._sample(), is_dark=True)
        sheet = card.styleSheet()
        self.assertIn(COLORS["dark"]["card_bg"], sheet)
        self.assertNotIn(COLORS["light"]["card_bg"], sheet)
        card.deleteLater()

    def test_card_view_set_theme_rebuilds_cards_for_light_mode(self):
        from src.ui.styles_parts.colors import COLORS
        from src.ui.widgets.cards import CardViewWidget

        view = CardViewWidget(is_dark=True)
        view.resize(900, 400)
        view.set_data([self._sample()])
        self.assertTrue(view._cards)
        self.assertIn(COLORS["dark"]["card_bg"], view._cards[0].styleSheet())

        view.set_theme("light")
        self.assertFalse(view.is_dark)
        self.assertTrue(view._cards)
        self.assertIn(COLORS["light"]["card_bg"], view._cards[0].styleSheet())
        view.deleteLater()

    def test_light_article_card_enables_styled_background_and_paints_light_pixel(self):
        from PyQt6.QtCore import Qt
        from src.ui.styles_parts.colors import COLORS
        from src.ui.widgets.cards import ArticleCard

        card = ArticleCard(self._sample(), is_dark=False)
        card.resize(280, 210)
        self._qt_app.processEvents()
        self.assertTrue(card.testAttribute(Qt.WidgetAttribute.WA_StyledBackground))
        img = card.grab().toImage()
        pixel = img.pixelColor(24, 36)
        self.assertGreater(
            (0.299 * pixel.red() + 0.587 * pixel.green() + 0.114 * pixel.blue()) / 255.0,
            0.72,
            f"light card pixel {pixel.name()} should be a light surface",
        )
        self.assertEqual(pixel.name().lower(), COLORS["light"]["card_bg"].lower())
        card.deleteLater()

    def test_crawler_set_theme_forces_light_groupbox_surfaces(self):
        import tempfile
        from src.core.database import ComplexDatabase
        from src.ui.styles_parts.colors import COLORS
        from src.ui.styles_parts.surfaces import apply_theme_surfaces
        from src.ui.widgets.crawler_tab import CrawlerTab
        from PyQt6.QtWidgets import QGroupBox

        with tempfile.TemporaryDirectory() as tmp:
            db = ComplexDatabase(os.path.join(tmp, "theme_cards.db"))
            tab = CrawlerTab(db, theme="dark")
            apply_theme_surfaces(tab, "light")
            boxes = tab.findChildren(QGroupBox)
            self.assertTrue(boxes)
            for box in boxes:
                self.assertIn(COLORS["light"]["bg_card"], box.styleSheet())
            db.close()
            tab.deleteLater()
