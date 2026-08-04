"""Process-wide crawl mutex so complex / geo / schedule never share DB writes concurrently."""

from __future__ import annotations

from threading import Lock
from typing import Optional


class CrawlLock:
    def __init__(self) -> None:
        self._lock = Lock()
        self._owner: Optional[str] = None

    def try_acquire(self, owner: str) -> bool:
        token = str(owner or "").strip() or "unknown"
        with self._lock:
            if self._owner is not None:
                return False
            self._owner = token
            return True

    def release(self, owner: str | None = None) -> None:
        """Release if owner matches, or if owner is None (best-effort cleanup)."""
        with self._lock:
            if owner is None:
                self._owner = None
                return
            if self._owner == str(owner).strip():
                self._owner = None

    def force_release(self) -> None:
        with self._lock:
            self._owner = None

    def is_held(self) -> bool:
        with self._lock:
            return self._owner is not None

    def owner(self) -> Optional[str]:
        with self._lock:
            return self._owner


_CRAWL_LOCK = CrawlLock()


def get_crawl_lock() -> CrawlLock:
    return _CRAWL_LOCK


def reset_crawl_lock_for_tests() -> None:
    _CRAWL_LOCK.force_release()
