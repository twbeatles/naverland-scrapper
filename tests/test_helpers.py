import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.helpers import (
    build_article_url,
    build_complex_url,
    get_article_url,
    get_complex_url,
)


class TestURLHelpers(unittest.TestCase):
    def test_build_complex_url_keeps_complex_deeplink_default(self):
        self.assertEqual(
            build_complex_url("12345"),
            "https://new.land.naver.com/complexes/12345",
        )
        self.assertEqual(
            build_complex_url("54321", asset_type="VL"),
            "https://new.land.naver.com/houses/54321",
        )

    def test_build_article_url_defaults_to_fin_family(self):
        self.assertEqual(
            build_article_url("2513105556", complex_id="12345", asset_type="APT"),
            "https://fin.land.naver.com/articles/2513105556",
        )
        self.assertEqual(
            build_article_url("999999999", complex_id="654321", asset_type="VL", preferred_family="new"),
            "https://new.land.naver.com/houses/654321?articleId=999999999",
        )

    def test_legacy_helper_wrappers_remain_compatible(self):
        self.assertEqual(
            get_complex_url("12345"),
            "https://new.land.naver.com/complexes/12345",
        )
        self.assertEqual(
            get_article_url("12345", "2513105556", "APT"),
            "https://fin.land.naver.com/articles/2513105556",
        )


if __name__ == "__main__":
    unittest.main()
