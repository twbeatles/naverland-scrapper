from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabTableRowRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    @staticmethod
    def _area_float(value):
        try:
            return round(float(value or 0), 1)
        except (TypeError, ValueError):
            return 0.0

    def _extract_price_values(self: Any, data):
        trade_type = str(data.get("거래유형", "") or "")
        if trade_type == "매매":
            price_text = str(data.get("매매가", "") or "")
            price_int = PriceConverter.to_int(price_text)
        else:
            deposit = str(data.get("보증금", "") or "")
            monthly = str(data.get("월세", "") or "")
            price_text = f"{deposit}/{monthly}" if monthly else deposit
            price_int = PriceConverter.representative_price_int(data, trade_type)
        return trade_type, price_text, int(price_int or 0)

    @staticmethod
    def _normalize_price_change(value):
        if isinstance(value, str):
            return PriceConverter.to_int(value)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _reset_result_state(self: Any):
        self.result_table.setRowCount(0)
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        self._refresh_result_render_options()
        self._compact_items_by_key = {}
        self._compact_rows_data = []
        self._compact_row_index_by_key = {}
        self._compact_source_keys_by_key = {}
        self._compact_key_by_article = {}
        self._compact_dirty_keys = set()
        self._compact_full_refresh_pending = False
        self._card_refresh_pending = False
        if hasattr(self, "_compact_refresh_timer"):
            self._compact_refresh_timer.stop()
        if hasattr(self, "_card_refresh_timer"):
            self._card_refresh_timer.stop()

    def _refresh_result_render_options(self: Any):
        try:
            threshold = max(0, int(settings.get("price_change_threshold", 0)))
        except (TypeError, ValueError):
            threshold = 0
        self._result_render_options = {
            "show_new_badge": bool(settings.get("show_new_badge", True)),
            "show_price_change": bool(settings.get("show_price_change", True)),
            "price_change_threshold": threshold,
        }
        return self._result_render_options

    def _rebuild_result_views_from_collected_data(self: Any):
        self._reset_result_state()
        display_data = self._decorate_favorite_state(
            self._apply_advanced_filter_items(self.collected_data)
        )
        if not display_data:
            self.card_view.set_data([])
            return

        if self._compact_duplicates:
            for item in display_data:
                compact_key, _existing, _created = self._consume_compact_item(item)
                self._recompute_compact_row_favorite(compact_key)
            self._render_compact_rows()
            if self.view_mode == "card":
                self.card_view.set_data(list(self._compact_rows_data))
        else:
            self._append_rows_batch(display_data)
            if self.view_mode == "card":
                self.card_view.set_data(display_data)
        self._filter_results(self._pending_search_text)

    def _on_items_batch(self: Any, items):
        if not items:
            return
        self.collected_data.extend(items)
        visible_items = self._decorate_favorite_state(self._apply_advanced_filter_items(items))
        if not visible_items:
            return
        if self._compact_duplicates:
            self._append_rows_compact_batch(visible_items)
            if self.view_mode == "card" and self.view_stack.currentWidget() is self.card_view:
                self._schedule_card_view_refresh()
        else:
            self._append_rows_batch(visible_items)
            if (
                self.view_mode == "card"
                and self.view_stack.currentWidget() is self.card_view
                and (self._advanced_filters or self._pending_search_text)
            ):
                self._schedule_card_view_refresh()
            elif self.view_mode == "card":
                self.card_view.append_data(visible_items)

    def _sync_row_search_cache(self: Any, row):
        values = []
        for col in range(self.result_table.columnCount()):
            item = self.result_table.item(row, col)
            if item:
                values.append(item.text())
        searchable = " ".join(values).lower()
        while len(self._row_search_cache) <= row:
            self._row_search_cache.append("")
        self._row_search_cache[row] = searchable
        return searchable

    @staticmethod
    def _build_row_searchable_text(values):
        return " ".join(str(value or "") for value in values).lower()

    @staticmethod
    def _format_won_value(value, signed: bool = False) -> str:
        try:
            won = int(value or 0)
        except (TypeError, ValueError):
            won = 0
        manwon = int(abs(won) / 10_000)
        text = PriceConverter.to_string(manwon) if manwon > 0 else ""
        if not signed:
            return text
        if won > 0 and text:
            return f"+{text}"
        if won < 0 and text:
            return f"-{text}"
        return text

    @staticmethod
    def _format_gap_ratio(value) -> str:
        try:
            ratio = float(value or 0)
        except (TypeError, ValueError):
            ratio = 0.0
        return f"{ratio:.4f}" if ratio else ""

    def _build_row_payload_from_data(self: Any, data, trade_type, price_int, area_val, price_change, is_new):
        payload = dict(data or {})
        payload["단지명"] = str(payload.get("단지명", "") or "")
        payload["단지ID"] = str(payload.get("단지ID", "") or "")
        payload["매물ID"] = str(payload.get("매물ID", "") or "")
        payload["자산유형"] = str(payload.get("자산유형", "APT") or "APT").strip().upper() or "APT"
        payload["거래유형"] = trade_type
        payload["price_int"] = int(price_int or 0)
        payload["면적(평)"] = float(area_val or 0)
        payload["층/방향"] = str(data.get("층/방향", "") if isinstance(data, dict) else "")
        payload["타입/특징"] = str(data.get("타입/특징", "") if isinstance(data, dict) else "")
        payload["is_new"] = bool(is_new)
        payload["is_favorite"] = bool(data.get("is_favorite")) if isinstance(data, dict) else False
        payload["price_change"] = int(price_change or 0)
        return payload

    def _build_row_payload_from_table(self: Any, row):
        def _text(col):
            item = self.result_table.item(row, col)
            return item.text().strip() if item else ""

        change_text = _text(self.COL_PRICE_CHANGE)
        sign = -1 if change_text.startswith("-") else 1
        change_value = PriceConverter.to_int(change_text.lstrip("+-"))
        price_int_text = _text(self.COL_PRICE_SORT)
        try:
            price_int = int(price_int_text.replace(",", "")) if price_int_text else 0
        except ValueError:
            price_int = 0
        area_val = self._area_float(_text(self.COL_AREA).replace("평", ""))
        payload = {
            "단지명": _text(self.COL_COMPLEX),
            "거래유형": _text(self.COL_TRADE),
            "price_int": int(price_int),
            "면적(평)": float(area_val),
            "층/방향": _text(self.COL_FLOOR),
            "타입/특징": _text(self.COL_FEATURE),
            "is_new": bool(_text(self.COL_NEW)),
            "price_change": int(sign * change_value),
        }
        return payload

    def _build_payload_lookup_by_url(self: Any):
        if self._compact_duplicates:
            source = list(self._compact_rows_data)
        else:
            source = self._decorate_favorite_state(self.collected_data)
        lookup = {}
        for item in source:
            trade_type, _, price_int = self._extract_price_values(item)
            area_val = self._area_float(item.get("면적(평)", 0))
            price_change = self._normalize_price_change(
                item.get("price_change", item.get("가격변동", 0))
            )
            is_new = bool(item.get("is_new") or item.get("신규여부"))
            payload = self._build_row_payload_from_data(
                data=item,
                trade_type=trade_type,
                price_int=price_int,
                area_val=area_val,
                price_change=price_change,
                is_new=is_new,
            )
            url = get_article_url(
                item.get("단지ID", ""),
                item.get("매물ID", ""),
                item.get("자산유형", "APT"),
            )
            if url:
                lookup[url] = payload
        return lookup

    def _set_result_row(self: Any, row, data):
        trade_type, price_text, price_int = self._extract_price_values(data)
        area_val = self._area_float(data.get("면적(평)", 0))
        price_change = self._normalize_price_change(
            data.get("price_change", data.get("가격변동", 0))
        )

        render_options = getattr(self, "_result_render_options", None)
        if not isinstance(render_options, dict):
            render_options = self._refresh_result_render_options()
        show_new_badge = bool(render_options.get("show_new_badge", True))
        show_price_change = bool(render_options.get("show_price_change", True))
        price_change_threshold = int(render_options.get("price_change_threshold", 0) or 0)
        if price_change_threshold > 0 and abs(price_change) < price_change_threshold:
            price_change = 0

        complex_name = str(data.get("단지명", ""))
        self.result_table.setItem(row, self.COL_COMPLEX, QTableWidgetItem(complex_name))
        self.result_table.setItem(row, self.COL_TRADE, QTableWidgetItem(trade_type))
        self.result_table.setItem(row, self.COL_PRICE, QTableWidgetItem(price_text))

        area_text = f"{area_val}평"
        area_item = QTableWidgetItem(f"{area_val}평")
        area_item.setData(Qt.ItemDataRole.EditRole, float(area_val))
        self.result_table.setItem(row, self.COL_AREA, area_item)

        pyeong_price_text = str(data.get("평당가_표시", "-"))
        self.result_table.setItem(row, self.COL_PYEONG_PRICE, QTableWidgetItem(pyeong_price_text))
        floor_text = str(data.get("층/방향", ""))
        self.result_table.setItem(row, self.COL_FLOOR, QTableWidgetItem(floor_text))
        feature_text = str(data.get("타입/특징", ""))
        self.result_table.setItem(row, self.COL_FEATURE, QTableWidgetItem(feature_text))

        dup_count = int(data.get("duplicate_count", 1) or 1)
        dup_count_text = f"{dup_count}건"
        self.result_table.setItem(row, self.COL_DUP_COUNT, QTableWidgetItem(dup_count_text))

        is_new = bool(data.get("is_new") or data.get("신규여부"))
        new_badge_text = "N" if show_new_badge and is_new else ""
        self.result_table.setItem(row, self.COL_NEW, QTableWidgetItem(new_badge_text))

        if show_price_change and price_change != 0:
            change_text = PriceConverter.to_signed_string(price_change, zero_text="")
        else:
            change_text = ""
        self.result_table.setItem(row, self.COL_PRICE_CHANGE, QTableWidgetItem(change_text))
        asset_type_text = str(data.get("자산유형", ""))
        self.result_table.setItem(row, self.COL_ASSET_TYPE, QTableWidgetItem(asset_type_text))
        prev_jeonse_text = self._format_won_value(data.get("기전세금(원)", 0))
        self.result_table.setItem(row, self.COL_PREV_JEONSE, QTableWidgetItem(prev_jeonse_text))
        gap_amount_text = self._format_won_value(data.get("갭금액(원)", 0), signed=True)
        self.result_table.setItem(row, self.COL_GAP_AMOUNT, QTableWidgetItem(gap_amount_text))
        gap_ratio_text = self._format_gap_ratio(data.get("갭비율", 0))
        self.result_table.setItem(row, self.COL_GAP_RATIO, QTableWidgetItem(gap_ratio_text))

        collect_time = str(data.get("수집시각", ""))
        self.result_table.setItem(row, self.COL_COLLECTED_AT, QTableWidgetItem(collect_time))
        self.result_table.setItem(row, self.COL_LINK, QTableWidgetItem("🔗"))

        article_url = get_article_url(
            data.get("단지ID", ""),
            data.get("매물ID", ""),
            data.get("자산유형", "APT"),
        )
        self.result_table.setItem(row, self.COL_URL, QTableWidgetItem(article_url))
        price_sort_text = str(price_int)
        sort_item = SortableTableWidgetItem(price_sort_text)
        sort_item.setData(Qt.ItemDataRole.EditRole, int(price_int))
        self.result_table.setItem(row, self.COL_PRICE_SORT, sort_item)
        payload = self._build_row_payload_from_data(
            data=data,
            trade_type=trade_type,
            price_int=price_int,
            area_val=area_val,
            price_change=price_change,
            is_new=is_new,
        )
        while len(self._row_payload_cache) <= row:
            self._row_payload_cache.append({})
        self._row_payload_cache[row] = payload
        searchable = self._build_row_searchable_text(
            [
                complex_name,
                trade_type,
                price_text,
                area_text,
                pyeong_price_text,
                floor_text,
                feature_text,
                dup_count_text,
                new_badge_text,
                change_text,
                asset_type_text,
                prev_jeonse_text,
                gap_amount_text,
                gap_ratio_text,
                collect_time,
                "🔗",
                article_url,
                price_sort_text,
            ]
        )
        while len(self._row_search_cache) <= row:
            self._row_search_cache.append("")
        self._row_search_cache[row] = searchable
        return payload, searchable

    def _append_rows_batch(self: Any, items):
        start_row = self.result_table.rowCount()
        row_count = len(items)
        if row_count == 0:
            return

        self._refresh_result_render_options()
        self.result_table.setSortingEnabled(False)
        self.result_table.setUpdatesEnabled(False)
        self.result_table.blockSignals(True)
        self.result_table.setRowCount(start_row + row_count)

        needed = start_row + row_count
        if len(self._row_search_cache) < needed:
            self._row_search_cache.extend([""] * (needed - len(self._row_search_cache)))
        if len(self._row_payload_cache) < needed:
            self._row_payload_cache.extend({} for _ in range(needed - len(self._row_payload_cache)))

        chunk_size = max(50, int(self._append_chunk_size))
        try:
            for start in range(0, row_count, chunk_size):
                end = min(row_count, start + chunk_size)
                for idx in range(start, end):
                    row = start_row + idx
                    data = dict(items[idx])
                    data["duplicate_count"] = 1
                    self._set_result_row(row, data)
                    self._apply_current_filter_to_row(row)
        finally:
            self.result_table.blockSignals(False)
            self.result_table.setUpdatesEnabled(True)
