import os
import sys
import unittest
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.retry_handler import RetryHandler


class TestRetryHandler(unittest.TestCase):
    def test_execute_with_retry_passes_base_delay(self):
        seen_base_delay = []
        attempts = {"count": 0}

        def _fn():
            if attempts["count"] == 0:
                attempts["count"] += 1
                raise TimeoutError("timeout")
            return "ok"

        def _wait_time(_error, _attempt, base_delay=2.0):
            seen_base_delay.append(base_delay)
            return 0.0

        with (
            patch("src.utils.retry_handler.NetworkErrorHandler.is_recoverable", return_value=True),
            patch("src.utils.retry_handler.NetworkErrorHandler.get_wait_time", side_effect=_wait_time),
            patch("src.utils.retry_handler.time.sleep", return_value=None),
        ):
            handler = RetryHandler(max_retries=1, base_delay=1.5)
            result = handler.execute_with_retry(_fn)

        self.assertEqual(result, "ok")
        self.assertEqual(seen_base_delay, [1.5])


if __name__ == "__main__":
    unittest.main()
