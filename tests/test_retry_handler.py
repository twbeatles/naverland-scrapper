import os
import sys
import time
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.retry_handler import RetryCancelledError, RetryHandler


class TestRetryHandler(unittest.TestCase):
    def test_execute_with_retry_cancelled_while_waiting(self):
        handler = RetryHandler(max_retries=3, base_delay=0.2)

        start = time.monotonic()

        def _failing():
            raise TimeoutError("temporary network error")

        def _cancel_checker():
            return (time.monotonic() - start) >= 0.05

        with self.assertRaises(RetryCancelledError):
            handler.execute_with_retry(
                _failing,
                cancel_checker=_cancel_checker,
                sleep_chunk_seconds=0.05,
            )

    def test_execute_with_retry_cancelled_before_attempt(self):
        handler = RetryHandler(max_retries=1, base_delay=0.1)
        called = {"count": 0}

        def _func():
            called["count"] += 1
            return "ok"

        with self.assertRaises(RetryCancelledError):
            handler.execute_with_retry(_func, cancel_checker=lambda: True)

        self.assertEqual(called["count"], 0)


if __name__ == "__main__":
    unittest.main()

