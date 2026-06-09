from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabFavoriteRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    @staticmethod
    def _favorite_key_for_item(item):
        if not isinstance(item, dict):
            return None
        article_id = str(item.get("매물ID", "") or "")
        complex_id = str(item.get("단지ID", "") or "")
        asset_type = str(item.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        if not article_id or not complex_id:
            return None
        return (asset_type, article_id, complex_id)

    def _favorite_keys_snapshot(self: Any):
        provider = self.favorite_keys_provider
        if callable(provider):
            try:
                value = provider()
            except Exception:
                value = None
            if isinstance(value, set):
                return set(value)
        current = getattr(self, "favorite_keys", set())
        return set(current) if isinstance(current, set) else set()

    def _decorate_favorite_state(self: Any, items):
        if not items:
            return []
        favorite_keys = self._favorite_keys_snapshot()
        decorated = []
        for item in items:
            row = dict(item or {})
            key = self._favorite_key_for_item(row)
            row["is_favorite"] = bool(key and key in favorite_keys)
            decorated.append(row)
        return decorated

    def _recompute_compact_row_favorite(self: Any, compact_key):
        row = self._compact_items_by_key.get(compact_key)
        if row is None:
            return False
        favorite_keys = self._favorite_keys_snapshot()
        source_keys = self._compact_source_keys_by_key.get(compact_key, set())
        is_favorite = any(source_key in favorite_keys for source_key in source_keys)
        row["is_favorite"] = bool(is_favorite)
        return bool(is_favorite)

    def _update_favorite_state_for_key(self: Any, favorite_key, is_favorite: bool):
        if not favorite_key:
            return

        favorite_state = bool(is_favorite)
        for item in self.collected_data:
            if self._favorite_key_for_item(item) == favorite_key:
                item["is_favorite"] = favorite_state

        if self._compact_duplicates:
            affected_compact_keys = set(self._compact_key_by_article.get(favorite_key) or set())
            for compact_key in affected_compact_keys:
                self._recompute_compact_row_favorite(compact_key)
                self._compact_dirty_keys.add(compact_key)
            if affected_compact_keys:
                self._schedule_compact_refresh(immediate=True)
                self.card_view.update_favorite_state(
                    lambda item: self._get_compact_key(item) in affected_compact_keys,
                    lambda item: bool(
                        self._compact_items_by_key.get(self._get_compact_key(item), {}).get("is_favorite")
                    ),
                )
            return

        for payload in self._row_payload_cache:
            if not isinstance(payload, dict):
                continue
            payload_key = (
                str(payload.get("자산유형", "APT") or "APT").strip().upper() or "APT",
                str(payload.get("매물ID", "") or ""),
                str(payload.get("단지ID", "") or ""),
            )
            if payload_key == favorite_key:
                payload["is_favorite"] = favorite_state

        self.card_view.update_favorite_state(
            lambda item: self._favorite_key_for_item(item) == favorite_key,
            lambda _item: favorite_state,
        )
