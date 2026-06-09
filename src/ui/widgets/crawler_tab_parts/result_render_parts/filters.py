from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabFilterRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _update_advanced_filter_badge(self: Any):
        if not hasattr(self, "lbl_advanced_filter"):
            return
        if self._advanced_filters:
            self.lbl_advanced_filter.setText("고급필터: ON")
            self.lbl_advanced_filter.setStyleSheet("color: #10b981; font-weight: 700;")
        else:
            self.lbl_advanced_filter.setText("고급필터: OFF")
            self.lbl_advanced_filter.setStyleSheet("color: #888;")

    def _apply_advanced_filter_items(self: Any, items):
        if not items:
            return []
        if not self._advanced_filters:
            return list(items)
        return [item for item in items if self._check_advanced_filter(item)]

    def set_advanced_filters(self: Any, filters):
        next_filters = filters or None
        if next_filters and self._is_default_advanced_filter(next_filters):
            next_filters = None
        self._advanced_filters = dict(next_filters) if isinstance(next_filters, dict) else None
        if hasattr(self, "btn_clear_advanced_filter"):
            self.btn_clear_advanced_filter.setEnabled(self._advanced_filters is not None)
        self._update_advanced_filter_badge()
        self._rebuild_result_views_from_collected_data()
        if self._advanced_filters:
            self.status_message.emit("고급 필터 적용됨")
        else:
            self.status_message.emit("고급 필터 해제됨")

    def _apply_current_filter_to_row(self: Any, row):
        text_lower = (self._pending_search_text or "").lower()
        searchable = self._row_search_cache[row] if row < len(self._row_search_cache) else ""
        hidden_by_text = bool(text_lower) and text_lower not in searchable
        hidden_by_advanced = False
        payload = self._row_payload_cache[row] if row < len(self._row_payload_cache) else None
        if self._advanced_filters and payload is not None:
            hidden_by_advanced = not self._check_advanced_filter(payload)
        hidden = hidden_by_text or hidden_by_advanced
        if self._row_hidden_state.get(row) != hidden:
            self.result_table.setRowHidden(row, hidden)
            self._row_hidden_state[row] = hidden
