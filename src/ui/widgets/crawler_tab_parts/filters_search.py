from __future__ import annotations


class CrawlerTabFiltersSearchMixin:
    def _on_search_text_changed(self, text):
        self._pending_search_text = text
        self._search_timer.start()

    def _apply_search_filter(self):
        self._filter_results(self._pending_search_text)

    def _rebuild_row_search_cache_from_table(self):
        rows = self.result_table.rowCount()
        self._row_search_cache = []
        self._row_payload_cache = []
        self._row_hidden_state = {}
        payload_lookup = self._build_payload_lookup_by_url()
        for r in range(rows):
            values = []
            for c in range(self.result_table.columnCount()):
                item = self.result_table.item(r, c)
                if item:
                    values.append(item.text())
            self._row_search_cache.append(" ".join(values).lower())
            url_item = self.result_table.item(r, self.COL_URL)
            row_url = url_item.text().strip() if url_item else ""
            payload = payload_lookup.get(row_url) or self._build_row_payload_from_table(r)
            self._row_payload_cache.append(payload)

    @staticmethod
    def _is_default_advanced_filter(filters: dict) -> bool:
        defaults = {
            "price_min": 0,
            "price_max": 9999999,
            "area_min": 0,
            "area_max": 500,
            "floor_low": True,
            "floor_mid": True,
            "floor_high": True,
            "only_new": False,
            "only_price_down": False,
            "only_price_change": False,
        }
        for key, val in defaults.items():
            if filters.get(key) != val:
                return False
        if filters.get("include_keywords"):
            return False
        if filters.get("exclude_keywords"):
            return False
        return True

    @staticmethod
    def _floor_category(floor_text: str):
        text = str(floor_text or "")
        if "저층" in text:
            return "low"
        if "중층" in text:
            return "mid"
        if "고층" in text or "탑" in text:
            return "high"
        m = re.search(r"(\d+)\s*층", text)
        if not m:
            return None
        try:
            floor_num = int(m.group(1))
        except ValueError:
            return None
        if floor_num <= 3:
            return "low"
        if floor_num <= 10:
            return "mid"
        return "high"

    def _check_advanced_filter(self, d):
        if not self._advanced_filters:
            return True
        f = self._advanced_filters

        price_int = d.get("price_int")
        if price_int is None:
            price_text = d.get("매매가") or d.get("보증금") or ""
            price_int = PriceConverter.to_int(price_text)
        if price_int < f.get("price_min", 0) or price_int > f.get("price_max", 9999999):
            return False

        area = self._area_float(d.get("면적(평)", 0))
        if area < f.get("area_min", 0) or area > f.get("area_max", 9999999):
            return False

        floor_category = self._floor_category(d.get("층/방향", ""))
        if floor_category == "low" and not f.get("floor_low", True):
            return False
        if floor_category == "mid" and not f.get("floor_mid", True):
            return False
        if floor_category == "high" and not f.get("floor_high", True):
            return False

        if f.get("only_new") and not bool(d.get("is_new", False)):
            return False

        price_change = d.get("price_change", 0)
        if isinstance(price_change, str):
            try:
                sign = -1 if str(price_change).strip().startswith("-") else 1
                price_change = sign * PriceConverter.to_int(str(price_change).strip().lstrip("+-"))
            except Exception:
                price_change = 0

        if f.get("only_price_down") and price_change >= 0:
            return False
        if f.get("only_price_change") and price_change == 0:
            return False

        text_blob = " ".join(
            [
                str(d.get("단지명", "")),
                str(d.get("타입/특징", "")),
                str(d.get("층/방향", "")),
            ]
        ).lower()
        include_keywords = [k.lower() for k in f.get("include_keywords", [])]
        exclude_keywords = [k.lower() for k in f.get("exclude_keywords", [])]
        if include_keywords and not any(k in text_blob for k in include_keywords):
            return False
        if exclude_keywords and any(k in text_blob for k in exclude_keywords):
            return False
        return True

    def _advanced_filtered_data_for_cards(self):
        if self._compact_duplicates:
            base = list(self._compact_rows_data)
        else:
            base = list(self.collected_data)
        if not self._advanced_filters:
            return base
        filtered = []
        for item in base:
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
            if self._check_advanced_filter(payload):
                filtered.append(item)
        return filtered

    def _apply_card_filters(self, text):
        if self._advanced_filters:
            self.card_view.set_data(self._advanced_filtered_data_for_cards())
        elif self._compact_duplicates:
            self.card_view.set_data(list(self._compact_rows_data))
        else:
            self.card_view.set_data(list(self.collected_data))
        self.card_view.filter_cards(text)

    def open_advanced_filter_dialog(self):
        dialog = AdvancedFilterDialog(self, current_filters=self._advanced_filters)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_advanced_filters(dialog.get_filters())

    def clear_advanced_filters(self):
        self.set_advanced_filters(None)

    def _filter_results(self, text):
        self._pending_search_text = text or ""
        rows = self.result_table.rowCount()
        for r in range(rows):
            if r >= len(self._row_search_cache):
                values = []
                for c in range(self.result_table.columnCount()):
                    item = self.result_table.item(r, c)
                    if item:
                        values.append(item.text())
                self._row_search_cache.append(" ".join(values).lower())
            if r >= len(self._row_payload_cache):
                self._row_payload_cache.append(self._build_row_payload_from_table(r))
            self._apply_current_filter_to_row(r)
            
        # Card filtering
        self._apply_card_filters(self._pending_search_text)

    def _sort_results(self, criterion):
        col_map = {
            "단지명": self.COL_COMPLEX,
            "가격": self.COL_PRICE_SORT,
            "면적": self.COL_AREA,
            "거래유형": self.COL_TRADE,
            "거래": self.COL_TRADE,
        }
        is_asc = "↑" in criterion
        key = criterion.split(" ")[0]
        if self._compact_duplicates:
            self._render_compact_rows()
            self._apply_card_filters(self._pending_search_text)
            return

        col = col_map.get(key, self.COL_COMPLEX)
        order = Qt.SortOrder.AscendingOrder if is_asc else Qt.SortOrder.DescendingOrder
        self.result_table.sortItems(col, order)
        self._rebuild_row_search_cache_from_table()
        self._filter_results(self._pending_search_text)

