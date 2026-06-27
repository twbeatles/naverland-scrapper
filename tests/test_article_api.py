import unittest

from src.core.services.article_api import (
    DEFAULT_ARTICLE_API_PAGE_SIZE,
    MAX_ARTICLE_API_PAGES,
    article_api_has_more_pages,
    article_api_path_kind,
    article_api_real_estate_type,
    build_article_api_query_params,
    build_article_api_url,
)


class TestArticleApiHelpers(unittest.TestCase):
    def test_path_kind_maps_houses_to_house(self):
        self.assertEqual(article_api_path_kind("houses"), "house")
        self.assertEqual(article_api_path_kind("complexes"), "complex")

    def test_real_estate_type_for_vl(self):
        self.assertEqual(article_api_real_estate_type("VL"), "VL:DDDGG:JWJT:SGJT")

    def test_build_url_includes_page_param(self):
        url = build_article_api_url("complexes", "3833", "매매", "APT", page=2)
        self.assertIn("/api/articles/complex/3833?", url)
        self.assertIn("page=2", url)
        self.assertIn("tradeType=A1", url)
        self.assertIn("realEstateType=APT%3AABYG%3AJGC", url)

    def test_query_params_default_page_is_one(self):
        params = build_article_api_query_params("전세", "APT")
        self.assertEqual(params["page"], "1")
        self.assertEqual(params["tradeType"], "B1")

    def test_has_more_pages_prefers_is_more_data_flag(self):
        self.assertFalse(article_api_has_more_pages({"isMoreData": False, "articleList": []}, 20))
        self.assertTrue(article_api_has_more_pages({"isMoreData": True, "articleList": []}, 1))

    def test_has_more_pages_falls_back_to_page_size(self):
        self.assertTrue(
            article_api_has_more_pages({"articleList": [{}] * DEFAULT_ARTICLE_API_PAGE_SIZE}, DEFAULT_ARTICLE_API_PAGE_SIZE)
        )
        self.assertFalse(
            article_api_has_more_pages({"articleList": [{}] * 3}, 3, page_size=DEFAULT_ARTICLE_API_PAGE_SIZE)
        )

    def test_safety_cap_constant_is_reasonable(self):
        self.assertGreaterEqual(MAX_ARTICLE_API_PAGES, 5)


if __name__ == "__main__":
    unittest.main()