from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabFilterRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _update_advanced_filter_badge(self: Any):
        active = bool(self._advanced_filters)
        if hasattr(self, "lbl_advanced_filter"):
            self.lbl_advanced_filter.setText("상세 필터로 일부 매물만 보고 있습니다." if active else "")
        notice = getattr(self, "filter_notice", None)
        if notice is not None:
            notice.setVisible(active)
        more_btn = getattr(self, "btn_result_more", None)
        if more_btn is not None:
            more_btn.setText("정렬·필터 (적용 중)" if active else "정렬·필터")

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
        enabled = self._advanced_filters is not None
        if hasattr(self, "btn_clear_advanced_filter"):
            self.btn_clear_advanced_filter.setEnabled(enabled)
        clear_action = getattr(self, "_clear_filter_menu_action", None)
        if clear_action is not None:
            clear_action.setEnabled(enabled)
        self._update_advanced_filter_badge()
        self._rebuild_result_views_from_collected_data()
        if self._advanced_filters:
            self.status_message.emit("상세 필터를 적용했습니다.")
        else:
            self.status_message.emit("상세 필터를 풀었습니다.")

    def _apply_current_filter_to_row(self: Any, row):
        text_lower = (self._pending_search_text or "").lower()
        searchable = self._row_search_cache[row] if row < len(self._row_search_cache) else ""
        text_norm = self._normalize_search_text(self._pending_search_text or "")
        searchable_norm = self._normalize_search_text(searchable)
        hidden_by_text = (
            bool(text_lower)
            and text_lower not in searchable
            and (not text_norm or text_norm not in searchable_norm)
        )
        hidden_by_advanced = False
        payload = self._row_payload_cache[row] if row < len(self._row_payload_cache) else None
        if self._advanced_filters and payload is not None:
            hidden_by_advanced = not self._check_advanced_filter(payload)
        hidden = hidden_by_text or hidden_by_advanced
        if self._row_hidden_state.get(row) != hidden:
            self.result_table.setRowHidden(row, hidden)
            self._row_hidden_state[row] = hidden
