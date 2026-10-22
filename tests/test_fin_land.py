"""fin.land front-api contract (live samples trimmed from 2026-10-22 probe)."""

import asyncio
import json
import unittest

from src.core.services.fin_article_api import (
    direction_label,
    fin_article_to_legacy,
    format_man_price,
    parse_fin_article_list,
    parse_fin_complex_info,
)
from src.core.services.fin_land_codec import (
    decode_base62_coord,
    encode_base62_coord,
    lz_decompress_from_uri,
    parse_fin_map_link,
    parse_map_center,
)
from src.core.services.keyword_search import (
    KeywordSearchError,
    fetch_complex_search_page,
    fetch_fin_complex_info,
    fetch_fin_search_page,
    fetch_search_page_with_fallback,
)
from src.core.services.response_capture import normalize_article_payload
from src.core.services.site_contract import (
    DESKTOP_USER_AGENT,
    build_fin_article_list_body,
    build_fin_autocomplete_url,
    build_front_api_basic_info_url,
)


def _ad(number, *, trade="A1", deal=3100000000, warranty=0, rent=0, direction="WS"):
    return {
        "complexName": "헬리오시티",
        "complexNumber": 111515,
        "articleNumber": number,
        "articleName": "헬리오시티",
        "dongName": "106",
        "tradeType": trade,
        "realEstateType": "A01",
        "spaceInfo": {"supplySpace": 110.17, "exclusiveSpace": 84.95, "supplySpaceName": "110F"},
        "verificationInfo": {"verificationType": "OWNER", "articleConfirmDate": "2026-10-22"},
        "brokerInfo": {"cpId": "bizmk", "brokerageName": "송파로얄공인중개사사무소", "brokerName": "매경부동산"},
        "articleDetail": {
            "direction": direction,
            "articleFeatureDescription": "커뮤니티인접",
            "directTrade": False,
            "floorInfo": "33/35",
        },
        "address": {"coordinates": {"xCoordinate": 127.103534, "yCoordinate": 37.496765}},
        "priceInfo": {"dealPrice": deal, "warrantyPrice": warranty, "rentPrice": rent, "managementFeeAmount": 300000},
    }


def _group(ads, *, deal_range=(3000000000, 3100000000)):
    return {
        "representativeArticleInfo": ads[0],
        "duplicatedArticleInfo": {
            "representativePriceInfo": {
                "dealPrice": {"minPrice": deal_range[0], "maxPrice": deal_range[1]},
                "warrantyPrice": {"minPrice": 0, "maxPrice": 0},
                "rentPrice": {"minPrice": 0, "maxPrice": 0},
            },
            "realtorCount": len(ads),
            "articleInfoList": ads,
        },
    }


def _list_payload(groups, *, has_next=False, last_info=None, seed="seed-1", total=None):
    return {
        "isSuccess": True,
        "detailCode": "success",
        "message": "",
        "result": {
            "seed": seed,
            "lastInfo": last_info or [],
            "hasNextPage": has_next,
            "totalCount": len(groups) if total is None else total,
            "list": groups,
        },
    }


class TestFinCodec(unittest.TestCase):
    def test_layer_decodes_live_samples(self):
        self.assertEqual(
            lz_decompress_from_uri("NobwRAlgJmBcYAsD2BbApmANGAzmghgE4DGCACkfijnCAL50C6QA"),
            '[{"id":"home","searchParams":{}}]',
        )
        link = parse_fin_map_link(
            "https://fin.land.naver.com/map?layer=NobwRAlgJmBcYGMD2BbADgGwKYA8D6UWALgIYQZgA0YaJATiSgM5zj"
            "LrY4CSMsAjAICsfQQF9qTLPQQALAAr1GLWOFIAjOGHpEICbGFGiAukA"
        )
        self.assertEqual(link["complex_id"], "111515")
        self.assertEqual(link["asset_type"], "APT")

    def test_malformed_layer_is_ignored(self):
        self.assertIsNone(lz_decompress_from_uri("not*valid"))
        self.assertEqual(parse_fin_map_link("https://fin.land.naver.com/map?layer=zzzz")["complex_id"], "")

    def test_base62_round_trip(self):
        self.assertEqual(encode_base62_coord(126.9779692), "3zhF48")
        decoded = decode_base62_coord("2AM354")
        assert decoded is not None
        self.assertAlmostEqual(decoded, 37.566535)
        self.assertIsNone(decode_base62_coord("!!"))

    def test_map_center_variants(self):
        self.assertEqual(parse_map_center("https://new.land.naver.com/complexes?ms=2AJ9Kw,3zn5fO,16"), (37.4976, 127.1072, 16))
        self.assertEqual(parse_map_center("?ms=37.5,127.0,20"), (37.5, 127.0, 18))
        self.assertEqual(parse_map_center("https://fin.land.naver.com/map?center=3zhF48-2AM354"), (37.566535, 126.9779692, 15))
        self.assertIsNone(parse_map_center("https://example.com/?ms=1.0,2.0,16"))


class TestFinArticleList(unittest.TestCase):
    def test_groups_are_expanded_to_ads(self):
        payload = _list_payload(
            [_group([_ad("1"), _ad("2"), _ad("3")]), _group([_ad("4")])],
            has_next=True,
            last_info=[1, 930.9, "4"],
        )
        parsed = parse_fin_article_list(payload)
        assert parsed is not None
        self.assertEqual([a["articleNo"] for a in parsed["articles"]], ["1", "2", "3", "4"])
        self.assertEqual(parsed["group_count"], 2)
        self.assertTrue(parsed["has_next"])
        self.assertEqual(parsed["last_info"], [1, 930.9, "4"])
        self.assertEqual(parsed["seed"], "seed-1")
        self.assertEqual(parsed["articles"][0]["sameAddrCnt"], 3)
        self.assertEqual(parsed["articles"][0]["sameAddrMaxPrc"], "31억")
        self.assertEqual(parsed["articles"][0]["sameAddrMinPrc"], "30억")

    def test_error_envelopes_and_missing_list_are_rejected(self):
        self.assertIsNone(parse_fin_article_list({"detailCode": "TOO_MANY_REQUESTS", "message": ""}))
        self.assertIsNone(parse_fin_article_list({"isSuccess": False, "result": {"list": []}}))
        self.assertIsNone(parse_fin_article_list({"isSuccess": True, "detailCode": "success", "result": {}}))
        empty = parse_fin_article_list(_list_payload([]))
        assert empty is not None
        self.assertEqual(empty["articles"], [])

    def test_normalized_row_matches_legacy_contract(self):
        legacy = fin_article_to_legacy(_ad("2656920495"), group=_group([_ad("2656920495")]))
        item = normalize_article_payload(legacy, "헬리오시티", "111515", "매매")
        self.assertEqual(item["매물ID"], "2656920495")
        self.assertEqual(item["거래유형"], "매매")
        self.assertEqual(item["매매가"], "31억")
        self.assertEqual(item["면적(㎡)"], 110.17)
        self.assertEqual(item["전용면적(㎡)"], 84.95)
        self.assertEqual(item["층/방향"], "33/35 남서향")
        self.assertEqual(item["확인일"], "20261022")
        self.assertEqual(item["부동산상호"], "송파로얄공인중개사사무소")
        self.assertEqual(item["확인유형"], "OWNER")
        self.assertEqual(item["자산유형"], "APT")
        self.assertAlmostEqual(item["위도"], 37.496765)
        self.assertEqual(item["데이터품질오류"], [])

    def test_monthly_rent_is_split_into_deposit_and_rent(self):
        legacy = fin_article_to_legacy(_ad("9", trade="B2", deal=0, warranty=800000000, rent=2400000))
        item = normalize_article_payload(legacy, "헬리오시티", "111515", "월세")
        self.assertEqual(item["보증금"], "8억")
        self.assertEqual(item["월세"], "240")

    def test_price_and_direction_formatting(self):
        self.assertEqual(format_man_price(135000), "13억 5,000")
        self.assertEqual(format_man_price(9500), "9,500")
        self.assertEqual(format_man_price(0), "")
        self.assertEqual(direction_label("SS"), "남향")
        self.assertEqual(direction_label("??"), "??")

    def test_complex_info(self):
        info = parse_fin_complex_info(
            {
                "isSuccess": True,
                "result": {
                    "name": "헬리오시티",
                    "type": "A01",
                    "address": {"city": "서울시", "division": "송파구", "sector": "가락동", "jibun": "913",
                                "legalDivisionNumber": "1171010700", "roadName": "송파대로 345"},
                    "coordinates": {"xCoordinate": 127.107268, "yCoordinate": 37.497624},
                    "totalHouseholdNumber": 9510,
                    "dongCount": 84,
                },
            }
        )
        self.assertEqual(info["name"], "헬리오시티")
        self.assertEqual(info["address"], "서울시 송파구 가락동 913")
        self.assertEqual(info["household_count"], 9510)
        self.assertEqual(parse_fin_complex_info({"isSuccess": False}), {})


class TestFinContract(unittest.TestCase):
    def test_article_list_body(self):
        body = build_fin_article_list_body("111515", "전세", last_info=[1, "x"], seed="s", size=99)
        self.assertEqual(body["tradeTypes"], ["B1"])
        self.assertEqual(body["size"], 30)
        self.assertEqual(body["lastInfo"], [1, "x"])
        self.assertEqual(body["seed"], "s")
        self.assertNotIn("seed", build_fin_article_list_body("1", "매매"))

    def test_basic_info_uses_article_number(self):
        url = build_front_api_basic_info_url("2656920495", trade_type="월세")
        self.assertIn("articleNumber=2656920495", url)
        self.assertIn("tradeType=B2", url)
        self.assertNotIn("articleId", url)

    def test_autocomplete_is_zero_based(self):
        self.assertIn("page=0", build_fin_autocomplete_url("complexes", "래미안"))

    def test_desktop_user_agent_is_not_headless(self):
        self.assertNotIn("Headless", DESKTOP_USER_AGENT)
        self.assertIn("Chrome/", DESKTOP_USER_AGENT)


_FIN_COMPLEXES = {
    "isSuccess": True,
    "detailCode": "success",
    "result": {
        "hasNextPage": True,
        "totalCount": 303,
        "list": [
            {
                "complexNumber": 111515,
                "complexName": "헬리오시티",
                "type": "A01",
                "legalDivisionName": "서울시 송파구 가락동",
                "legalDivisionNumber": "1171010700",
                "coordinates": {"xCoordinate": 127.107268, "yCoordinate": 37.497624},
            }
        ],
    },
}
_FIN_REGIONS = {
    "isSuccess": True,
    "detailCode": "success",
    "result": {
        "hasNextPage": False,
        "totalCount": 1,
        "list": [
            {
                "legalDivisionNumber": "1165010700",
                "legalDivisionName": "서울시 서초구 반포동",
                "legalDivisionLevelType": "EUP",
                "coordinates": {"xCoordinate": 127.0019, "yCoordinate": 37.5047},
            }
        ],
    },
}
_FIN_EMPTY = {"isSuccess": True, "detailCode": "success", "result": {"hasNextPage": False, "totalCount": 0, "list": []}}


def _router(routes):
    calls = []

    def fetch(url):
        calls.append(url)
        for token, response in routes:
            if token in url:
                return response
        return 404, ""

    return fetch, calls


class TestFinKeywordSearch(unittest.TestCase):
    def test_fin_search_page_maps_complexes_and_regions(self):
        fetch, calls = _router([
            ("/autocomplete/complexes", (200, json.dumps(_FIN_COMPLEXES))),
            ("/autocomplete/legalDivisions", (200, json.dumps(_FIN_REGIONS))),
        ])
        result = fetch_fin_search_page("헬리오시티", fetch, page=1)
        self.assertEqual(result["complexes"][0]["complex_id"], "111515")
        self.assertEqual(result["complexes"][0]["address"], "서울시 송파구 가락동")
        self.assertAlmostEqual(result["complexes"][0]["latitude"], 37.497624)
        self.assertEqual(result["regions"][0]["cortar_no"], "1165010700")
        self.assertTrue(result["is_more_data"])
        self.assertIn("page=0", calls[0])

    def test_later_pages_skip_regions(self):
        fetch, calls = _router([("/autocomplete/complexes", (200, json.dumps(_FIN_COMPLEXES)))])
        result = fetch_fin_search_page("래미안", fetch, page=3)
        self.assertEqual(result["regions"], [])
        self.assertEqual(len(calls), 1)
        self.assertIn("page=2", calls[0])

    def test_falls_back_to_new_land_when_fin_fails(self):
        legacy = {"complexes": [{"complexNo": "22853", "complexName": "반포자이", "cortarAddress": "서울시 서초구 반포동"}]}
        fetch, _calls = _router([
            ("front-api", (500, "")),
            ("new.land.naver.com/api/search", (200, json.dumps(legacy))),
        ])
        result = fetch_complex_search_page("반포자이", fetch)
        self.assertEqual(result["source"], "new_land")
        self.assertEqual(result["complexes"][0]["complex_id"], "22853")

    def test_rate_limit_does_not_hit_fallback_host(self):
        fetch, calls = _router([("front-api", (429, ""))])
        with self.assertRaises(KeywordSearchError):
            fetch_complex_search_page("반포자이", fetch)
        self.assertTrue(all("front-api" in url for url in calls))

    def test_full_address_falls_back_to_dong_name(self):
        from urllib.parse import parse_qs, urlparse

        def fetch(url):
            keyword = parse_qs(urlparse(url).query).get("keyword", [""])[0]
            if "/autocomplete/complexes" in url and keyword == "가락동":
                return 200, json.dumps(_FIN_COMPLEXES)
            return 200, json.dumps(_FIN_EMPTY)

        result = fetch_search_page_with_fallback(
            "서울특별시 송파구 가락동", fetch, fetch_page=fetch_complex_search_page
        )
        self.assertEqual(result["effective_query"], "가락동")
        self.assertEqual(result["complexes"][0]["complex_id"], "111515")

    def test_complex_info_lookup(self):
        body = {"isSuccess": True, "result": {"name": "헬리오시티", "type": "A01", "address": {}, "coordinates": {}}}
        fetch, calls = _router([("/front-api/v1/complex?", (200, json.dumps(body)))])
        self.assertEqual(fetch_fin_complex_info("111515", fetch)["name"], "헬리오시티")
        self.assertIn("complexNumber=111515", calls[0])
        self.assertEqual(fetch_fin_complex_info("1", _router([])[0]), {})


class _FakeFinPage:
    def __init__(self, responses):
        self._responses = list(responses)
        self.bodies = []
        self.urls = []

    def is_closed(self):
        return False

    async def evaluate(self, _script, args):
        self.urls.append(args[0])
        self.bodies.append(args[2])
        status, payload = self._responses.pop(0)
        return {"status": status, "body": json.dumps(payload)}


class TestFinEngineFastPath(unittest.TestCase):
    def _engine(self, responses):
        from test_playwright_engine_stabilization import _ThreadStub
        from src.core.engines.playwright_engine import PlaywrightCrawlerEngine

        thread = _ThreadStub()
        setattr(thread, "article_api_page_delay_ms", 0)
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_context = object()
        engine._fin_api_page = _FakeFinPage(responses)
        return engine, thread

    def _collect(self, engine):
        async def _noop():
            return None

        engine._ensure_started = _noop
        try:
            return engine._loop.run_until_complete(
                engine._collect_target_raw_items("헬리오시티", "111515", "매매", asset_type="APT")
            )
        finally:
            engine._loop.close()

    def test_paginates_with_cursor_and_completes(self):
        from src.core.engines.playwright_parts.complex_mode_parts.fin_api import PlaywrightFinApiMixin as fin_api

        original = fin_api.FIN_MIN_PAGE_DELAY_SEC
        fin_api.FIN_MIN_PAGE_DELAY_SEC = 0
        try:
            engine, thread = self._engine([
                (200, _list_payload([_group([_ad("1"), _ad("2")])], has_next=True, last_info=[1, 9.5, "2"])),
                (200, _list_payload([_group([_ad("3")])], has_next=False)),
            ])
            page = engine._fin_api_page
            assert isinstance(page, _FakeFinPage)
            result = self._collect(engine)
        finally:
            fin_api.FIN_MIN_PAGE_DELAY_SEC = original
        self.assertEqual(result["collection_status"], "complete")
        self.assertEqual([row["매물ID"] for row in result["raw_items"]], ["1", "2", "3"])
        self.assertEqual(page.bodies[1]["lastInfo"], [1, 9.5, "2"])
        self.assertEqual(page.bodies[1]["seed"], "seed-1")
        self.assertEqual(thread.stats.get("fin_api_hit_count"), 1)

    def test_later_page_rate_limit_keeps_rows_as_partial(self):
        from src.core.engines.playwright_parts.complex_mode_parts.fin_api import PlaywrightFinApiMixin as fin_api

        original = fin_api.FIN_MIN_PAGE_DELAY_SEC
        fin_api.FIN_MIN_PAGE_DELAY_SEC = 0
        try:
            engine, thread = self._engine([
                (200, _list_payload([_group([_ad("1")])], has_next=True, last_info=[1, "1"])),
                (429, {"detailCode": "TOO_MANY_REQUESTS"}),
            ])
            result = self._collect(engine)
        finally:
            fin_api.FIN_MIN_PAGE_DELAY_SEC = original
        self.assertEqual(result["collection_status"], "partial")
        self.assertEqual(result["failure_reason"], "rate_limited")
        self.assertEqual(result["last_successful_page"], 1)
        self.assertEqual(len(result["raw_items"]), 1)
        self.assertEqual(thread.stats["fin_api_failure_reasons"], {"rate_limited": 1})

    def _no_delay(self):
        from src.core.engines.playwright_parts.complex_mode_parts.fin_api import PlaywrightFinApiMixin

        original = PlaywrightFinApiMixin.FIN_MIN_PAGE_DELAY_SEC
        PlaywrightFinApiMixin.FIN_MIN_PAGE_DELAY_SEC = 0
        self.addCleanup(setattr, PlaywrightFinApiMixin, "FIN_MIN_PAGE_DELAY_SEC", original)

    def _collect_asset(self, engine, cid, asset):
        async def _noop():
            return None

        engine._ensure_started = _noop
        try:
            return engine._loop.run_until_complete(
                engine._collect_target_raw_items("빌라", cid, "매매", asset_type=asset)
            )
        finally:
            engine._loop.close()

    def test_villa_uses_villa_article_list(self):
        self._no_delay()
        villa_ad = dict(_ad("2653765203"), realEstateType="A06", complexNumber=615902)
        engine, _thread = self._engine([(200, _list_payload([_group([villa_ad])]))])
        page = engine._fin_api_page
        assert isinstance(page, _FakeFinPage)
        result = self._collect_asset(engine, "615902", "VL")
        self.assertEqual(result["collection_status"], "complete")
        self.assertEqual(result["raw_items"][0]["자산유형"], "VL")
        self.assertTrue(page.urls[0].endswith("/complex/villa/article/list"))

    def test_unknown_complex_falls_back_to_legacy_path(self):
        self._no_delay()
        engine, thread = self._engine([
            (200, _list_payload([])),
            (200, {"isSuccess": True, "detailCode": "success", "message": ""}),
        ])
        fallback_calls = []

        async def _legacy(**kwargs):
            fallback_calls.append(kwargs["cid"])
            return {"raw_items": [], "collection_status": "complete", "api_fast_path": True}

        setattr(engine, "_fetch_article_api_fast_path", _legacy)
        self._collect_asset(engine, "123456", "VL")
        self.assertEqual(fallback_calls, ["123456"])
        self.assertEqual(thread.stats["fin_api_failure_reasons"], {"unknown_complex": 1})

    def test_empty_but_existing_complex_is_complete(self):
        self._no_delay()
        engine, _thread = self._engine([
            (200, _list_payload([])),
            (200, {"isSuccess": True, "result": {"name": "골든빌", "type": "A06", "address": {}, "coordinates": {}}}),
        ])
        result = self._collect_asset(engine, "615902", "VL")
        self.assertEqual(result["collection_status"], "complete")
        self.assertEqual(result["raw_items"], [])


def _bounded_item(cid, name, *, villa=False, deal=5, lease=0):
    info_key, body_key = ("villaInfo", "villa") if villa else ("complexInfo", "complex")
    return {
        "type": "VILLA" if villa else "COMPLEX",
        body_key: {
            info_key: {
                "complexNumber": cid,
                "name": name,
                "type": "A06" if villa else "A01",
                "totalHouseholdNumber": 100,
                "address": {"coordinates": {"xCoordinate": 126.95, "yCoordinate": 37.55}},
            },
            "articleCountInfoDto": {"dealCount": deal, "leaseDepositCount": lease, "leaseMonthlyCount": 0},
        },
    }


def _bounded_payload(items, *, has_next=False, last_info=None):
    return {"isSuccess": True, "detailCode": "success", "result": {
        "seed": "s", "lastInfo": last_info or [], "hasNextPage": has_next, "totalCount": len(items), "list": items}}


class TestFinGeoDiscovery(unittest.TestCase):
    def test_parse_bounded_complexes_filters_by_trade_count(self):
        from src.core.services.fin_article_api import parse_fin_bounded_complexes

        payload = _bounded_payload([
            _bounded_item(104917, "마포래미안푸르지오", deal=156, lease=37),
            _bounded_item(1, "전세만", deal=0, lease=3),
            _bounded_item(615902, "골든빌", villa=True, deal=10),
        ])
        sale = parse_fin_bounded_complexes(payload, trade_code="A1")
        assert sale is not None
        self.assertEqual([m["complex_id"] for m in sale["markers"]], ["104917", "615902"])
        self.assertEqual(sale["markers"][1]["asset_type"], "VL")
        self.assertEqual(sale["markers"][0]["count"], 156)
        lease = parse_fin_bounded_complexes(payload, trade_code="B1")
        assert lease is not None
        self.assertEqual([m["complex_id"] for m in lease["markers"]], ["104917", "1"])
        self.assertIsNone(parse_fin_bounded_complexes({"detailCode": "TOO_MANY_REQUESTS"}))

    def test_bounded_body_contract(self):
        from src.core.services.site_contract import build_fin_bounded_complexes_body

        body = build_fin_bounded_complexes_body(
            asset_type="VL", trade_type="전세",
            bounds={"leftLon": 1.0, "rightLon": 2.0, "topLat": 4.0, "bottomLat": 3.0},
            zoom=15, last_info=[3, "601000"], seed="s",
        )
        self.assertEqual(body["filter"]["realEstateTypes"], ["A05", "A06", "A07", "C02"])
        self.assertEqual(body["filter"]["tradeTypes"], ["B1"])
        self.assertTrue(body["filter"]["hasArticle"])
        self.assertEqual(body["boundingBox"], {"left": 1.0, "right": 2.0, "top": 4.0, "bottom": 3.0})
        self.assertEqual(body["complexPagingRequest"]["lastInfo"], [3, "601000"])

    def _geo_engine(self, responses):
        from test_playwright_engine_stabilization import _ThreadStub
        from src.core.engines.playwright_engine import PlaywrightCrawlerEngine
        from src.core.engines.playwright_parts.geo_mode_parts.fin_markers import PlaywrightGeoFinMarkerMixin

        original = PlaywrightGeoFinMarkerMixin.FIN_GEO_PAGE_DELAY_SEC
        PlaywrightGeoFinMarkerMixin.FIN_GEO_PAGE_DELAY_SEC = 0
        self.addCleanup(setattr, PlaywrightGeoFinMarkerMixin, "FIN_GEO_PAGE_DELAY_SEC", original)
        thread = _ThreadStub()
        thread.geo_config.rings = 0
        registered = []
        setattr(thread, "register_discovered_complex", lambda marker: registered.append(marker))
        setattr(thread, "emit_stats", lambda: None)
        engine = PlaywrightCrawlerEngine(thread)
        engine._desktop_context = object()
        engine._desktop_page = object()
        engine._fin_api_page = _FakeFinPage(responses)
        engine._geo_discovered_ref = {}
        return engine, thread, registered

    def test_geo_sweep_paginates_bbox_without_map_navigation(self):
        engine, thread, registered = self._geo_engine([
            (200, _bounded_payload([_bounded_item(104917, "마포래미안푸르지오")], has_next=True, last_info=[37, "1"])),
            (200, _bounded_payload([_bounded_item(148651, "마포더클래시")])),
        ])
        page = engine._fin_api_page
        assert isinstance(page, _FakeFinPage)
        try:
            ok = engine._loop.run_until_complete(
                engine._scan_geo_asset_type("APT", "매매", 37.544, 126.951, 15, thread.geo_config)
            )
        finally:
            engine._loop.close()
        self.assertTrue(ok)
        self.assertEqual(sorted(engine._geo_discovered_ref), ["APT:104917", "APT:148651"])
        self.assertEqual([m["complex_name"] for m in registered], ["마포래미안푸르지오", "마포더클래시"])
        self.assertEqual(page.bodies[1]["complexPagingRequest"]["lastInfo"], [37, "1"])
        self.assertEqual(thread.stats["geo_marker_switch_last_method"], "fin_bounded_complexes")

    def test_geo_first_query_failure_returns_none_for_fallback(self):
        engine, thread, _registered = self._geo_engine([(429, {"detailCode": "TOO_MANY_REQUESTS"})])
        try:
            result = engine._loop.run_until_complete(
                engine._scan_geo_asset_type_fin("APT", "매매", 37.544, 126.951, 15, thread.geo_config)
            )
        finally:
            engine._loop.close()
        self.assertIsNone(result)
        self.assertEqual(thread.stats["geo_fin_api_last_status"], "429")


if __name__ == "__main__":
    unittest.main()
