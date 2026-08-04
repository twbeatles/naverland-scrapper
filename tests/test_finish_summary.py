import unittest

from src.ui.widgets.crawler_tab_parts.crawl_control_parts.finish import CrawlerTabFinishMixin


class _Harness(CrawlerTabFinishMixin):
    pass


class TestFinishSummary(unittest.TestCase):
    def test_format_api_failure_summary(self):
        h = _Harness()
        text = h._format_api_failure_summary(
            {"article_api_failure_reasons": {"rate_limited": 3, "invalid_payload": 1}}
        )
        self.assertIn("rate_limited=3", text)
        self.assertIn("invalid_payload=1", text)

    def test_format_api_failure_summary_empty(self):
        h = _Harness()
        self.assertEqual(h._format_api_failure_summary({}), "")
        self.assertEqual(h._format_api_failure_summary({"article_api_failure_reasons": []}), "")


if __name__ == "__main__":
    unittest.main()
