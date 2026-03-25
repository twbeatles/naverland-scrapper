import asyncio
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail


class _FakeLocatorFirst:
    async def click(self, timeout=0):
        return None


class _FakeLocator:
    def __init__(self):
        self.first = _FakeLocatorFirst()


class _FakePage:
    def __init__(self, bodies, *, html=None, hydration=None, responses=None):
        self._bodies = dict(bodies)
        self._html = dict(html or {})
        self._hydration = dict(hydration or {})
        self._responses = dict(responses or {})
        self._handlers = {"response": []}
        self.url = ""
        self.visited = []

    def on(self, event, handler):
        self._handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        listeners = self._handlers.get(event, [])
        self._handlers[event] = [item for item in listeners if item is not handler]

    async def goto(self, url, wait_until="domcontentloaded"):
        self.url = url
        self.visited.append(url)
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

    async def evaluate(self, script):
        return self._hydration.get(self.url, {})

    def locator(self, query):
        return _FakeLocator()

    async def title(self):
        return "테스트 상세"


class _FakeResponse:
    def __init__(self, url, payload):
        self.url = url
        self._payload = payload

    async def json(self):
        return self._payload


class TestDetailFetcher(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_mobile_article_detail_falls_back_from_fin_to_m_info(self):
        article_no = "2513105556"
        page = _FakePage(
            {
                f"https://fin.land.naver.com/articles/{article_no}": "실거래가",
                f"https://m.land.naver.com/article/info/{article_no}": "\n".join(
                    [
                        "실거래가",
                        "중개소",
                        "홍길동",
                        "행복부동산",
                        "전화 02-123-4567",
                        "기전세금 1억 2,000만",
                        "3년 내 최고 1억 5,000만",
                        "3년 내 최저 1억",
                    ]
                ),
            }
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["전화1"], "02-123-4567")
        self.assertEqual(detail["부동산상호"], "행복부동산")
        self.assertEqual(detail["_detail_meta"]["detail_source"], "m_info")
        self.assertIn(detail["_detail_meta"]["detail_parse_state"], {"partial", "success"})

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
                                "brokerName": "행복공인중개사",
                                "agentName": "김중개",
                                "phone": "02-987-6543",
                            }
                        }
                    }
                }
            },
            responses={
                url: [
                    _FakeResponse(
                        "https://fin.land.naver.com/front-api/article/2529610450",
                        {"prevJeonse": "1억 1,000만", "phones": ["02-987-6543"]},
                    )
                ]
            },
        )

        detail = await fetch_mobile_article_detail(page, article_no)

        self.assertEqual(detail["부동산상호"], "행복공인중개사")
        self.assertEqual(detail["중개사이름"], "김중개")
        self.assertEqual(detail["전화1"], "02-987-6543")
        self.assertEqual(int(detail["기전세금(원)"]), 110_000_000)
        self.assertEqual(int(detail["_detail_meta"]["network_response_count"]), 1)
        self.assertEqual(int(detail["_detail_meta"]["hydration_hit"]), 1)


if __name__ == "__main__":
    unittest.main()
