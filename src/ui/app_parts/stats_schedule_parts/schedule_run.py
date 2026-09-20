from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleRunMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _snapshot_crawler_tasks(self: Any) -> tuple[list[tuple[str, str, str]], int]:
        rows: list[tuple[str, str, str]] = []
        table = getattr(getattr(self, "crawler_tab", None), "table_list", None)
        if table is None:
            return rows, -1
        for row in range(table.rowCount()):
            name_item = table.item(row, 0)
            cid_item = table.item(row, 1)
            asset_item = table.item(row, 2)
            asset_type = str(asset_item.text() if asset_item else "APT").strip().upper() or "APT"
            if asset_type not in {"APT", "VL"}:
                asset_type = "APT"
            rows.append(
                (
                    name_item.text() if name_item else "",
                    cid_item.text() if cid_item else "",
                    asset_type,
                )
            )
        return rows, table.currentRow()

    def _restore_crawler_tasks(self: Any, rows: list[tuple[str, ...]], current_row: int = -1) -> None:
        if not hasattr(self, "crawler_tab"):
            return
        self.crawler_tab.clear_tasks()
        for row in rows:
            name = row[0] if len(row) >= 1 else ""
            cid = row[1] if len(row) >= 2 else ""
            asset_type = row[2] if len(row) >= 3 else "APT"
            self.crawler_tab._append_task_row(str(name), str(cid), str(asset_type))
        if rows and 0 <= current_row < len(rows):
            self.crawler_tab.table_list.selectRow(current_row)
        elif getattr(self.crawler_tab, "table_list", None) is not None:
            self.crawler_tab.table_list.clearSelection()

    def _mark_schedule_run_started(self: Any, config: dict[str, Any], slot: str) -> None:
        config["last_run_slot"] = slot
        config["last_run_at"] = DateTimeHelper.now_string()
        self._schedule_skip_notice_key = None
        settings.update(
            {
                "schedule_config": config,
                "schedule_geo_lat": config["geo"]["lat"],
                "schedule_geo_lon": config["geo"]["lon"],
            }
        )

    def _check_schedule(self: Any):
        if not self.check_schedule.isChecked():
            self.is_scheduled_run = False
            self._schedule_skip_notice_key = None
            return
        config = self._collect_schedule_config()
        mode = str(config.get("mode", "complex") or "complex")
        if mode == "complex" and self.schedule_group_combo.count() == 0:
            self.is_scheduled_run = False
            self._schedule_skip_notice_key = None
            return

        current_dt = datetime.now()
        target_time = QTime.fromString(str(config.get("time", "09:00") or "09:00"), "HH:mm")
        if not target_time.isValid():
            target_time = QTime(9, 0)
        target_dt = current_dt.replace(
            hour=target_time.hour(),
            minute=target_time.minute(),
            second=0,
            microsecond=0,
        )
        catchup_deadline = target_dt + timedelta(minutes=self.SCHEDULE_CATCHUP_WINDOW_MINUTES)
        if current_dt < target_dt or current_dt >= catchup_deadline:
            self.is_scheduled_run = False
            self._schedule_skip_notice_key = None
            return

        slot = self._schedule_slot_for(config, current_dt)
        if str(config.get("last_run_slot", "") or "") == slot:
            self.is_scheduled_run = False
            self._schedule_skip_notice_key = None
            return

        self.is_scheduled_run = bool(self._run_scheduled(slot=slot))

    def _run_scheduled(self: Any, slot: str | None = None) -> bool:
        config = self._collect_schedule_config()
        mode = str(config.get("mode", "complex") or "complex")
        active_slot = slot or self._schedule_slot_for(config)
        from src.core.crawl_lock import get_crawl_lock

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
        lock_held = get_crawl_lock().is_held()
        if crawler_running or geo_running or lock_held:
            owner = get_crawl_lock().owner() or "busy"
            self._remember_schedule_skip(
                active_slot,
                "busy",
                f"⏸ 예약 작업 건너뜀: 다른 수집이 이미 실행 중입니다. ({owner})",
            )
            return False

        if mode == "geo_sweep":
            geo = config.get("geo", {}) if isinstance(config.get("geo"), dict) else {}
            raw_asset_types = geo.get("asset_types", None)
            asset_types = self._normalize_geo_asset_types(
                raw_asset_types,
                default_to_all=raw_asset_types is None,
            )
            if not asset_types:
                self._remember_schedule_skip(
                    active_slot,
                    "missing_geo_asset_type",
                    "⏸ 예약 Geo 작업 중단: 최소 하나의 자산 유형(APT 또는 VL)을 선택해주세요.",
                )
                return False
            self.tabs.setCurrentWidget(self.geo_tab)
            self.geo_tab.apply_geo_profile(
                lat=float(geo.get("lat", self.schedule_geo_lat.value())),
                lon=float(geo.get("lon", self.schedule_geo_lon.value())),
                zoom=int(geo.get("zoom", settings.get("geo_default_zoom", 15) or 15)),
                rings=int(geo.get("rings", settings.get("geo_grid_rings", 1) or 1)),
                step_px=int(geo.get("step_px", settings.get("geo_grid_step_px", 480) or 480)),
                dwell_ms=int(geo.get("dwell_ms", settings.get("geo_sweep_dwell_ms", 600) or 600)),
                asset_types=asset_types,
                persist_last=False,
            )
            if self.geo_tab.start_crawling():
                self._mark_schedule_run_started(config, active_slot)
                self.status_bar.showMessage(
                    f"⏰ 예약 Geo 작업 시작: {self.geo_tab.spin_lat.value():.6f}, {self.geo_tab.spin_lon.value():.6f}"
                )
                return True
            return False

        gid = config.get("group_id", self.schedule_group_combo.currentData())
        if gid is None:
            self._remember_schedule_skip(active_slot, "missing_group", "⏸ 예약 작업 중단: 선택된 그룹이 없습니다.")
            return False

        previous_rows, previous_current_row = self._snapshot_crawler_tasks()
        self.tabs.setCurrentWidget(self.crawler_tab)
        self.crawler_tab.clear_tasks()
        excluded_vl = 0
        loaded_count = 0
        engine_name = str(settings.get("crawl_engine", "playwright") or "playwright").strip().lower() or "playwright"
        for _, name, asset_type, cid, _ in self.db.get_complexes_in_group(gid):
            asset_token = str(asset_type or "APT").strip().upper() or "APT"
            if asset_token not in {"APT", "VL"}:
                asset_token = "APT"
            if engine_name == "selenium" and asset_token != "APT":
                excluded_vl += 1
                continue
            if self.crawler_tab.add_task(name, cid, asset_token):
                loaded_count += 1
        if excluded_vl > 0:
            msg = f"Selenium complex 모드는 APT만 지원하여 VL {excluded_vl}개를 제외했습니다."
            self.crawler_tab.append_log(f"ℹ️ {msg}", 20)
            self.status_bar.showMessage(msg)
            ui_logger.info(f"예약 작업 필터링: group={gid}, excluded_vl={excluded_vl}")
        if loaded_count <= 0:
            self._restore_crawler_tasks(previous_rows, previous_current_row)
            self._remember_schedule_skip(
                active_slot,
                "no_target",
                "⏸ 예약 작업 중단: 실행 가능한 대상이 없습니다.",
            )
            return False
        if self.crawler_tab.start_crawling():
            self._mark_schedule_run_started(config, active_slot)
            self.status_bar.showMessage(f"⏰ 예약 작업 시작: 그룹 {gid}")
            return True
        self._restore_crawler_tasks(previous_rows, previous_current_row)
        return False
