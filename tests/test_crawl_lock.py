import unittest

from src.core.crawl_lock import CrawlLock, get_crawl_lock, reset_crawl_lock_for_tests
from src.core.managers import collection_runtime_kwargs


class TestCrawlLock(unittest.TestCase):
    def setUp(self):
        reset_crawl_lock_for_tests()

    def tearDown(self):
        reset_crawl_lock_for_tests()

    def test_exclusive_acquire_release(self):
        lock = CrawlLock()
        self.assertTrue(lock.try_acquire("complex"))
        self.assertFalse(lock.try_acquire("geo"))
        self.assertEqual(lock.owner(), "complex")
        lock.release("complex")
        self.assertTrue(lock.try_acquire("geo"))
        lock.release("geo")
        self.assertFalse(lock.is_held())

    def test_wrong_owner_does_not_release(self):
        lock = CrawlLock()
        lock.try_acquire("complex")
        lock.release("geo")
        self.assertTrue(lock.is_held())
        self.assertEqual(lock.owner(), "complex")
        lock.release("complex")
        self.assertFalse(lock.is_held())

    def test_singleton_reset_for_tests(self):
        lock = get_crawl_lock()
        self.assertTrue(lock.try_acquire("complex"))
        reset_crawl_lock_for_tests()
        self.assertFalse(get_crawl_lock().is_held())

    def test_collection_runtime_kwargs_keys(self):
        kwargs = collection_runtime_kwargs(
            {
                "include_pre_sale_rights": True,
                "detail_enrichment_enabled": False,
                "detail_enrichment_max_per_complex": 12,
                "detail_front_api_enabled": True,
                "article_api_page_delay_ms": 200,
            }
        )
        self.assertTrue(kwargs["include_pre_sale_rights"])
        self.assertFalse(kwargs["detail_enrichment_enabled"])
        self.assertEqual(kwargs["detail_enrichment_max_per_complex"], 12)
        self.assertEqual(kwargs["article_api_page_delay_ms"], 200)
        self.assertIn("detail_front_api_enabled", kwargs)


if __name__ == "__main__":
    unittest.main()
