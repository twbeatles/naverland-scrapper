"""Guard: rebind facade must expose symbols used by mixin free names."""

import unittest

import src.core.engines.playwright_engine as pe


REQUIRED_GLOBALS = (
    "HOST_NEW",
    "HOST_FIN",
    "HOST_M",
    "build_geo_map_url",
    "build_complex_page_url",
    "build_single_markers_url",
    "build_complex_overview_url",
    "viewport_bounds",
    "normalize_marker_payload",
    "normalize_article_payload",
    "apply_mobile_detail",
    "fetch_mobile_article_detail",
    "is_fin_html_dead_url",
    "build_grid_sweep_coords",
    "clamp_korea",
    # fin.land front-api path (2026-10-22)
    "DESKTOP_USER_AGENT",
    "FIN_API_ORIGIN_PAGE",
    "FRONT_API_COMPLEX_ARTICLE_LIST",
    "MAX_ARTICLE_API_PAGES",
    "build_fin_article_list_body",
    "parse_fin_article_list",
    "parse_fin_bounded_complexes",
    "parse_fin_complex_info",
    "build_fin_bounded_complexes_body",
    "build_fin_complex_info_url",
    "fin_article_list_url",
    "FRONT_API_BOUNDED_COMPLEXES",
    "trade_type_to_code",
)


class TestPlaywrightEngineGlobals(unittest.TestCase):
    def test_required_rebind_symbols_present(self):
        missing = [name for name in REQUIRED_GLOBALS if name not in pe.__dict__]
        self.assertEqual(missing, [], f"playwright_engine missing rebind globals: {missing}")

    def test_site_contract_builders_callable(self):
        self.assertTrue(callable(pe.build_geo_map_url))
        self.assertTrue(callable(pe.build_single_markers_url))
        url = pe.build_geo_map_url(
            base_kind="complexes",
            lat=37.5,
            lon=127.0,
            zoom=15,
            asset_type="APT",
            trade_type="매매",
        )
        self.assertIn("b=A1", url)
        self.assertNotIn("tradeTypes", url)


if __name__ == "__main__":
    unittest.main()
