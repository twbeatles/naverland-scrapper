import time
from typing import Callable, Optional

from src.utils.error_handler import NetworkErrorHandler
from src.utils.logger import get_logger


class RetryCancelledError(Exception):
    """Raised when a retry flow is cancelled by caller request."""


class RetryHandler:
    """Retry helper with exponential backoff and cancellation support."""

    def __init__(self, max_retries: int = 3, base_delay: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._logger = get_logger("RetryHandler")

    def execute_with_retry(
        self,
        func,
        *args,
        cancel_checker: Optional[Callable[[], bool]] = None,
        sleep_chunk_seconds: float = 0.2,
        **kwargs,
    ):
        """Execute a callable with recoverable retry policy."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            if self._is_cancelled(cancel_checker):
                raise RetryCancelledError("retry cancelled before attempt")
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if self._is_cancelled(cancel_checker):
                    raise RetryCancelledError("retry cancelled after exception") from e

                if not NetworkErrorHandler.is_recoverable(e):
                    self._logger.error(f"recoverable check failed: {e}")
                    raise

                if attempt < self.max_retries:
                    wait_time = NetworkErrorHandler.get_wait_time(
                        e,
                        attempt,
                        base_delay=self.base_delay,
                    )

                    if self.is_rate_limited(e):
                        wait_time = max(wait_time, 30)
                        self._logger.warning(f"rate limit detected; waiting {wait_time:.1f}s")
                    else:
                        self._logger.warning(
                            f"retry in {wait_time:.1f}s ({attempt + 1}/{self.max_retries}): {e}"
                        )

                    self._sleep_with_cancel(
                        wait_time,
                        cancel_checker=cancel_checker,
                        chunk_seconds=sleep_chunk_seconds,
                    )

        raise last_error if last_error else Exception("unknown retry error")

    def is_rate_limited(self, error) -> bool:
        """Detect common rate-limit signatures."""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "429",
            "too many requests",
            "rate limit",
            "접속이 차단",
            "일시적으로 사용",
            "잠시 후",
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    @staticmethod
    def _is_cancelled(cancel_checker: Optional[Callable[[], bool]]) -> bool:
        if not callable(cancel_checker):
            return False
        try:
            return bool(cancel_checker())
        except Exception:
            return False

    def _sleep_with_cancel(
        self,
        wait_time: float,
        cancel_checker: Optional[Callable[[], bool]],
        chunk_seconds: float = 0.2,
    ):
        remaining = max(0.0, float(wait_time or 0.0))
        chunk = min(0.2, max(0.05, float(chunk_seconds or 0.2)))
        while remaining > 0:
            if self._is_cancelled(cancel_checker):
                raise RetryCancelledError("retry cancelled while waiting")
            step = chunk if remaining > chunk else remaining
            time.sleep(step)
            remaining -= step
