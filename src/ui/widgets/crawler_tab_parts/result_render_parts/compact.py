from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabCompactRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _toggle_compact_duplicates(self: Any, enabled):
        self._compact_duplicates = bool(enabled)
        settings.set("compact_duplicate_listings", self._compact_duplicates)
        self._rebuild_result_views_from_collected_data()

    def _get_compact_key(self: Any, data):
        trade_type, price_text, _ = self._extract_price_values(data)
        return (
            str(data.get("자산유형", "APT") or "APT"),
            str(data.get("단지명", "") or ""),
            str(data.get("단지ID", "") or ""),
            trade_type,
            str(price_text),
            self._area_float(data.get("면적(평)", 0)),
            str(data.get("층/방향", "") or ""),
        )

    def _merge_compact_item(self: Any, existing, incoming):
        existing["duplicate_count"] = int(existing.get("duplicate_count", 1) or 1) + 1
        existing["수집시각"] = incoming.get("수집시각", existing.get("수집시각", ""))
        if bool(incoming.get("is_favorite")):
            existing["is_favorite"] = True
        if bool(incoming.get("is_new") or incoming.get("신규여부")):
            existing["is_new"] = True
            existing["신규여부"] = True
        in_change = self._normalize_price_change(
            incoming.get("price_change", incoming.get("가격변동", 0))
        )
        ex_change = self._normalize_price_change(
            existing.get("price_change", existing.get("가격변동", 0))
        )
        if abs(in_change) > abs(ex_change):
            existing["price_change"] = in_change
            existing["가격변동"] = in_change

    def _consume_compact_item(self: Any, item):
        compact_key = self._get_compact_key(item)
        article_key = self._favorite_key_for_item(item)
        existing = self._compact_items_by_key.get(compact_key)
        created = existing is None
        if created:
            existing = dict(item or {})
            existing["duplicate_count"] = 1
            self._compact_items_by_key[compact_key] = existing
        else:
            self._merge_compact_item(existing, item)
        if article_key:
            self._compact_source_keys_by_key.setdefault(compact_key, set()).add(article_key)
            self._compact_key_by_article.setdefault(article_key, set()).add(compact_key)
        return compact_key, existing, created

    def _compact_sort_descriptor(self: Any):
        criterion = str(self.combo_sort.currentText() or "")
        sort_key = criterion.split(" ")[0] if criterion else "가격"
        is_asc = "↑" in criterion
        return sort_key, is_asc

    def _compact_sort_value(self: Any, data):
        sort_key, _is_asc = self._compact_sort_descriptor()
        if sort_key == "가격":
            return self._extract_price_values(data)[2]
        if sort_key == "면적":
            return self._area_float(data.get("면적(평)", 0))
        if sort_key in ("거래", "거래유형"):
            return str(data.get("거래유형", "") or "")
        return str(data.get("단지명", "") or "")

    def _find_compact_insert_index(self: Any, data):
        target = self._compact_sort_value(data)
        _sort_key, is_asc = self._compact_sort_descriptor()
        for index, current in enumerate(self._compact_rows_data):
            current_value = self._compact_sort_value(current)
            if is_asc:
                if target < current_value:
                    return index
            else:
                if target > current_value:
                    return index
        return len(self._compact_rows_data)

    def _reindex_compact_row_map(self: Any, start_row: int = 0):
        if start_row <= 0:
            self._compact_row_index_by_key = {}
            start_row = 0
        for row in range(start_row, len(self._compact_rows_data)):
            self._compact_row_index_by_key[self._get_compact_key(self._compact_rows_data[row])] = row

    def _compact_updates_should_coalesce(self: Any) -> bool:
        thread = getattr(self, "crawler_thread", None)
        if thread is None:
            return False
        try:
            return bool(thread.isRunning())
        except Exception:
            return False

    def _schedule_compact_refresh(self: Any, *, full: bool = False, immediate: bool = False):
        if full:
            self._compact_full_refresh_pending = True
        if immediate or not self._compact_updates_should_coalesce():
            if hasattr(self, "_compact_refresh_timer"):
                self._compact_refresh_timer.stop()
            self._flush_compact_updates()
            return
        self._compact_refresh_timer.start()

    def _flush_compact_updates(self: Any):
        if self._compact_full_refresh_pending:
            self._compact_full_refresh_pending = False
            self._compact_dirty_keys.clear()
            self._render_compact_rows()
            return
        self._refresh_result_render_options()

        dirty_keys = [
            key
            for key in self._compact_dirty_keys
            if key in self._compact_items_by_key and key in self._compact_row_index_by_key
        ]
        if not dirty_keys:
            self._compact_dirty_keys.clear()
            return

        self.result_table.setSortingEnabled(False)
        self.result_table.setUpdatesEnabled(False)
        self.result_table.blockSignals(True)
        try:
            for compact_key in dirty_keys:
                row = self._compact_row_index_by_key.get(compact_key)
                if row is None:
                    continue
                data = self._compact_items_by_key.get(compact_key)
                if data is None:
                    continue
                self._set_result_row(row, data)
                self._apply_current_filter_to_row(row)
        finally:
            self.result_table.blockSignals(False)
            self.result_table.setUpdatesEnabled(True)
        self._compact_dirty_keys.clear()

    def _append_rows_compact_batch(self: Any, items):
        if not items:
            return
        self._refresh_result_render_options()
        self.result_table.setSortingEnabled(False)
        new_rows = []
        for item in items:
            compact_key, compact_item, created = self._consume_compact_item(item)
            self._recompute_compact_row_favorite(compact_key)
            if created:
                new_rows.append((compact_key, compact_item))
            self._compact_dirty_keys.add(compact_key)
        if new_rows:
            start_row = self.result_table.rowCount()
            self.result_table.setRowCount(start_row + len(new_rows))
            for offset, (compact_key, compact_item) in enumerate(new_rows):
                row = start_row + offset
                self._compact_rows_data.append(compact_item)
                self._row_search_cache.append("")
                self._row_payload_cache.append({})
                self._compact_row_index_by_key[compact_key] = row
        self._schedule_compact_refresh()

    def _sort_compact_rows(self: Any, rows):
        sort_key, is_asc = self._compact_sort_descriptor()
        if sort_key == "가격":
            rows.sort(key=lambda d: self._extract_price_values(d)[2], reverse=not is_asc)
        elif sort_key == "면적":
            rows.sort(key=lambda d: self._area_float(d.get("면적(평)", 0)), reverse=not is_asc)
        elif sort_key in ("거래", "거래유형"):
            rows.sort(key=lambda d: str(d.get("거래유형", "")), reverse=not is_asc)
        else:
            rows.sort(key=lambda d: str(d.get("단지명", "")), reverse=not is_asc)

    def _render_compact_rows(self: Any):
        self._refresh_result_render_options()
        for compact_key in list(self._compact_items_by_key.keys()):
            self._recompute_compact_row_favorite(compact_key)
        rows = list(self._compact_items_by_key.values())
        self._sort_compact_rows(rows)
        self._compact_rows_data = rows

        self.result_table.setUpdatesEnabled(False)
        self.result_table.setSortingEnabled(False)
        self.result_table.setRowCount(len(rows))
        self.result_table.blockSignals(True)
        self._row_search_cache = [""] * len(rows)
        self._row_payload_cache = [{} for _ in rows]
        self._row_hidden_state = {}
        self._reindex_compact_row_map()

        try:
            for row, data in enumerate(rows):
                self._set_result_row(row, data)
                self._apply_current_filter_to_row(row)
        finally:
            self.result_table.blockSignals(False)
            self.result_table.setUpdatesEnabled(True)
        self._compact_dirty_keys.clear()
        self._compact_full_refresh_pending = False
