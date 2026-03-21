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

    def _reset_result_state(self: Any):
        self.result_table.setRowCount(0)
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
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

        if level >= 40:
            color = theme_colors["error"]
        elif level >= 30:
            color = theme_colors["warning"]
        elif level == 10:
            color = theme_colors["text_secondary"]

        try:
            max_lines = max(200, int(settings.get("max_log_lines", 1500)))
        except (TypeError, ValueError):
            max_lines = 1500
        doc = self.log_browser.document()
        if getattr(self, "_log_max_block_count", None) != max_lines:
            doc.setMaximumBlockCount(max_lines)
            self._log_max_block_count = max_lines
        self.log_browser.append(f'<span style="color:{color}">{msg}</span>')
        sb = self.log_browser.verticalScrollBar()
        sb.setValue(sb.maximum())

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

    def _recompute_compact_row_favorite(self: Any, compact_key):
        row = self._compact_items_by_key.get(compact_key)
        if row is None:
            return False
        favorite_keys = self._favorite_keys_snapshot()
        source_keys = self._compact_source_keys_by_key.get(compact_key, set())
        is_favorite = any(source_key in favorite_keys for source_key in source_keys)
        row["is_favorite"] = bool(is_favorite)
        return bool(is_favorite)

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
        price_change = self._normalize_price_change(
            data.get("price_change", data.get("가격변동", 0))
        )

        show_new_badge = bool(settings.get("show_new_badge", True))
        show_price_change = bool(settings.get("show_price_change", True))
        try:
            price_change_threshold = max(0, int(settings.get("price_change_threshold", 0)))
        except (TypeError, ValueError):
            price_change_threshold = 0
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
        sort_item = QTableWidgetItem(price_sort_text)
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

    def _append_rows_compact_batch(self: Any, items):
        if not items:
            return
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

    def _append_rows_batch(self: Any, items):
        start_row = self.result_table.rowCount()
        row_count = len(items)
        if row_count == 0:
            return

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
