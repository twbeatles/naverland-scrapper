import asyncio
import json
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.services.detail_fetcher import (
    apply_mobile_detail,
    build_front_api_agent_url,
    fetch_mobile_article_detail,
    parse_front_api_agent_payload,
)


class _FakeLocatorFirst:
    async def click(self, timeout=0):
        return None


class _FakeLocator:
    def __init__(self):
        self.first = _FakeLocatorFirst()


class _FakeRequestContext:
    def __init__(self, routes=None):
        self._routes = dict(routes or {})
        self.calls = []

    async def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        entry = self._routes.get(url)
        if entry is None:
            return _FakeResponse(url, {"detailCode": "NOT_FOUND"}, status=404)
        if isinstance(entry, _FakeResponse):
            return entry
        payload, status = entry if isinstance(entry, tuple) else (entry, 200)
        return _FakeResponse(url, payload, status=status)


class _FakePage:
    def __init__(self, bodies, *, html=None, hydration=None, responses=None, request_routes=None):
        self._bodies = dict(bodies)
        self._html = dict(html or {})
        self._hydration = dict(hydration or {})
        self._responses = dict(responses or {})
        self._handlers = {"response": []}
        self.url = ""
        self.visited = []
        self.goto_calls = []
        self.request = _FakeRequestContext(request_routes)
        self.context = type("Ctx", (), {"request": self.request})()

    def on(self, event, handler):
        self._handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        listeners = self._handlers.get(event, [])
        self._handlers[event] = [item for item in listeners if item is not handler]

    async def goto(self, url, wait_until="domcontentloaded", timeout=None):
        self.url = url
        self.visited.append(url)
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        for response in list(self._responses.get(url, []) or []):
            for handler in list(self._handlers.get("response", [])):
                handler(response)

    async def wait_for_load_state(self, state="networkidle", timeout=0):
        return None

    async def wait_for_timeout(self, timeout_ms):
        return None

    async def inner_text(self, selector):
        if selector != "body":
            return ""
        return self._bodies.get(self.url, "")

    async def content(self):
        return self._html.get(self.url, "")

    async def evaluate(self, script, arg=None):
        # In-page front-api fetch (2026-10): route through the fake request routes.
        if isinstance(arg, list) and arg and "/front-api/" in str(arg[0]):
            response = await self.request.get(arg[0])
            return {"status": response.status, "body": json.dumps(await response.json())}
        return self._hydration.get(self.url, {})

    def locator(self, query):
        return _FakeLocator()

    async def title(self):
        return "테스트 상세"


class _FakeResponse:
    def __init__(self, url, payload, status=200):
        self.url = url
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class TestDetailFetcher(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_mobile_article_detail_skips_m_land_redirect(self):
        # m.land article pages redirect to the fin article (2026-10-22): no extra hop.
        article_no = "2513105556"
        page = _FakePage(
            {
                f"https://fin.land.naver.com/articles/{article_no}": "\n".join(
                    [
                        "실거래가",
                        "중개소",
                        "홍길동",
                        "행복부동산",
                        "전화 02-123-4567",
                    ]
                ),
            }
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["_detail_meta"]["detail_source"], "fin_article")
        self.assertFalse(any("m.land.naver.com" in url for url in page.visited))

    async def test_front_api_runs_in_page_on_fin_origin(self):
        article_no = "2656920495"
        fin_url = f"https://fin.land.naver.com/articles/{article_no}"
        agent_url = build_front_api_agent_url(article_no)
        page = _FakePage(
            {fin_url: "요청하신 페이지를 찾을 수 없어요"},
            request_routes={
                agent_url: {
                    "isSuccess": True,
                    "result": {
                        "brokerageName": "송파로얄공인중개사사무소",
                        "brokerName": "이수영",
                        "phone": {"brokerage": "02-430-4500", "mobile": "010-4542-4501"},
                    },
                }
            },
        )
        evaluated = []
        original = page.evaluate

        async def _evaluate(script, arg=None):
            if isinstance(arg, list):
                evaluated.append(arg[0])
            return await original(script, arg)

        page.evaluate = _evaluate
        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "송파로얄공인중개사사무소")
        self.assertEqual(detail["전화2"], "010-4542-4501")
        self.assertIn(agent_url, evaluated)
        self.assertFalse(any("new.land" in url for url in page.visited))

    async def test_agent_phone_wins_over_complex_management_office_phone(self):
        # Live 2026-10-22: the article page also loads /complex?complexNumber=, whose
        # managementOfficeContact used to be stored as the broker phone.
        article_no = "2657052503"
        fin_url = f"https://fin.land.naver.com/articles/{article_no}"
        agent_url = build_front_api_agent_url(article_no)
        page = _FakePage(
            {fin_url: "헬리오시티\n관리사무소 02-403-8330"},
            responses={
                fin_url: [
                    _FakeResponse(
                        "https://fin.land.naver.com/front-api/v1/complex?complexNumber=111515",
                        {"isSuccess": True, "result": {"name": "헬리오시티", "managementOfficeContact": "02-403-8330"}},
                    )
                ]
            },
            request_routes={
                agent_url: {
                    "isSuccess": True,
                    "result": {
                        "brokerageName": "삼천공인중개사사무소",
                        "brokerName": "홍순화",
                        "phone": {"brokerage": "02-415-3000", "mobile": "010-1111-2222"},
                    },
                }
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "삼천공인중개사사무소")
        self.assertEqual(detail["전화1"], "02-415-3000")
        self.assertEqual(detail["전화2"], "010-1111-2222")

    async def test_api_first_skips_article_page_and_reads_previous_deposit(self):
        from src.core.services.detail_fetcher import (
            build_front_api_article_key_url,
            build_front_api_basic_info_url,
        )

        article_no = "2657059949"
        agent_url = build_front_api_agent_url(article_no)
        key_url = build_front_api_article_key_url(article_no)
        basic_url = build_front_api_basic_info_url(article_no, real_estate_type="A01", trade_type="A1")
        page = _FakePage(
            {},
            request_routes={
                agent_url: {"isSuccess": True, "result": {
                    "brokerageName": "API중개", "brokerName": "김중개",
                    "phone": {"brokerage": "02-111-2222"},
                }},
                key_url: {"isSuccess": True, "result": {"type": {"realEstateType": "A01", "tradeType": "A1"}}},
                basic_url: {"isSuccess": True, "result": {"priceInfo": {"price": 2880000000, "previousDeposit": 1300000000}}},
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["_detail_meta"]["detail_source"], "front_api")
        self.assertEqual(detail["부동산상호"], "API중개")
        self.assertEqual(int(detail["기전세금(원)"]), 1_300_000_000)
        self.assertFalse(any("/articles/" in url for url in page.visited))
        self.assertIn(basic_url, [call["url"] for call in page.request.calls])

    async def test_basic_info_skipped_for_lease_articles(self):
        from src.core.services.detail_fetcher import build_front_api_article_key_url

        article_no = "2656983002"
        key_url = build_front_api_article_key_url(article_no)
        page = _FakePage(
            {},
            request_routes={
                build_front_api_agent_url(article_no): {"isSuccess": True, "result": {"brokerageName": "전세중개"}},
                key_url: {"isSuccess": True, "result": {"type": {"realEstateType": "A01", "tradeType": "B1"}}},
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "전세중개")
        self.assertFalse(any("basicInfo" in call["url"] for call in page.request.calls))

    async def test_apply_mobile_detail_strips_internal_meta(self):
        item = {"단지ID": "12345", "매물ID": "A1", "매매가": "1억"}
        detail = {
            "부동산상호": "테스트부동산",
            "_detail_meta": {
                "detail_source": "fin_article",
                "detail_parse_state": "failed",
                "missing_field_count": 8,
            },
        }

        enriched = apply_mobile_detail(dict(item), detail)

        self.assertEqual(enriched["부동산상호"], "테스트부동산")
        self.assertNotIn("_detail_meta", enriched)
        self.assertEqual(enriched["detail_source"], "fin_article")
        self.assertEqual(enriched["detail_parse_state"], "failed")
        self.assertEqual(enriched["missing_field_count"], 8)
        self.assertEqual(enriched["상세소스"], "fin_article")
        self.assertEqual(enriched["상세수집상태"], "failed")
        self.assertEqual(enriched["상세누락필드수"], 8)

    async def test_apply_mobile_detail_preserves_list_realtor_and_marks_partial(self):
        item = {
            "단지ID": "3833",
            "매물ID": "1",
            "매매가": "10억",
            "부동산상호": "목록중개",
        }
        detail = {
            "부동산상호": "",
            "전화1": "",
            "_detail_meta": {
                "detail_source": "fin_article",
                "detail_parse_state": "failed",
                "missing_field_count": 8,
                "detail_host_unreachable": True,
            },
        }
        enriched = apply_mobile_detail(dict(item), detail)
        self.assertEqual(enriched["부동산상호"], "목록중개")
        self.assertEqual(enriched["detail_parse_state"], "partial")
        self.assertTrue(enriched.get("detail_host_unreachable"))

    async def test_prefer_front_api_only_skips_html_navigation(self):
        article_no = "2630745167"
        agent_url = build_front_api_agent_url(article_no)
        page = _FakePage(
            {},
            request_routes={
                agent_url: {
                    "brokerageName": "API중개",
                    "brokerName": "김에이피아이",
                    "phones": ["02-111-2222"],
                }
            },
        )
        detail = await fetch_mobile_article_detail(
            page,
            article_no,
            prefer_front_api_only=True,
            front_api_enabled=True,
        )
        self.assertEqual(detail.get("부동산상호"), "API중개")
        self.assertEqual(detail.get("_detail_meta", {}).get("detail_source"), "front_api")
        # Session warm may park on fin robots.txt once; never open fin article HTML in API-only mode.
        self.assertFalse(
            any("fin.land.naver.com/articles" in str(call.get("url", "")) for call in page.goto_calls)
        )
        self.assertLessEqual(len(page.goto_calls), 1)

    async def test_fetch_mobile_article_detail_uses_hydration_and_network_corpus(self):
        article_no = "2529610450"
        url = f"https://fin.land.naver.com/articles/{article_no}"
        page = _FakePage(
            {url: "실거래가"},
            html={url: "<html><body><div>실거래가</div></body></html>"},
            hydration={
                url: {
                    "__NEXT_DATA__": {
                        "props": {
                            "pageProps": {
                                "brokerageName": "행복공인중개사",
                                "brokerName": "김중개",
                            }
                        }
                    }
                }
            },
            responses={
                url: [
                    _FakeResponse(
                        "https://fin.land.naver.com/front-api/article/2529610450",
                        {
                            "prevJeonse": "1억 1,000만",
                            "phone": {"brokerage": "02-987-6543", "mobile": "010-1234-5678"},
                        },
                    )
                ]
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "행복공인중개사")
        self.assertEqual(detail["중개사이름"], "김중개")
        self.assertEqual(detail["전화1"], "02-987-6543")
        self.assertEqual(detail["전화2"], "010-1234-5678")
        self.assertEqual(int(detail["기전세금(원)"]), 110_000_000)
        self.assertEqual(int(detail["_detail_meta"]["network_response_count"]), 1)
        self.assertEqual(int(detail["_detail_meta"]["hydration_hit"]), 1)

    async def test_fetch_mobile_article_detail_passes_navigation_timeout(self):
        article_no = "2513105556"
        url = f"https://fin.land.naver.com/articles/{article_no}"
        page = _FakePage(
            {
                url: "\n".join(
                    [
                        "실거래가",
                        "중개소",
                        "행복부동산",
                        "김중개",
                        "전화 02-987-6543",
                    ]
                )
            }
        )

        await fetch_mobile_article_detail(page, article_no, navigation_timeout_ms=4321)

        self.assertTrue(page.goto_calls)
        self.assertEqual(page.goto_calls[0]["timeout"], 4321)

    def test_parse_front_api_agent_payload_nested_phone(self):
        fields = parse_front_api_agent_payload(
            {
                "result": {
                    "brokerageName": "행복공인중개사",
                    "brokerName": "김중개",
                    "phone": {"brokerage": "02-111-2222", "mobile": "010-3333-4444"},
                }
            }
        )
        self.assertEqual(fields["부동산상호"], "행복공인중개사")
        self.assertEqual(fields["중개사이름"], "김중개")
        self.assertEqual(fields["전화1"], "02-111-2222")
        self.assertEqual(fields["전화2"], "010-3333-4444")

    async def test_fetch_uses_front_api_when_dom_is_404(self):
        article_no = "2630745167"
        fin_url = f"https://fin.land.naver.com/articles/{article_no}"
        agent_url = build_front_api_agent_url(article_no)
        page = _FakePage(
            {
                fin_url: "요청하신 페이지를 찾을 수 없어요",
                f"https://m.land.naver.com/article/info/{article_no}": "요청하신 페이지를 찾을 수 없어요",
                f"https://m.land.naver.com/article/view/{article_no}": "요청하신 페이지를 찾을 수 없어요",
            },
            request_routes={
                agent_url: {
                    "brokerageName": "남산중개",
                    "brokerName": "이공인",
                    "phones": ["02-555-6666", "010-7777-8888"],
                }
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "남산중개")
        self.assertEqual(detail["중개사이름"], "이공인")
        self.assertEqual(detail["전화1"], "02-555-6666")
        self.assertIn(detail["_detail_meta"]["detail_parse_state"], {"partial", "success"})
        self.assertGreaterEqual(int(detail["_detail_meta"]["network_response_count"]), 1)
        self.assertTrue(any(agent_url in str(call.get("url", "")) for call in page.request.calls))


if __name__ == "__main__":
    unittest.main()
