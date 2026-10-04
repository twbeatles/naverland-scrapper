"""Keyword search service tests (live fixtures captured 2026-10-04)."""

import json
import unittest
from urllib.parse import parse_qs, urlparse

from src.core.services.keyword_search import (
    KeywordSearchError,
    fetch_search_page,
    fetch_suggestions,
    is_rate_limit_error,
    parse_autocomplete_payload,
    parse_search_complexes,
    parse_search_has_more,
    parse_search_regions,
    strip_autocomplete_highlight,
)
from src.core.services.site_contract import (
    build_autocomplete_url,
    build_cortars_url,
    build_search_url,
)

# Live fixture: GET /api/autocomplete?keyword=반포자이 (status 200).
AUTOCOMPLETE_BANPO_RAW = (
    '["<strong class=\'text_input\'>반포</strong>동 '
    '<strong class=\'text_input\'>반포</strong>'
    "<strong class='text_input'>자이</strong>\","
    '"잠원동 메이플<strong class=\'text_input\'>자이</strong>",'
    '"잠원동 <strong class=\'text_input\'>반포</strong>센트럴'
    "<strong class='text_input'>자이</strong>\","
    '"잠원동 신<strong class=\'text_input\'>반포</strong>'
    "<strong class='text_input'>자이</strong>\"]"
)

# Live fixture: GET /api/search?keyword=반포자이&page=1 (status 200, trimmed
# to two complexes; tail flags preserved verbatim).
SEARCH_BANPO_RAW = json.dumps(
    {
        "complexes": [
            {
                "complexNo": "22853",
                "complexName": "반포자이",
                "cortarNo": "1165010700",
                "realEstateTypeCode": "APT",
                "realEstateTypeName": "아파트",
                "latitude": 37.507784,
                "longitude": 127.014484,
                "totalHouseholdCount": 3410,
                "cortarAddress": "서울시 서초구 반포동",
                "deepLink": "/complexes/22853?&a=APT:ABYG:JGC",
                "useYn": "Y",
            },
            {
                "complexNo": "168097",
                "complexName": "메이플자이",
                "cortarNo": "1165010600",
                "realEstateTypeCode": "APT",
                "realEstateTypeName": "아파트",
                "latitude": 37.51158,
                "longitude": 127.013089,
                "totalHouseholdCount": 3307,
                "cortarAddress": "서울시 서초구 잠원동",
                "deepLink": "/complexes/168097?&a=APT:ABYG:JGC",
                "useYn": "Y",
            },
        ],
        "isShown": True,
        "isMoreData": False,
        "keyword": "반포자이",
        "totalCount": 0,
    },
    ensure_ascii=False,
)

# Live fixture: regions slice of GET /api/search?keyword=합정동&page=1.
SEARCH_HAPJEONG_REGIONS = {
    "complexes": [],
    "regions": [
        {
            "cortarNo": "1144012200",
            "centerLat": 37.549433,
            "centerLon": 126.905725,
            "cortarName": "서울시 마포구 합정동",
            "cortarType": "sec",
            "deepLink": "/complexes?ms=37.549433,126.905725,16&e=RETAIL",
        }
    ],
    "isShown": True,
    "isMoreData": True,
    "keyword": "합정동",
    "totalCount": 0,
}

# Live fixture: GET /api/search?keyword=empty-query-zzz&page=1 (status 200).
SEARCH_EMPTY_RAW = '{"isShown":false,"isMoreData":false,"keyword":"empty-query-zzz","totalCount":0}'


class TestKeywordSearchContract(unittest.TestCase):
    def test_autocomplete_url_encodes_keyword(self):
        url = build_autocomplete_url("래미안")
        self.assertIn("/api/autocomplete", url)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("keyword"), ["래미안"])

    def test_search_url_has_page(self):
        url = build_search_url("반포자이", page=2)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("keyword"), ["반포자이"])
        self.assertEqual(qs.get("page"), ["2"])

    def test_search_url_page_floor(self):
        qs = parse_qs(urlparse(build_search_url("a", page=0)).query)
        self.assertEqual(qs.get("page"), ["1"])

    def test_cortars_url(self):
        url = build_cortars_url(zoom=16, center_lat=37.5, center_lon=127.0)
        self.assertIn("/api/cortars", url)
        qs = parse_qs(urlparse(url).query)
        self.assertEqual(qs.get("zoom"), ["16"])
        self.assertEqual(qs.get("centerLat"), ["37.5"])


class TestKeywordSearchParsing(unittest.TestCase):
    def test_strip_highlight(self):
        self.assertEqual(
            strip_autocomplete_highlight("약사동 <strong class='text_input'>래미안</strong>2단지"),
            "약사동 래미안2단지",
        )
        self.assertEqual(strip_autocomplete_highlight("plain"), "plain")

    def test_parse_autocomplete_live(self):
        suggestions = parse_autocomplete_payload(AUTOCOMPLETE_BANPO_RAW)
        self.assertEqual(len(suggestions), 4)
        self.assertIn("반포동 반포자이", suggestions)
        self.assertIn("잠원동 메이플자이", suggestions)
        self.assertTrue(all("<" not in s for s in suggestions))

    def test_parse_autocomplete_empty(self):
        self.assertEqual(parse_autocomplete_payload("[]"), [])
        self.assertEqual(parse_autocomplete_payload({}), [])
        self.assertEqual(parse_autocomplete_payload("not json"), [])

    def test_parse_search_complexes_live(self):
        complexes = parse_search_complexes(json.loads(SEARCH_BANPO_RAW))
        self.assertEqual(len(complexes), 2)
        first = complexes[0]
        self.assertEqual(first["complex_id"], "22853")
        self.assertEqual(first["name"], "반포자이")
        self.assertEqual(first["address"], "서울시 서초구 반포동")
        self.assertEqual(first["asset_type"], "APT")
        self.assertAlmostEqual(first["latitude"], 37.507784)

    def test_parse_search_missing_keys(self):
        self.assertEqual(parse_search_complexes(json.loads(SEARCH_EMPTY_RAW)), [])
        self.assertEqual(parse_search_complexes({}), [])
        self.assertEqual(parse_search_complexes([]), [])

    def test_parse_search_regions_live(self):
        regions = parse_search_regions(SEARCH_HAPJEONG_REGIONS)
        self.assertEqual(len(regions), 1)
        region = regions[0]
        self.assertEqual(region["cortar_no"], "1144012200")
        self.assertAlmostEqual(region["latitude"], 37.549433)
        self.assertAlmostEqual(region["longitude"], 126.905725)

    def test_parse_search_regions_missing(self):
        self.assertEqual(parse_search_regions(json.loads(SEARCH_EMPTY_RAW)), [])

    def test_parse_search_has_more(self):
        self.assertTrue(parse_search_has_more(SEARCH_HAPJEONG_REGIONS))
        self.assertFalse(parse_search_has_more(json.loads(SEARCH_BANPO_RAW)))
        self.assertFalse(parse_search_has_more({}))


class TestKeywordSearchFetch(unittest.TestCase):
    def _ok(self, body):
        return lambda url: (200, body)

    def test_fetch_suggestions_uses_parser(self):
        names = fetch_suggestions("반포자이", self._ok(AUTOCOMPLETE_BANPO_RAW))
        self.assertEqual(len(names), 4)

    def test_fetch_suggestions_empty_keyword_skips_network(self):
        calls = []
        names = fetch_suggestions(
            "  ", lambda url: (calls.append(url), (200, "[]"))[1]
        )
        self.assertEqual(names, [])
        self.assertEqual(calls, [])

    def test_fetch_suggestions_non_200_raises(self):
        with self.assertRaises(KeywordSearchError) as ctx:
            fetch_suggestions("a", lambda url: (429, ""))
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.keyword, "a")

    def test_fetch_suggestions_error_distinguishes_empty(self):
        # Empty keyword is not an error; transport failure is.
        self.assertEqual(fetch_suggestions("  ", lambda url: (200, "[]")), [])
        with self.assertRaises(KeywordSearchError):
            fetch_suggestions("a", lambda url: (500, "oops"))

    def test_fetch_search_page_live(self):
        result = fetch_search_page("반포자이", self._ok(SEARCH_BANPO_RAW), page=1)
        self.assertEqual(len(result["complexes"]), 2)
        self.assertEqual(result["regions"], [])
        self.assertFalse(result["is_more_data"])

    def test_fetch_search_page_empty(self):
        result = fetch_search_page("empty-query-zzz", self._ok(SEARCH_EMPTY_RAW), page=1)
        self.assertEqual(result, {"complexes": [], "regions": [], "is_more_data": False})

    def test_fetch_search_page_bad_status_raises(self):
        with self.assertRaises(KeywordSearchError) as ctx:
            fetch_search_page("a", lambda url: (429, ""), page=1)
        self.assertEqual(ctx.exception.status, 429)

    def test_fetch_search_page_invalid_json_raises(self):
        with self.assertRaises(KeywordSearchError):
            fetch_search_page("a", lambda url: (200, "not-json{{"), page=1)

    def test_is_rate_limit_error(self):
        self.assertTrue(is_rate_limit_error(KeywordSearchError("a", 429)))
        self.assertTrue(is_rate_limit_error(RuntimeError("429 too many")))
        self.assertFalse(is_rate_limit_error(KeywordSearchError("a", 500)))
        self.assertFalse(is_rate_limit_error(RuntimeError("boom")))


if __name__ == "__main__":
    unittest.main()
