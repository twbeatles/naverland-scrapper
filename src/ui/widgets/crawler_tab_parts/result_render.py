from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabResultRenderMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _toggle_compact_duplicates(self: Any, enabled):
        self._compact_duplicates = bool(enabled)
        settings.set("compact_duplicate_listings", self._compact_duplicates)
        self._rebuild_result_views_from_collected_data()

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
        provider = getattr(self, "favorite_keys_provider", None)
        if callable(provider):
            try:
                value = provider()
            except Exception:
                value = None
            if value is not None:
                return set(value)
        current = getattr(self, "favorite_keys", None)
        return set(current) if current else set()

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
            price_int = PriceConverter.to_int(deposit)
        return trade_type, price_text, int(price_int or 0)

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

    @staticmethod
    def _normalize_price_change(value):
        if isinstance(value, str):
            return PriceConverter.to_int(value)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _merge_compact_item(self: Any, existing, incoming):
        existing["duplicate_count"] = int(existing.get("duplicate_count", 1) or 1) + 1
        existing["수집시각"] = incoming.get("수집시각", existing.get("수집시각", ""))
        if bool(incoming.get("is_favorite")):
            existing["is_favorite"] = True
        if bool(incoming.get("is_new") or incoming.get("신규여부")):
            existing["is_new"] = True
            existing["신규여부"] = True
        in_change = self._normalize_price_change(incoming.get("price_change", incoming.get("가격변동", 0)))
        ex_change = self._normalize_price_change(existing.get("price_change", existing.get("가격변동", 0)))
        if abs(in_change) > abs(ex_change):
            existing["price_change"] = in_change
            existing["가격변동"] = in_change

    def _reset_result_state(self: Any):
        self.result_table.setRowCount(0)
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        self._compact_items_by_key = {}
        self._compact_rows_data = []

    def _rebuild_result_views_from_collected_data(self: Any):
        self._reset_result_state()
        display_data = self._decorate_favorite_state(
            self._apply_advanced_filter_items(self.collected_data)
        )
        if not display_data:
            self.card_view.set_data([])
            return

        if self._compact_duplicates:
            self._append_rows_compact_batch(display_data)
            if self.view_mode == "card":
                self.card_view.set_data(list(self._compact_rows_data))
        else:
            self._append_rows_batch(display_data)
            if self.view_mode == "card":
                self.card_view.set_data(display_data)
        self._filter_results(self._pending_search_text)

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

    def append_log(self: Any, msg, level=20):
        theme_colors = COLORS[self.current_theme]
        color = theme_colors["text_primary"]
        
        if level >= 40: color = theme_colors["error"]
        elif level >= 30: color = theme_colors["warning"]
        elif level == 10: color = theme_colors["text_secondary"]
        
        self.log_browser.append(f'<span style="color:{color}">{msg}</span>')
        try:
            max_lines = max(200, int(settings.get("max_log_lines", 1500)))
        except (TypeError, ValueError):
            max_lines = 1500
        overflow = self.log_browser.document().blockCount() - max_lines
        if overflow > 0:
            cursor = self.log_browser.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(overflow):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
        # Scroll to bottom
        sb = self.log_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_items_batch(self: Any, items):
        if not items:
            return
        self.collected_data.extend(items)
        visible_items = self._decorate_favorite_state(self._apply_advanced_filter_items(items))
        if not visible_items:
            return
        if self._compact_duplicates:
            self._append_rows_compact_batch(visible_items)
            if self.view_mode == "card":
                self.card_view.set_data(list(self._compact_rows_data))
        else:
            self._append_rows_batch(visible_items)
            if self.view_mode == "card":
                self.card_view.append_data(visible_items)
        if self.view_mode == "card" and (self._advanced_filters or self._pending_search_text or self._compact_duplicates):
            self._apply_card_filters(self._pending_search_text)

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
            price_change = self._normalize_price_change(item.get("price_change", item.get("가격변동", 0)))
            is_new = bool(item.get("is_new") or item.get("신규여부"))
            payload = self._build_row_payload_from_data(
                data=item,
                trade_type=trade_type,
                price_int=price_int,
                area_val=area_val,
                price_change=price_change,
                is_new=is_new,
            )
            url = get_article_url(item.get("단지ID", ""), item.get("매물ID", ""), item.get("자산유형", "APT"))
            if url:
                lookup[url] = payload
        return lookup

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

    def _set_result_row(self: Any, row, data):
        trade_type, price_text, price_int = self._extract_price_values(data)
        area_val = self._area_float(data.get("면적(평)", 0))
        price_change = self._normalize_price_change(data.get("price_change", data.get("가격변동", 0)))

        show_new_badge = bool(settings.get("show_new_badge", True))
        show_price_change = bool(settings.get("show_price_change", True))
        try:
            price_change_threshold = max(0, int(settings.get("price_change_threshold", 0)))
        except (TypeError, ValueError):
            price_change_threshold = 0
        if price_change_threshold > 0 and abs(price_change) < price_change_threshold:
            price_change = 0

        self.result_table.setItem(row, self.COL_COMPLEX, QTableWidgetItem(str(data.get("단지명", ""))))
        self.result_table.setItem(row, self.COL_TRADE, QTableWidgetItem(trade_type))
        self.result_table.setItem(row, self.COL_PRICE, QTableWidgetItem(price_text))

        area_item = QTableWidgetItem(f"{area_val}평")
        area_item.setData(Qt.ItemDataRole.EditRole, float(area_val))
        self.result_table.setItem(row, self.COL_AREA, area_item)

        self.result_table.setItem(
            row, self.COL_PYEONG_PRICE, QTableWidgetItem(str(data.get("평당가_표시", "-")))
        )
        self.result_table.setItem(
            row, self.COL_FLOOR, QTableWidgetItem(str(data.get("층/방향", "")))
        )
        self.result_table.setItem(
            row, self.COL_FEATURE, QTableWidgetItem(str(data.get("타입/특징", "")))
        )

        dup_count = int(data.get("duplicate_count", 1) or 1)
        self.result_table.setItem(row, self.COL_DUP_COUNT, QTableWidgetItem(f"{dup_count}건"))

        is_new = bool(data.get("is_new") or data.get("신규여부"))
        new_badge_text = "N" if show_new_badge and is_new else ""
        self.result_table.setItem(row, self.COL_NEW, QTableWidgetItem(new_badge_text))

        if show_price_change and price_change != 0:
            change_text = PriceConverter.to_signed_string(price_change, zero_text="")
        else:
            change_text = ""
        self.result_table.setItem(row, self.COL_PRICE_CHANGE, QTableWidgetItem(change_text))
        self.result_table.setItem(row, self.COL_ASSET_TYPE, QTableWidgetItem(str(data.get("자산유형", ""))))
        self.result_table.setItem(
            row,
            self.COL_PREV_JEONSE,
            QTableWidgetItem(self._format_won_value(data.get("기전세금(원)", 0))),
        )
        self.result_table.setItem(
            row,
            self.COL_GAP_AMOUNT,
            QTableWidgetItem(self._format_won_value(data.get("갭금액(원)", 0), signed=True)),
        )
        self.result_table.setItem(
            row,
            self.COL_GAP_RATIO,
            QTableWidgetItem(self._format_gap_ratio(data.get("갭비율", 0))),
        )

        collect_time = str(data.get("수집시각", ""))
        self.result_table.setItem(row, self.COL_COLLECTED_AT, QTableWidgetItem(collect_time))
        self.result_table.setItem(row, self.COL_LINK, QTableWidgetItem("🔗"))

        article_url = get_article_url(
            data.get("단지ID", ""),
            data.get("매물ID", ""),
            data.get("자산유형", "APT"),
        )
        self.result_table.setItem(row, self.COL_URL, QTableWidgetItem(article_url))
        sort_item = QTableWidgetItem(str(price_int))
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

    def _append_rows_compact_batch(self: Any, items):
        for item in items:
            key = self._get_compact_key(item)
            if key in self._compact_items_by_key:
                self._merge_compact_item(self._compact_items_by_key[key], item)
            else:
                compact_item = dict(item)
                compact_item["duplicate_count"] = 1
                self._compact_items_by_key[key] = compact_item
        self._render_compact_rows()

    def _sort_compact_rows(self: Any, rows):
        criterion = self.combo_sort.currentText()
        key = criterion.split(" ")[0]
        is_asc = "↑" in criterion

        if key == "가격":
            rows.sort(key=lambda d: self._extract_price_values(d)[2], reverse=not is_asc)
        elif key == "면적":
            rows.sort(key=lambda d: self._area_float(d.get("면적(평)", 0)), reverse=not is_asc)
        elif key in ("거래", "거래유형"):
            rows.sort(key=lambda d: str(d.get("거래유형", "")), reverse=not is_asc)
        else:
            rows.sort(key=lambda d: str(d.get("단지명", "")), reverse=not is_asc)

    def _render_compact_rows(self: Any):
        rows = list(self._compact_items_by_key.values())
        self._sort_compact_rows(rows)
        self._compact_rows_data = rows

        self.result_table.setUpdatesEnabled(False)
        self.result_table.setSortingEnabled(False)
        self.result_table.setRowCount(len(rows))
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}

        for row, data in enumerate(rows):
            self._set_result_row(row, data)
            self._sync_row_search_cache(row)
            self._apply_current_filter_to_row(row)

        self.result_table.setUpdatesEnabled(True)

    def _append_rows_batch(self: Any, items):
        start_row = self.result_table.rowCount()
        row_count = len(items)
        if row_count == 0:
            return

        self.result_table.setSortingEnabled(False)
        self.result_table.setUpdatesEnabled(False)
        self.result_table.setRowCount(start_row + row_count)

        chunk_size = max(50, int(self._append_chunk_size))
        for start in range(0, row_count, chunk_size):
            end = min(row_count, start + chunk_size)
            for idx in range(start, end):
                row = start_row + idx
                data = dict(items[idx])
                data["duplicate_count"] = 1
                self._set_result_row(row, data)
                self._sync_row_search_cache(row)
                self._apply_current_filter_to_row(row)

        self.result_table.setUpdatesEnabled(True)

