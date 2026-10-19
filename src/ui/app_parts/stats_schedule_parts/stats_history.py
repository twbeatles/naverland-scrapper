from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleStatsHistoryMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    STATS_COMPARE_LIMIT = 5

    def _refresh_stats_metric_visibility(self: Any) -> None:
        visible = str(self.stats_type_combo.currentText() or "") == "월세"
        self.stats_metric_label.setVisible(visible)
        self.stats_metric_combo.setVisible(visible)

    def _current_stats_price_metric(self: Any):
        trade_type = str(self.stats_type_combo.currentText() or "")
        if trade_type == "월세":
            return str(self.stats_metric_combo.currentData() or "rent")
        if trade_type in {"매매", "전세"}:
            return "price"
        return None

    def _stats_metric_display_name(self: Any, price_metric: str | None) -> str:
        metric_token = str(price_metric or "").strip().lower()
        if metric_token == "rent":
            return "월세"
        if metric_token == "deposit":
            return "보증금"
        return "가격"

    def _update_stats_table_headers(self: Any, price_metric: str | None) -> None:
        metric_name = self._stats_metric_display_name(price_metric)
        self.stats_table.setHorizontalHeaderLabels(
            [
                "날짜",
                "유형",
                "평형",
                f"최저 {metric_name}",
                f"최고 {metric_name}",
                f"평균 {metric_name}",
                "매물 수",
                "직전 대비",
            ]
        )

    def _on_stats_type_changed(self: Any, *_args):
        # 사용자가 직접 고른 거래 종류는 자동으로 바꾸지 않는다.
        self._refresh_stats_metric_visibility()
        self._on_stats_complex_changed(self.stats_complex_combo.currentIndex(), auto_trade=False)

    def _load_history(self: Any):
        self.history_table.blockSignals(True)
        self.history_table.setUpdatesEnabled(False)
        prev_sorting = self.history_table.isSortingEnabled()
        self.history_table.setSortingEnabled(False)
        try:
            self.history_table.setRowCount(0)
            history = self.db.get_crawl_history()
            self.history_table.setRowCount(len(history))
            for row_idx, history_row in enumerate(history):
                if isinstance(history_row, dict):
                    name = str(history_row.get("complex_name", "") or "")
                    cid = str(history_row.get("complex_id", "") or "")
                    asset_type = str(history_row.get("asset_type", "APT") or "APT").strip().upper() or "APT"
                    engine = str(history_row.get("engine", "") or "")
                    mode = str(history_row.get("mode", "complex") or "complex")
                    run_status = str(history_row.get("run_status", "success") or "success")
                    trade_types = str(history_row.get("trade_types", "") or "")
                    item_count = int(history_row.get("item_count", 0) or 0)
                    crawled_at = str(history_row.get("crawled_at", "") or "")
                else:
                    name = str(history_row[0] if len(history_row) > 0 else "")
                    cid = str(history_row[1] if len(history_row) > 1 else "")
                    asset_type = str(history_row[2] if len(history_row) > 2 else "APT").strip().upper() or "APT"
                    engine = str(history_row[3] if len(history_row) > 3 else "")
                    mode = str(history_row[4] if len(history_row) > 4 else "complex")
                    run_status = str(history_row[5] if len(history_row) > 5 else "success")
                    trade_types = str(history_row[6] if len(history_row) > 6 else "")
                    item_count = int(history_row[7] if len(history_row) > 7 else 0)
                    crawled_at = str(history_row[8] if len(history_row) > 8 else "")

                self.history_table.setItem(row_idx, 0, QTableWidgetItem(name))
                self.history_table.setItem(row_idx, 1, QTableWidgetItem(cid))
                self.history_table.setItem(row_idx, 2, QTableWidgetItem(asset_type))
                self.history_table.setItem(row_idx, 3, QTableWidgetItem(engine))
                self.history_table.setItem(row_idx, 4, QTableWidgetItem(mode))
                self.history_table.setItem(row_idx, 5, QTableWidgetItem(run_status))
                self.history_table.setItem(row_idx, 6, QTableWidgetItem(trade_types))
                self.history_table.setItem(row_idx, 7, QTableWidgetItem(str(item_count)))
                self.history_table.setItem(row_idx, 8, QTableWidgetItem(crawled_at))
        finally:
            self.history_table.blockSignals(False)
            self.history_table.setUpdatesEnabled(True)
            self.history_table.setSortingEnabled(prev_sorting)

    @staticmethod
    def _parse_pyeong_value(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        text = text.replace("평", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_pyeong_value(value):
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _split_stats_key(selected) -> tuple[str | None, str]:
        """콤보 데이터(``(asset, cid)`` / ``"APT:cid"`` / ``"cid"``)를 (asset, cid)로 나눈다."""
        asset_type = None
        cid = ""
        if isinstance(selected, (tuple, list)) and len(selected) >= 2:
            asset_type = str(selected[0] or "APT").strip().upper() or "APT"
            cid = str(selected[1] or "")
        else:
            cid = str(selected or "")
            asset_type = "APT" if cid else None
        if isinstance(cid, str) and ":" in cid:
            head, tail = cid.split(":", 1)
            if head in {"APT", "VL"} and tail:
                asset_type = head
                cid = tail
        return asset_type, cid

    def _current_stats_complex_name(self: Any) -> str:
        text = str(self.stats_complex_combo.currentText() or "")
        return re.sub(r"\s*\([A-Z]+:[^)]*\)\s*$", "", text).strip() or text

    def _load_stats_complexes(self: Any):
        current_key = self.stats_complex_combo.currentData()
        self.stats_complex_combo.blockSignals(True)
        try:
            self.stats_complex_combo.clear()
            complexes = self.db.get_complexes_for_stats()
            for row in complexes:
                if isinstance(row, (tuple, list)) and len(row) >= 3:
                    name, asset_type, cid = row[0], row[1], row[2]
                elif isinstance(row, (tuple, list)) and len(row) >= 2:
                    name = row[0]
                    asset_type, cid = self._split_stats_key(str(row[1] or ""))
                else:
                    continue
                cid_text = str(cid or "")
                if not cid_text:
                    continue
                asset_token = str(asset_type or "APT").strip().upper() or "APT"
                display_name = str(name or f"단지_{cid_text}")
                combo_data = (asset_token, cid_text)
                self.stats_complex_combo.addItem(f"{display_name} ({asset_token}:{cid_text})", combo_data)
            if current_key:
                idx = self._find_stats_complex_index(current_key)
                if idx >= 0:
                    self.stats_complex_combo.setCurrentIndex(idx)
            if self.stats_complex_combo.count() > 0 and self.stats_complex_combo.currentIndex() < 0:
                self.stats_complex_combo.setCurrentIndex(0)
        except Exception as e:
            ui_logger.warning(f"통계 단지 목록 로드 실패: {e}")
        finally:
            self.stats_complex_combo.blockSignals(False)
        self._update_stats_empty_state()

    def _find_stats_complex_index(self: Any, key) -> int:
        idx = self.stats_complex_combo.findData(key)
        if idx >= 0:
            return idx
        want_asset, want_cid = self._split_stats_key(key)
        strict_asset = isinstance(key, (tuple, list)) or (isinstance(key, str) and ":" in key)
        for i in range(self.stats_complex_combo.count()):
            data = self.stats_complex_combo.itemData(i)
            if not (isinstance(data, tuple) and len(data) >= 2):
                continue
            if str(data[1]) != str(want_cid):
                continue
            if strict_asset and want_asset and str(data[0]) != str(want_asset):
                continue
            return i
        return -1

    def _update_stats_empty_state(self: Any) -> None:
        empty = getattr(self, "stats_empty_state", None)
        if empty is None:
            return
        has_complexes = self.stats_complex_combo.count() > 0
        empty.setVisible(not has_complexes)
        for name in ("stats_filter_bar", "stats_compare_bar", "stats_summary", "stats_splitter"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(has_complexes)

    def _reload_stats_page(self: Any) -> None:
        """단지 목록을 새로 읽고, 현재 단지의 면적 목록과 기록을 다시 그린다."""
        self._load_stats_complexes()
        self._on_stats_complex_changed(self.stats_complex_combo.currentIndex())

    def _open_stats_for_complex(self: Any, asset_type: str, complex_id: str) -> None:
        """다른 화면(내 단지·수집 기록)에서 고른 단지의 「시세 흐름」으로 바로 이동한다."""
        cid = str(complex_id or "").strip()
        if not cid:
            return
        asset = str(asset_type or "APT").strip().upper() or "APT"
        self._load_stats_complexes()
        idx = self._find_stats_complex_index((asset, cid))
        if idx < 0:
            idx = self._find_stats_complex_index(cid)
        if idx < 0:
            self.show_toast("이 단지는 아직 가격 기록이 없습니다. 먼저 수집해 주세요.", toast_type="warning")
            return
        self.stats_complex_combo.blockSignals(True)
        self.stats_complex_combo.setCurrentIndex(idx)
        self.stats_complex_combo.blockSignals(False)
        self._on_stats_complex_changed(idx)
        self._mark_noncritical_loaded("stats")
        self.tabs.setCurrentWidget(self.stats_tab)

    def _open_stats_from_history_row(self: Any, row: int, _column: int = 0) -> None:
        cid_item = self.history_table.item(row, 1)
        if cid_item is None:
            return
        asset_item = self.history_table.item(row, 2)
        asset = asset_item.text() if asset_item is not None else "APT"
        if asset not in {"APT", "VL"}:
            asset = "APT"
        self._open_stats_for_complex(asset, cid_item.text())

    def _stats_trade_types_with_data(self: Any, cid: str, asset_type) -> list[str]:
        available = []
        for trade in ("매매", "전세", "월세"):
            metric = "rent" if trade == "월세" else "price"
            try:
                if self.db.get_price_snapshot_pyeongs(cid, asset_type=asset_type, trade_type=trade, price_metric=metric):
                    available.append(trade)
            except Exception as e:
                ui_logger.debug(f"거래 종류 확인 실패({trade}): {e}")
        return available

    def _load_stats(self: Any):
        from src.core.services.price_trend import (
            MSG_PICK_TRADE_TYPE,
            build_series,
            filter_period,
            format_pct,
            pick_chart_series,
            previous_avg_map,
            summarize,
        )
        from src.ui.widgets.chart import ChartSeries, format_price_axis
        from src.ui.widgets.components import NumericSortTableWidgetItem
        from src.utils.helpers import PriceConverter

        asset_type, cid = self._split_stats_key(self.stats_complex_combo.currentData())
        if not cid:
            # 단지가 모두 지워졌으면 이전 단지의 표·요약이 남지 않게 비운다.
            self.stats_table.setRowCount(0)
            summary_widget = getattr(self, "stats_summary", None)
            if summary_widget is not None:
                summary_widget.clear("단지를 고르면 최근 평균과 변화가 여기에 나타납니다.")
            return
        ttype = self.stats_type_combo.currentText()
        if ttype == "전체": ttype = None
        price_metric = self._current_stats_price_metric()
        self._refresh_stats_metric_visibility()
        self._update_stats_table_headers(price_metric)

        pyeong = self.stats_pyeong_combo.currentData()
        if pyeong is None:
            pyeong_text = self.stats_pyeong_combo.currentText()
            if pyeong_text != "전체":
                pyeong = self._parse_pyeong_value(pyeong_text)
                if pyeong is None:
                    ui_logger.warning(f"평형 파싱 실패: {pyeong_text}")

        snapshots = self.db.get_price_snapshots(
            cid,
            ttype,
            asset_type=asset_type,
            pyeong=pyeong,
            price_metric=price_metric,
        )
        period_combo = getattr(self, "stats_period_combo", None)
        period_days = period_combo.currentData() if period_combo is not None else None
        snapshots = filter_period(snapshots, period_days)
        series_list = build_series(snapshots)
        prev_map = previous_avg_map(series_list)

        def _numeric_item(text: str, sort_value) -> QTableWidgetItem:
            item = NumericSortTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, sort_value)
            return item

        def _price_item(value) -> QTableWidgetItem:
            try:
                amount = int(round(float(value or 0)))
            except (TypeError, ValueError):
                amount = 0
            return _numeric_item(PriceConverter.to_string(amount) if amount > 0 else "-", amount)

        self.stats_table.blockSignals(True)
        self.stats_table.setUpdatesEnabled(False)
        prev_sorting = self.stats_table.isSortingEnabled()
        self.stats_table.setSortingEnabled(False)
        try:
            self.stats_table.setRowCount(0)
            self.stats_table.setRowCount(len(snapshots))
            for row, snapshot in enumerate(snapshots):
                date, typ, py, min_p, max_p, avg_p, cnt, _row_metric, _legacy_monthly = snapshot
                parsed_py = self._parse_pyeong_value(py)
                py_text = (
                    f"{self._format_pyeong_value(parsed_py)}평"
                    if parsed_py is not None
                    else f"{py}평"
                )
                self.stats_table.setItem(row, 0, QTableWidgetItem(str(date)))
                self.stats_table.setItem(row, 1, QTableWidgetItem(str(typ)))
                self.stats_table.setItem(row, 2, _numeric_item(py_text, float(parsed_py or 0)))
                self.stats_table.setItem(row, 3, _price_item(min_p))
                self.stats_table.setItem(row, 4, _price_item(max_p))
                self.stats_table.setItem(row, 5, _price_item(avg_p))
                self.stats_table.setItem(row, 6, _numeric_item(f"{int(cnt or 0)}건", int(cnt or 0)))

                prev_avg = prev_map.get((str(typ or ""), float(parsed_py or 0), str(date)[:10]))
                try:
                    delta = int(round(float(avg_p or 0))) - prev_avg if prev_avg else 0
                except (TypeError, ValueError):
                    delta = 0
                if prev_avg:
                    pct = format_pct(delta / prev_avg * 100.0)
                    delta_text = "변동 없음" if delta == 0 else f"{PriceConverter.to_signed_string(delta)} ({pct})"
                else:
                    delta_text = "-"
                delta_item = _numeric_item(delta_text, delta)
                if delta:
                    # 국내 시세 표기 관례: 상승 빨강, 하락 파랑.
                    delta_item.setForeground(QColor("#ef4444" if delta > 0 else "#3b82f6"))
                self.stats_table.setItem(row, 7, delta_item)
        finally:
            self.stats_table.blockSignals(False)
            self.stats_table.setUpdatesEnabled(True)
            self.stats_table.setSortingEnabled(prev_sorting)

        self._ensure_chart_widget()
        summary_widget = getattr(self, "stats_summary", None)
        complex_name = self._current_stats_complex_name()
        metric_name = self._stats_metric_display_name(price_metric)

        if not series_list:
            message = (
                f"이 단지에는 고른 조건의 {ttype} 가격 기록이 없습니다."
                if ttype
                else "고른 조건의 가격 기록이 없습니다."
            )
            if period_days:
                message += " 기간을 넓혀 보세요."
            if summary_widget is not None:
                summary_widget.clear(message)
            if not self._render_stats_compare(ttype, price_metric, period_days):
                self.chart_widget.clear(message)
            return

        trade_types = {s.trade_type for s in series_list}
        if len(trade_types) > 1:
            self.chart_widget.clear(MSG_PICK_TRADE_TYPE)
            if summary_widget is not None:
                summary_widget.clear("거래 종류를 하나 고르면 변화 요약이 나타납니다.")
            return

        if len(series_list) == 1:
            series = series_list[0]
            title = (
                f"{complex_name} · {series.trade_type} "
                f"{self._format_pyeong_value(series.pyeong)}평 "
                f"{self._stats_metric_display_name(series.metric or price_metric)} 흐름"
            )
            hint = "" if len(series.points) >= 2 else "기록이 하루치뿐입니다. 며칠 더 수집하면 흐름이 보입니다."
            if summary_widget is not None:
                summary_widget.set_summary(summarize(series), hint=hint)
            if self._render_stats_compare(ttype, price_metric, period_days):
                return
            self.chart_widget.update_series(
                [
                    ChartSeries(
                        label="평균",
                        dates=[p.date_text for p in series.points],
                        avg=[p.avg_price for p in series.points],
                        min_vals=[p.min_price for p in series.points],
                        max_vals=[p.max_price for p in series.points],
                    )
                ],
                title,
                value_formatter=format_price_axis,
            )
            return

        # 같은 거래 종류의 여러 면적 → 평균선만 겹쳐 그리고 범례에 기간 변화율을 붙인다.
        chart_series = []
        for series in pick_chart_series(series_list):
            summary = summarize(series)
            label = f"{self._format_pyeong_value(series.pyeong)}평"
            if summary is not None and summary.record_days >= 2:
                label += f" ({format_pct(summary.period_change_pct)})"
            chart_series.append(
                ChartSeries(
                    label=label,
                    dates=[p.date_text for p in series.points],
                    avg=[p.avg_price for p in series.points],
                )
            )
        hidden = len(series_list) - len(chart_series)
        hint = "면적을 하나 고르면 변화 요약과 최저~최고 범위가 나타납니다."
        if hidden > 0:
            hint += f" (기록이 적은 면적 {hidden}개는 그래프에서 뺐습니다)"
        if summary_widget is not None:
            summary_widget.clear(hint)
        if self._render_stats_compare(ttype, price_metric, period_days):
            return
        self.chart_widget.update_series(
            chart_series,
            f"{complex_name} · {next(iter(trade_types))} 면적별 평균 {metric_name} 흐름",
            value_formatter=format_price_axis,
        )

    # --- 단지 비교 ---------------------------------------------------------
    def _stats_complex_name_for_key(self: Any, key: str) -> str:
        idx = self._find_stats_complex_index(key)
        if idx < 0:
            return str(key)
        text = str(self.stats_complex_combo.itemText(idx) or "")
        return re.sub(r"\s*\([A-Z]+:[^)]*\)\s*$", "", text).strip() or text

    def _current_stats_key_text(self: Any) -> str:
        asset_type, cid = self._split_stats_key(self.stats_complex_combo.currentData())
        return f"{asset_type or 'APT'}:{cid}" if cid else ""

    def _active_stats_compare_keys(self: Any) -> list[str]:
        """현재 단지를 뺀, 목록에 아직 남아 있는 비교 단지 키."""
        current = self._current_stats_key_text()
        keys = []
        for key in list(getattr(self, "_stats_compare_keys", []) or []):
            if key and key != current and key not in keys and self._find_stats_complex_index(key) >= 0:
                keys.append(key)
        return keys

    def _update_stats_compare_label(self: Any) -> None:
        label = getattr(self, "stats_compare_label", None)
        clear_btn = getattr(self, "btn_stats_compare_clear", None)
        if label is None:
            return
        keys = self._active_stats_compare_keys()
        if keys:
            names = ", ".join(self._stats_complex_name_for_key(k) for k in keys)
            label.setText(f"비교 중 {len(keys)}곳: {names} · 평당 평균가로 비교")
        else:
            label.setText("")
        label.setVisible(bool(keys))
        if clear_btn is not None:
            clear_btn.setVisible(bool(keys))

    def _choose_stats_compare(self: Any) -> None:
        from src.ui.dialogs import MultiSelectDialog

        current = self._current_stats_key_text()
        items = []
        for i in range(self.stats_complex_combo.count()):
            asset_type, cid = self._split_stats_key(self.stats_complex_combo.itemData(i))
            key = f"{asset_type or 'APT'}:{cid}"
            if not cid or key == current:
                continue
            items.append((str(self.stats_complex_combo.itemText(i)), key))
        if not items:
            self.show_toast("비교할 다른 단지가 없습니다. 다른 단지도 수집해 주세요.", toast_type="warning")
            return
        dlg = MultiSelectDialog(
            "함께 비교할 단지 고르기",
            items,
            self,
            preselected=self._active_stats_compare_keys(),
            hint=f"최대 {self.STATS_COMPARE_LIMIT}곳까지 고른 단지와 같은 거래 종류의 평당 평균가 흐름을 겹쳐 봅니다.",
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = [str(k) for k in dlg.selected_items() if k]
        if len(chosen) > self.STATS_COMPARE_LIMIT:
            self.show_toast(
                f"비교는 {self.STATS_COMPARE_LIMIT}곳까지만 됩니다. 앞의 {self.STATS_COMPARE_LIMIT}곳만 봅니다.",
                toast_type="warning",
            )
            chosen = chosen[: self.STATS_COMPARE_LIMIT]
        self._set_stats_compare(chosen)

    def _set_stats_compare(self: Any, keys) -> None:
        self._stats_compare_keys = [str(k) for k in (keys or []) if k]
        self._update_stats_compare_label()
        self._load_stats()

    def _clear_stats_compare(self: Any) -> None:
        self._set_stats_compare([])

    def _render_stats_compare(self: Any, ttype, price_metric, period_days) -> bool:
        """비교 단지가 있으면 평당 평균가 비교 그래프를 그리고 True를 돌려준다."""
        self._update_stats_compare_label()
        keys = self._active_stats_compare_keys()
        if not keys:
            return False
        if not ttype:
            from src.core.services.price_trend import MSG_PICK_TRADE_TYPE

            self.chart_widget.clear(MSG_PICK_TRADE_TYPE)
            return True
        from src.core.services.price_trend import filter_period, format_pct, per_pyeong_series, summarize
        from src.ui.widgets.chart import ChartSeries, format_price_axis
        from src.utils.helpers import PriceConverter

        entries = [(self._current_stats_key_text(), self._current_stats_complex_name())]
        entries += [(k, self._stats_complex_name_for_key(k)) for k in keys]
        chart_series = []
        missing = []
        for key, name in entries:
            asset_type, cid = self._split_stats_key(key)
            try:
                rows = self.db.get_price_snapshots(cid, ttype, asset_type=asset_type, price_metric=price_metric)
            except Exception as e:
                ui_logger.warning(f"비교 단지 가격 조회 실패({key}): {e}")
                rows = []
            series = per_pyeong_series(filter_period(rows, period_days), ttype)
            if series is None:
                missing.append(name)
                continue
            summary = summarize(series)
            label = name
            if summary is not None and summary.record_days >= 2:
                label += f" ({format_pct(summary.period_change_pct)})"
            chart_series.append(
                ChartSeries(
                    label=label,
                    dates=[p.date_text for p in series.points],
                    avg=[p.avg_price for p in series.points],
                )
            )
        if missing:
            self.status_bar.showMessage(
                f"{ttype} 기록이 없어 비교에서 빠진 단지: {', '.join(missing)}", 6000
            )
        if not chart_series:
            self.chart_widget.clear(f"비교할 단지들에 고른 조건의 {ttype} 가격 기록이 없습니다.")
            return True
        metric_name = self._stats_metric_display_name(price_metric)
        self.chart_widget.update_series(
            chart_series,
            f"{ttype} 평당 평균 {metric_name} 비교 (만원/평)",
            value_formatter=format_price_axis,
            point_formatter=lambda v: f"{PriceConverter.to_string(int(round(v)))}/평",
            show_band=False,
        )
        return True

    def _on_stats_complex_changed(self: Any, index=None, *, auto_trade: bool = True):
        """단지(또는 거래 종류) 변경 시 면적 목록을 갱신하고 바로 다시 그린다."""
        self._refresh_stats_metric_visibility()
        asset_type, cid = self._split_stats_key(self.stats_complex_combo.currentData())
        if not cid:
            self._load_stats()
            return

        if auto_trade:
            current_trade = str(self.stats_type_combo.currentText() or "")
            if current_trade != "전체":
                available = self._stats_trade_types_with_data(cid, asset_type)
                if available and current_trade not in available:
                    self.stats_type_combo.blockSignals(True)
                    self.stats_type_combo.setCurrentText(available[0])
                    self.stats_type_combo.blockSignals(False)
                    self._refresh_stats_metric_visibility()
                    self.status_bar.showMessage(
                        f"이 단지에는 {current_trade} 기록이 없어 {available[0]} 흐름을 보여 줍니다.", 5000
                    )

        try:
            selected_trade_type = self.stats_type_combo.currentText()
            if selected_trade_type == "전체":
                selected_trade_type = None
            pyeongs = sorted(
                set(
                    self.db.get_price_snapshot_pyeongs(
                        cid,
                        asset_type=asset_type,
                        trade_type=selected_trade_type,
                        price_metric=self._current_stats_price_metric(),
                    )
                )
            )
        except Exception as e:
            ui_logger.warning(f"평형 목록 로드 실패: {e}")
            pyeongs = []

        prev_text = self.stats_pyeong_combo.currentText()
        prev_value = self._parse_pyeong_value(prev_text) if prev_text and prev_text != "전체" else None

        self.stats_pyeong_combo.blockSignals(True)
        self.stats_pyeong_combo.clear()
        self.stats_pyeong_combo.addItem("전체", None)
        for p in pyeongs:
            self.stats_pyeong_combo.addItem(f"{self._format_pyeong_value(p)}평", p)
        if prev_value is not None:
            for i in range(1, self.stats_pyeong_combo.count()):
                row_value = self.stats_pyeong_combo.itemData(i)
                if row_value is None:
                    continue
                if abs(float(row_value) - float(prev_value)) <= 1e-6:
                    self.stats_pyeong_combo.setCurrentIndex(i)
                    break
        elif len(pyeongs) == 1:
            # 면적이 하나뿐이면 바로 골라 두어 변화 요약이 곧장 보이게 한다.
            self.stats_pyeong_combo.setCurrentIndex(1)
        self.stats_pyeong_combo.blockSignals(False)
        self._load_stats()
