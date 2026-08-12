import unittest
from urllib.parse import parse_qs, urlparse

from src.core.services.map_geometry import viewport_bounds
from src.core.services.site_contract import (
    GEO_QUERY_TRADE,
    build_complex_page_url,
    build_geo_map_url,
    build_single_markers_url,
    is_fin_html_dead_url,
    trade_type_to_code,
)


class TestSiteContract(unittest.TestCase):
    def test_trade_type_to_code(self):
        self.assertEqual(trade_type_to_code("매매"), "A1")
        self.assertEqual(trade_type_to_code("전세"), "B1")
        self.assertEqual(trade_type_to_code("월세"), "B2")

    def test_geo_map_url_uses_b_not_trade_types(self):
        url = build_geo_map_url(
            base_kind="complexes",
            lat=37.55,
            lon=126.98,
            zoom=15,
            asset_type="APT",
            trade_type="매매",
        )
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertIn("new.land.naver.com/complexes", url)
        self.assertEqual(qs.get(GEO_QUERY_TRADE), ["A1"])
        self.assertNotIn("tradeTypes", qs)
        self.assertEqual(qs.get("a"), ["APT:ABYG:JGC"])
        self.assertEqual(qs.get("e"), ["RETAIL"])

    def test_geo_map_url_vl_uses_houses(self):
        url = build_geo_map_url(
            base_kind="houses",
            lat=37.5,
            lon=127.0,
            zoom=16,
            asset_type="VL",
            trade_type="전세",
        )
        self.assertIn("/houses?", url)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("b"), ["B1"])
        self.assertIn("VL", qs.get("a", [""])[0])

    def test_complex_page_url_includes_b_and_retail(self):
        url = build_complex_page_url("3833", trade_type="월세", path_asset="APT")
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("b"), ["B2"])
        self.assertEqual(qs.get("e"), ["RETAIL"])
        self.assertIn("3833", url)

    def test_fin_html_dead_detection(self):
        self.assertTrue(
            is_fin_html_dead_url(
                "https://financial.pstatic.net/404.html?url=https://fin.land.naver.com/"
            )
        )
        self.assertTrue(
            is_fin_html_dead_url(
                "https://fin.land.naver.com/articles/1",
                "요청하신 페이지를 찾을 수 없어요",
            )
        )
        self.assertFalse(is_fin_html_dead_url("https://new.land.naver.com/complexes/3833", "매물"))

    def test_single_markers_url_uses_trade_type_singular(self):
        bounds = viewport_bounds(37.55, 126.98, 15)
        url = build_single_markers_url(
            asset_type="APT",
            trade_type="매매",
            zoom=15,
            left_lon=bounds["leftLon"],
            right_lon=bounds["rightLon"],
            top_lat=bounds["topLat"],
            bottom_lat=bounds["bottomLat"],
        )
        self.assertIn("single-markers/2.0", url)
        self.assertIn("tradeType=A1", url)
        self.assertIn("realEstateType=", url)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("priceType"), ["RETAIL"])


if __name__ == "__main__":
    unittest.main()
