from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleStatsHistoryMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
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
            ["날짜", "유형", "평형", f"최저 {metric_name}", f"최고 {metric_name}", f"평균 {metric_name}"]
        )

    def _on_stats_type_changed(self: Any, *_args):
        self._refresh_stats_metric_visibility()
        self._on_stats_complex_changed(self.stats_complex_combo.currentIndex())

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
                    name, key = row[0], row[1]
                    key_text = str(key or "")
                    if ":" in key_text:
                        head, tail = key_text.split(":", 1)
                        if head in {"APT", "VL"} and tail:
                            asset_type, cid = head, tail
                        else:
                            asset_type, cid = "APT", key_text
                    else:
                        asset_type, cid = "APT", key_text
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
                idx = self.stats_complex_combo.findData(current_key)
                if idx < 0:
                    for i in range(self.stats_complex_combo.count()):
                        data = self.stats_complex_combo.itemData(i)
                        if isinstance(data, tuple) and len(data) >= 2:
                            if isinstance(current_key, tuple) and len(current_key) >= 2:
                                if str(data[0]) == str(current_key[0]) and str(data[1]) == str(current_key[1]):
                                    idx = i
                                    break
                            elif str(data[1]) == str(current_key):
                                idx = i
                                break
                if idx >= 0:
                    self.stats_complex_combo.setCurrentIndex(idx)
            if self.stats_complex_combo.count() > 0 and self.stats_complex_combo.currentIndex() < 0:
                self.stats_complex_combo.setCurrentIndex(0)
        except Exception as e:
            ui_logger.warning(f"통계 단지 목록 로드 실패: {e}")
        finally:
            self.stats_complex_combo.blockSignals(False)

    def _load_stats(self: Any):
        selected = self.stats_complex_combo.currentData()
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
        if not cid:
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

        self.stats_table.blockSignals(True)
        self.stats_table.setUpdatesEnabled(False)
        prev_sorting = self.stats_table.isSortingEnabled()
        self.stats_table.setSortingEnabled(False)
        series_keys = set()
        chart_data = {"date": [], "avg": [], "min": [], "max": [], "type": None, "py": None}
        try:
            self.stats_table.setRowCount(0)
            self.stats_table.setRowCount(len(snapshots))
            for row, snapshot in enumerate(snapshots):
                date, typ, py, min_p, max_p, avg_p, cnt, row_metric, _legacy_monthly = snapshot
                parsed_py = self._parse_pyeong_value(py)
                py_text = (
                    f"{self._format_pyeong_value(parsed_py)}평"
                    if parsed_py is not None
                    else f"{py}평"
                )
                self.stats_table.setItem(row, 0, QTableWidgetItem(date))
                self.stats_table.setItem(row, 1, QTableWidgetItem(typ))
                self.stats_table.setItem(row, 2, QTableWidgetItem(py_text))
                self.stats_table.setItem(row, 3, SortableTableWidgetItem(str(min_p)))
                self.stats_table.setItem(row, 4, SortableTableWidgetItem(str(max_p)))
                self.stats_table.setItem(row, 5, SortableTableWidgetItem(str(avg_p)))
                series_keys.add((str(typ or ""), parsed_py))
                if parsed_py is not None:
                    chart_data["type"] = typ
                    chart_data["py"] = parsed_py
                chart_data["date"].append(date)
                chart_data["avg"].append(avg_p)
                chart_data["min"].append(min_p)
                chart_data["max"].append(max_p)
                chart_data["metric"] = row_metric
        finally:
            self.stats_table.blockSignals(False)
            self.stats_table.setUpdatesEnabled(True)
            self.stats_table.setSortingEnabled(prev_sorting)

        self._ensure_chart_widget()
        if not chart_data["date"]:
            self.chart_widget.clear("차트 데이터가 없습니다.")
            return

        if len(series_keys) != 1:
            self.chart_widget.clear("차트를 보려면 거래유형과 평형을 하나로 좁혀주세요.")
            return

        title = (
            f"{self.stats_complex_combo.currentText()} - "
            f"{chart_data.get('type', '')} "
            f"{self._format_pyeong_value(chart_data.get('py', 0))}평 "
            f"{self._stats_metric_display_name(chart_data.get('metric', price_metric))} 추이"
        )
        self.chart_widget.update_chart(
            chart_data["date"],
            chart_data["avg"],
            chart_data["min"],
            chart_data["max"],
            title,
        )

    def _on_stats_complex_changed(self: Any, index):
        """통계 탭 단지 변경 시 평형 콤보박스 업데이트"""
        self._refresh_stats_metric_visibility()
        selected = self.stats_complex_combo.currentData()
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
        if not cid:
            return

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
        self.stats_pyeong_combo.blockSignals(False)
