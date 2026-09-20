from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, List
from src.utils import paths as paths_util
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper
from src.utils.json_store import atomic_write_json, load_json_with_recovery


class RecentlyViewedManager:
    """최근 본 매물 관리 (v13.0)"""

    MAX_ITEMS = 50

    def __init__(self, max_items: int | None = None):
        self.max_items = self._normalize_max_items(max_items)
        self._items: List[dict] = []
        self._lock = Lock()
        self._load()

    @classmethod
    def _normalize_max_items(cls, max_items: int | None) -> int:
        try:
            value = int(max_items if max_items is not None else cls.MAX_ITEMS)
        except (TypeError, ValueError):
            value = cls.MAX_ITEMS
        return max(1, value)

    @staticmethod
    def _storage_path() -> Path:
        return paths_util.get_data_dir() / "recently_viewed.json"

    @staticmethod
    def _article_identity(article: dict[str, Any]) -> tuple[str, str, str]:
        asset_type = str(article.get("자산유형", article.get("asset_type", "APT")) or "APT").strip().upper() or "APT"
        complex_id = str(article.get("단지ID", article.get("complex_id", "")) or "").strip()
        article_id = str(article.get("매물ID", article.get("article_id", "")) or "").strip()
        return asset_type, complex_id, article_id

    def _load(self):
        """파일에서 로드"""
        payload = load_json_with_recovery(
            self._storage_path(),
            default_factory=list,
            logger_name="RecentlyViewedManager",
            label="recently_viewed",
        )
        self._items = list(payload[: self.max_items]) if isinstance(payload, list) else []

    def _save(self):
        """파일에 저장"""
        try:
            atomic_write_json(self._storage_path(), self._items[: self.max_items])
        except OSError as e:
            get_logger("RecentlyViewedManager").warning(f"최근 본 매물 저장 실패: {e}")

    def set_max_items(self, max_items: int | None) -> None:
        with self._lock:
            self.max_items = self._normalize_max_items(max_items)
            self._items = self._items[: self.max_items]
            self._save()

    def add(self, article: dict):
        """최근 본 매물 추가"""
        with self._lock:
            article_copy = dict(article or {})
            _, _, article_id = self._article_identity(article_copy)
            if not article_id:
                return

            article_key = self._article_identity(article_copy)
            self._items = [
                item for item in self._items
                if self._article_identity(item) != article_key
            ]

            article_copy["viewed_at"] = DateTimeHelper.now_string()
            self._items.insert(0, article_copy)
            self._items = self._items[: self.max_items]
            self._save()

    def get_recent(self, count: int | None = None) -> List[dict]:
        """최근 본 매물 목록"""
        limit = self.max_items if count is None else max(1, int(count))
        return self._items[:limit]

    def clear(self):
        """전체 삭제"""
        with self._lock:
            self._items = []
            self._save()
