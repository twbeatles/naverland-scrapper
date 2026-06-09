from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabCardSyncMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _toggle_view_mode(self: Any):
        if self.btn_view_mode.isChecked():
            self.view_mode = "card"
            self.btn_view_mode.setText("📄 테이블")
            self.view_stack.setCurrentWidget(self.card_view)
            if self.collected_data:
                if self._compact_duplicates:
                    self.card_view.set_data(list(self._compact_rows_data))
                else:
                    self.card_view.set_data(
                        self._decorate_favorite_state(
                            self._apply_advanced_filter_items(self.collected_data)
                        )
                    )
                if self._advanced_filters or self._pending_search_text:
                    self._apply_card_filters(self._pending_search_text)
        else:
            self.view_mode = "table"
            self.btn_view_mode.setText("🃏 카드뷰")
            self.view_stack.setCurrentWidget(self.result_table)
        settings.set("view_mode", self.view_mode)

    def _schedule_card_view_refresh(self: Any, *, immediate: bool = False):
        self._card_refresh_pending = True
        if self.view_mode != "card" or self.view_stack.currentWidget() is not self.card_view:
            return
        if immediate or not self._compact_updates_should_coalesce():
            if hasattr(self, "_card_refresh_timer"):
                self._card_refresh_timer.stop()
            self._flush_card_view_refresh()
            return
        if self._card_refresh_timer.isActive():
            return
        self._card_refresh_timer.start()

    def _flush_card_view_refresh(self: Any):
        if not self._card_refresh_pending:
            return
        self._card_refresh_pending = False
        if self.view_mode != "card" or self.view_stack.currentWidget() is not self.card_view:
            return
        self._apply_card_filters(self._pending_search_text)
