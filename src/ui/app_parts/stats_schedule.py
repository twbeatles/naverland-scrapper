from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _schedule_geo_defaults(self: Any):
        asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        normalized_assets = []
        for asset in asset_types:
            token = str(asset or "").strip().upper()
            if token in {"APT", "VL"} and token not in normalized_assets:
                normalized_assets.append(token)
        return {
            "lat": float(settings.get("schedule_geo_lat", 37.5608) or 37.5608),
            "lon": float(settings.get("schedule_geo_lon", 126.9888) or 126.9888),
            "zoom": int(settings.get("geo_default_zoom", 15) or 15),
            "rings": int(settings.get("geo_grid_rings", 1) or 1),
            "step_px": int(settings.get("geo_grid_step_px", 480) or 480),
            "dwell_ms": int(settings.get("geo_sweep_dwell_ms", 600) or 600),
            "asset_types": normalized_assets or ["APT", "VL"],
        }

    def _collect_schedule_config(self: Any):
        geo_defaults = self._schedule_geo_defaults()
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        return {
            "enabled": bool(self.check_schedule.isChecked()),
            "mode": mode,
            "time": self.time_edit.time().toString("HH:mm"),
            "group_id": self.schedule_group_combo.currentData(),
            "geo": {
                "lat": float(self.schedule_geo_lat.value()),
                "lon": float(self.schedule_geo_lon.value()),
                "zoom": int(geo_defaults["zoom"]),
                "rings": int(geo_defaults["rings"]),
                "step_px": int(geo_defaults["step_px"]),
                "dwell_ms": int(geo_defaults["dwell_ms"]),
                "asset_types": list(geo_defaults["asset_types"]),
            },
        }

    def _save_schedule_config(self: Any, *_args):
        config = self._collect_schedule_config()
        settings.update(
            {
                "schedule_config": config,
                "schedule_geo_lat": config["geo"]["lat"],
                "schedule_geo_lon": config["geo"]["lon"],
            }
        )
        return config

    def _load_schedule_config(self: Any):
        config = settings.get("schedule_config", {}) or {}
        mode = str(config.get("mode", "complex") or "complex")
        time_text = str(config.get("time", "09:00") or "09:00")
        geo_config = config.get("geo", {}) if isinstance(config.get("geo"), dict) else {}

        self.check_schedule.blockSignals(True)
        self.time_edit.blockSignals(True)
        self.schedule_mode_combo.blockSignals(True)
        self.schedule_group_combo.blockSignals(True)
        self.schedule_geo_lat.blockSignals(True)
        self.schedule_geo_lon.blockSignals(True)
        try:
            self.check_schedule.setChecked(bool(config.get("enabled", False)))
            parsed_time = QTime.fromString(time_text, "HH:mm")
            self.time_edit.setTime(parsed_time if parsed_time.isValid() else QTime(9, 0))

            mode_index = self.schedule_mode_combo.findData(mode)
            self.schedule_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)

            gid = config.get("group_id")
            if gid is not None:
                group_index = self.schedule_group_combo.findData(gid)
                if group_index >= 0:
                    self.schedule_group_combo.setCurrentIndex(group_index)

            lat = geo_config.get("lat", settings.get("schedule_geo_lat", 37.5608))
            lon = geo_config.get("lon", settings.get("schedule_geo_lon", 126.9888))
            try:
                self.schedule_geo_lat.setValue(float(lat))
            except (TypeError, ValueError):
                self.schedule_geo_lat.setValue(37.5608)
            try:
                self.schedule_geo_lon.setValue(float(lon))
            except (TypeError, ValueError):
                self.schedule_geo_lon.setValue(126.9888)
        finally:
            self.check_schedule.blockSignals(False)
            self.time_edit.blockSignals(False)
            self.schedule_mode_combo.blockSignals(False)
            self.schedule_group_combo.blockSignals(False)
            self.schedule_geo_lat.blockSignals(False)
            self.schedule_geo_lon.blockSignals(False)

        self._on_schedule_mode_changed()
        self._save_schedule_config()

    def _load_schedule_groups(self: Any):
        current_gid = self.schedule_group_combo.currentData()
        selected = False
        self.schedule_group_combo.blockSignals(True)
        try:
            self.schedule_group_combo.clear()
            for gid, name, _ in self.db.get_all_groups():
                self.schedule_group_combo.addItem(name, gid)
            if current_gid is not None:
                idx = self.schedule_group_combo.findData(current_gid)
                if idx >= 0:
                    self.schedule_group_combo.setCurrentIndex(idx)
                    selected = True
            if not selected:
                saved_gid = (settings.get("schedule_config", {}) or {}).get("group_id")
                if saved_gid is not None:
                    idx = self.schedule_group_combo.findData(saved_gid)
                    if idx >= 0:
                        self.schedule_group_combo.setCurrentIndex(idx)
        finally:
            self.schedule_group_combo.blockSignals(False)
        self._update_schedule_state()
        self._save_schedule_config()

    def _on_schedule_mode_changed(self: Any, *_args):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        self.schedule_group_widget.setVisible(mode == "complex")
        self.schedule_geo_widget.setVisible(mode == "geo_sweep")
        self._update_schedule_state()
        self._save_schedule_config()

    def _check_schedule(self: Any):
        if not self.check_schedule.isChecked():
            return
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        if mode == "complex" and self.schedule_group_combo.count() == 0:
            return
        now = QTime.currentTime()
        target = self.time_edit.time()
        if now.hour() == target.hour() and now.minute() == target.minute():
            if not self.is_scheduled_run:
                self.is_scheduled_run = True
                self._run_scheduled()
        else:
            self.is_scheduled_run = False

    def _run_scheduled(self: Any):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        crawler_running = bool(
            hasattr(self, "crawler_tab")
            and getattr(self.crawler_tab, "crawler_thread", None)
            and self.crawler_tab.crawler_thread.isRunning()
        )
        geo_running = bool(
            hasattr(self, "geo_tab")
            and getattr(self.geo_tab, "crawler_thread", None)
            and self.geo_tab.crawler_thread.isRunning()
        )
        if crawler_running or geo_running:
            self.status_bar.showMessage("⏸ 예약 작업 건너뜀: 다른 크롤링이 이미 실행 중입니다.")
            ui_logger.info(
                f"예약 작업 스킵: crawler_running={crawler_running}, geo_running={geo_running}"
            )
            return

        config = self._save_schedule_config()
        if mode == "geo_sweep":
            geo = config.get("geo", {}) if isinstance(config.get("geo"), dict) else {}
            self.tabs.setCurrentWidget(self.geo_tab)
            self.geo_tab.spin_lat.setValue(float(geo.get("lat", self.schedule_geo_lat.value())))
            self.geo_tab.spin_lon.setValue(float(geo.get("lon", self.schedule_geo_lon.value())))
            self.geo_tab.spin_zoom.setValue(int(geo.get("zoom", settings.get("geo_default_zoom", 15) or 15)))
            self.geo_tab.spin_rings.setValue(int(geo.get("rings", settings.get("geo_grid_rings", 1) or 1)))
            self.geo_tab.spin_step.setValue(int(geo.get("step_px", settings.get("geo_grid_step_px", 480) or 480)))
            self.geo_tab.spin_dwell.setValue(
                int(geo.get("dwell_ms", settings.get("geo_sweep_dwell_ms", 600) or 600))
            )
            asset_types = geo.get("asset_types", settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"])
            asset_tokens = {str(asset or "").strip().upper() for asset in asset_types}
            self.geo_tab.check_asset_apt.setChecked("APT" in asset_tokens or not asset_tokens)
            self.geo_tab.check_asset_vl.setChecked("VL" in asset_tokens or not asset_tokens)
            self.geo_tab.start_crawling()
            self.status_bar.showMessage(
                f"⏰ 예약 Geo 작업 시작: {self.geo_tab.spin_lat.value():.6f}, {self.geo_tab.spin_lon.value():.6f}"
            )
            return

        gid = self.schedule_group_combo.currentData()
        if gid is None:
            self.status_bar.showMessage("⏸ 예약 작업 중단: 선택된 그룹이 없습니다.")
            return

        self.tabs.setCurrentWidget(self.crawler_tab)
        self.crawler_tab.clear_tasks()
        excluded_vl = 0
        loaded_count = 0
        for _, name, asset_type, cid, _ in self.db.get_complexes_in_group(gid):
            asset_token = str(asset_type or "APT").strip().upper() or "APT"
            if asset_token != "APT":
                excluded_vl += 1
                continue
            if self.crawler_tab.add_task(name, cid):
                loaded_count += 1
        if excluded_vl > 0:
            msg = f"complex 모드는 APT만 지원하여 VL {excluded_vl}개를 제외했습니다."
            self.crawler_tab.append_log(f"ℹ️ {msg}", 20)
            self.status_bar.showMessage(msg)
            ui_logger.info(f"예약 작업 필터링: group={gid}, excluded_vl={excluded_vl}")
        if loaded_count <= 0:
            self.status_bar.showMessage("⏸ 예약 작업 중단: 실행 가능한 APT 대상이 없습니다.")
            return
        self.crawler_tab.start_crawling()
        self.status_bar.showMessage(f"⏰ 예약 작업 시작: 그룹 {gid}")


    def _update_group_empty_state(self: Any):
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_empty_label"):
            self.group_empty_label.setVisible(not has_groups)
        self.group_list.setEnabled(has_groups)
        if not has_groups:
            self.group_complex_table.setRowCount(0)
            self._update_group_complex_empty_state(0)

    def _update_group_action_state(self: Any):
        has_selection = self.group_list.currentRow() >= 0
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_btn_delete"):
            self.group_btn_delete.setEnabled(has_selection)
        if hasattr(self, "group_btn_add"):
            self.group_btn_add.setEnabled(has_groups)
        if hasattr(self, "group_btn_add_multi"):
            self.group_btn_add_multi.setEnabled(has_groups)
        if not has_groups:
            if hasattr(self, "group_btn_remove"):
                self.group_btn_remove.setEnabled(False)

    def _update_group_complex_empty_state(self: Any, count):
        is_empty = count == 0
        if hasattr(self, "group_complex_empty_label"):
            self.group_complex_empty_label.setVisible(is_empty)
        self.group_complex_table.setEnabled(not is_empty)

    def _update_group_complex_action_state(self: Any):
        has_selection = self.group_complex_table.currentRow() >= 0
        if hasattr(self, "group_btn_remove"):
            self.group_btn_remove.setEnabled(has_selection)

    def _update_schedule_state(self: Any):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        has_groups = self.schedule_group_combo.count() > 0
        can_run = mode == "geo_sweep" or has_groups
        self.check_schedule.setEnabled(can_run)
        self.time_edit.setEnabled(can_run)
        self.schedule_mode_combo.setEnabled(True)
        self.schedule_group_combo.setEnabled(mode == "complex" and has_groups)
        self.schedule_geo_lat.setEnabled(mode == "geo_sweep")
        self.schedule_geo_lon.setEnabled(mode == "geo_sweep")
        if hasattr(self, "schedule_empty_label"):
            self.schedule_empty_label.setVisible(mode == "complex" and not has_groups)
    
    # History Tab handlers
    def _load_history(self: Any):
        self.history_table.setUpdatesEnabled(False)
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
            self.history_table.setUpdatesEnabled(True)

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

    # Stats Tab handlers
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

        pyeong = self.stats_pyeong_combo.currentData()
        if pyeong is None:
            pyeong_text = self.stats_pyeong_combo.currentText()
            if pyeong_text != "전체":
                pyeong = self._parse_pyeong_value(pyeong_text)
                if pyeong is None:
                    ui_logger.warning(f"평형 파싱 실패: {pyeong_text}")

        snapshots = self.db.get_price_snapshots(cid, ttype, asset_type=asset_type)
        if pyeong is not None:
            filtered = []
            for s in snapshots:
                py = self._parse_pyeong_value(s[2] if len(s) > 2 else None)
                if py is not None and abs(py - float(pyeong)) <= 1e-6:
                    filtered.append(s)
            snapshots = filtered

        self.stats_table.setUpdatesEnabled(False)
        series_keys = set()
        chart_data = {"date": [], "avg": [], "min": [], "max": [], "type": None, "py": None}
        try:
            self.stats_table.setRowCount(0)
            self.stats_table.setRowCount(len(snapshots))
            for row, (date, typ, py, min_p, max_p, avg_p, cnt) in enumerate(snapshots):
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
        finally:
            self.stats_table.setUpdatesEnabled(True)

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
            f"{self._format_pyeong_value(chart_data.get('py', 0))}평 가격 추이"
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
            snapshots = self.db.get_price_snapshots(cid, asset_type=asset_type)
        except Exception as e:
            ui_logger.warning(f"평형 목록 로드 실패: {e}")
            snapshots = []
        # 평형 목록 추출
        pyeong_values = []
        for row in snapshots:
            value = self._parse_pyeong_value(row[2] if len(row) > 2 else None)
            if value is not None:
                pyeong_values.append(value)
        pyeongs = sorted(set(pyeong_values))

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

