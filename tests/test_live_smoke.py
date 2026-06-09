import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from src.utils import live_smoke


class _NavigationFailPage:
    url = ""

    async def goto(self, *_args, **_kwargs):
        raise TimeoutError("probe timeout")

    async def wait_for_load_state(self, *_args, **_kwargs):
        return None

    async def title(self):
        return ""


class _ArticleResponse:
    def __init__(self, url, payload, status=200):
        self.url = url
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class _ArticleListPage:
    def __init__(self, complex_id, payload, status=200):
        self.url = f"https://new.land.naver.com/complexes/{complex_id}"
        self._complex_id = complex_id
        self._payload = payload
        self._status = status
        self._response_handler = None

    def on(self, event, handler):
        if event == "response":
            self._response_handler = handler

    def remove_listener(self, event, handler):
        if event == "response" and self._response_handler is handler:
            self._response_handler = None

    async def goto(self, *_args, **_kwargs):
        if self._response_handler is not None:
            self._response_handler(
                _ArticleResponse(
                    f"https://new.land.naver.com/api/articles/complex/{self._complex_id}",
                    self._payload,
                    status=self._status,
                )
            )
        return _ArticleResponse(self.url, {}, status=200)

    async def wait_for_load_state(self, *_args, **_kwargs):
        return None

    async def title(self):
        return "네이버페이 부동산"


class _ArticleRequestContext:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _ArticleResponse(url, self._payload, status=self._status)


class _ArticleApiContext:
    def __init__(self, payload, status=200):
        self.request = _ArticleRequestContext(payload, status=status)


class _DetailFieldPage:
    url = "https://m.land.naver.com/article/info/2625154515"

    def set_default_timeout(self, *_args, **_kwargs):
        return None

    async def title(self):
        return "매물 상세"


class TestLiveSmoke(unittest.IsolatedAsyncioTestCase):
    async def test_navigate_probe_converts_navigation_exception_to_failure(self):
        result = await live_smoke._navigate_probe(_NavigationFailPage(), "https://example.com", 5)

        self.assertFalse(result["ok"])
        self.assertIn("navigation_exception:TimeoutError", result["reason"])
        self.assertEqual(result["final_url"], "")

    async def test_complex_probe_returns_failure_line_without_raising_on_navigation_timeout(self):
        ok, line = await live_smoke._run_complex_probe(_NavigationFailPage(), "102378", 5)

        self.assertFalse(ok)
        self.assertIn("[fail] [complex]", line)
        self.assertIn("navigation_exception:TimeoutError", line)

    async def test_complex_probe_records_article_count_and_sample_article(self):
        page = _ArticleListPage(
            "3833",
            {
                "articleList": [
                    {"articleNo": "2625154515"},
                    {"articleNo": "2625343720"},
                ]
            },
        )

        ok, line, sample_article_id, article_count = await live_smoke._run_complex_probe_detail(page, "3833", 1000)

        self.assertTrue(ok)
        self.assertEqual(sample_article_id, "2625154515")
        self.assertEqual(article_count, 2)
        self.assertIn("article_count=2", line)
        self.assertIn("sample_article=2625154515", line)

    async def test_article_api_probe_records_article_count_and_sample_article(self):
        context = _ArticleApiContext(
            {
                "articleList": [
                    {"articleNo": "2625154515"},
                    {"articleNo": "2625343720"},
                ]
            }
        )

        ok, line, sample_article_id, article_count = await live_smoke._run_article_api_probe(
            context,
            "3833",
            1000,
        )

        self.assertTrue(ok)
        self.assertEqual(sample_article_id, "2625154515")
        self.assertEqual(article_count, 2)
        self.assertIn("[ok] [article-api]", line)
        self.assertIn("article_count=2", line)

    async def test_complex_probe_fails_when_article_list_is_empty(self):
        page = _ArticleListPage("102378", {"articleList": []})

        ok, line, sample_article_id, article_count = await live_smoke._run_complex_probe_detail(
            page,
            "102378",
            1000,
        )

        self.assertFalse(ok)
        self.assertEqual(sample_article_id, "")
        self.assertEqual(article_count, 0)
        self.assertIn("article_count=0", line)
        self.assertIn("articles_empty", line)

    async def test_detail_field_probe_reports_parse_metadata(self):
        with patch(
            "src.utils.live_smoke.fetch_mobile_article_detail",
            new=AsyncMock(
                return_value={
                    "부동산상호": "행복부동산",
                    "전화1": "02-123-4567",
                    "_detail_meta": {
                        "detail_source": "m_info",
                        "detail_parse_state": "partial",
                        "missing_field_count": 6,
                        "network_response_count": 1,
                        "hydration_hit": 0,
                    },
                }
            ),
        ):
            ok, line = await live_smoke._run_detail_field_probe(_DetailFieldPage(), "2625154515", 1000)

        self.assertTrue(ok)
        self.assertIn("[ok] [detail-fields]", line)
        self.assertIn("parse_state=partial", line)
        self.assertIn("core_field_count=2", line)


class TestRunLiveSmoke(unittest.TestCase):
    def test_run_live_smoke_writes_json_log_for_unexpected_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "nested", "smoke.json")
            with patch(
                "src.utils.live_smoke._run_live_smoke_async",
                side_effect=RuntimeError("boom"),
            ):
                ok, messages = live_smoke.run_live_smoke(["https://example.com"], json_log_path=log_path)

            self.assertFalse(ok)
            self.assertTrue(messages)
            self.assertTrue(any("unexpected_exception=RuntimeError" in message for message in messages))
            with open(log_path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["requested_article_id"], live_smoke.DEFAULT_SMOKE_ARTICLE_ID)
        self.assertEqual(payload["effective_article_id"], live_smoke.DEFAULT_SMOKE_ARTICLE_ID)
        self.assertIn(payload["runtime_source"], {"source", "frozen"})
        self.assertIn("executable", payload)
        self.assertIn("data_dir", payload)
        self.assertFalse(payload["include_detail_fields"])
        self.assertEqual(payload["messages"], messages)


if __name__ == "__main__":
    unittest.main()
