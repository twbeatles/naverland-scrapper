from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleConfigMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _collect_schedule_config(self: Any):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        current = settings.get("schedule_config", {}) or {}
        return {
            "enabled": bool(self.check_schedule.isChecked()),
            "mode": mode,
            "time": self.time_edit.time().toString("HH:mm"),
            "group_id": self.schedule_group_combo.currentData(),
            "last_run_slot": str(current.get("last_run_slot", "") or ""),
            "last_run_at": str(current.get("last_run_at", "") or ""),
            "geo": {
                "lat": float(self.schedule_geo_lat.value()),
                "lon": float(self.schedule_geo_lon.value()),
                "zoom": int(self.schedule_geo_zoom.value()),
                "rings": int(self.schedule_geo_rings.value()),
                "step_px": int(self.schedule_geo_step.value()),
                "dwell_ms": int(self.schedule_geo_dwell.value()),
                "asset_types": self._selected_schedule_geo_assets(),
            },
        }

    def _save_schedule_config(self: Any, *_args):
        if bool(getattr(self, "_schedule_hydrating", False)):
            return settings.get("schedule_config", {}) or {}
        config = self._collect_schedule_config()
        if (
            str(config.get("mode", "complex") or "complex") == "geo_sweep"
            and not self._normalize_geo_asset_types(config["geo"].get("asset_types", []), default_to_all=False)
        ):
            QMessageBox.warning(self, "경고", "최소 하나의 자산 유형(APT 또는 VL)을 선택해주세요.")
            self.status_bar.showMessage("예약 Geo 설정 저장 중단: 최소 하나의 자산 유형을 선택해주세요.")
            return settings.get("schedule_config", {}) or {}
        settings.update(
            {
                "schedule_config": config,
                "schedule_geo_lat": config["geo"]["lat"],
                "schedule_geo_lon": config["geo"]["lon"],
            }
        )
        return config

    def _schedule_target_descriptor(self: Any, config: dict[str, Any]) -> str:
        mode = str(config.get("mode", "complex") or "complex")
        if mode == "geo_sweep":
            geo = config.get("geo", {}) if isinstance(config.get("geo"), dict) else {}
            raw_asset_types = geo.get("asset_types", ["APT", "VL"])
            asset_types = self._normalize_geo_asset_types(
                raw_asset_types,
                default_to_all=raw_asset_types is None,
            )
            return (
                f"{float(geo.get('lat', 37.5608)):.6f}/"
                f"{float(geo.get('lon', 126.9888)):.6f}/"
                f"{int(geo.get('zoom', 15))}/"
                f"{int(geo.get('rings', 1))}/"
                f"{int(geo.get('step_px', 480))}/"
                f"{int(geo.get('dwell_ms', 600))}/"
                f"{','.join(asset_types)}"
            )
        return str(config.get("group_id", "") or "")

    def _schedule_slot_for(self: Any, config: dict[str, Any], now_dt=None) -> str:
        current_dt = now_dt or datetime.now()
        time_text = str(config.get("time", "09:00") or "09:00")
        mode = str(config.get("mode", "complex") or "complex")
        target = self._schedule_target_descriptor(config)
        return f"{current_dt.strftime('%Y-%m-%d')}|{time_text}|{mode}|{target}"

    def _remember_schedule_skip(self: Any, slot: str, reason: str, message: str) -> None:
        notice_key = (slot, reason)
        if getattr(self, "_schedule_skip_notice_key", None) == notice_key:
            return
        self._schedule_skip_notice_key = notice_key
        self.status_bar.showMessage(message)
        ui_logger.info(f"{message} [slot={slot}]")

    def _load_schedule_config(self: Any):
        config = settings.get("schedule_config", {}) or {}
        mode = str(config.get("mode", "complex") or "complex")
        time_text = str(config.get("time", "09:00") or "09:00")
        geo_config = config.get("geo", {}) if isinstance(config.get("geo"), dict) else {}

        previous_hydrating = bool(getattr(self, "_schedule_hydrating", False))
        self._schedule_hydrating = True
        self.check_schedule.blockSignals(True)
        self.time_edit.blockSignals(True)
        self.schedule_mode_combo.blockSignals(True)
        self.schedule_group_combo.blockSignals(True)
        self.schedule_geo_lat.blockSignals(True)
        self.schedule_geo_lon.blockSignals(True)
        self.schedule_geo_zoom.blockSignals(True)
        self.schedule_geo_rings.blockSignals(True)
        self.schedule_geo_step.blockSignals(True)
        self.schedule_geo_dwell.blockSignals(True)
        self.schedule_geo_asset_apt.blockSignals(True)
        self.schedule_geo_asset_vl.blockSignals(True)
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
            zoom = geo_config.get("zoom", settings.get("geo_default_zoom", 15))
            rings = geo_config.get("rings", settings.get("geo_grid_rings", 1))
            step_px = geo_config.get("step_px", settings.get("geo_grid_step_px", 480))
            dwell_ms = geo_config.get("dwell_ms", settings.get("geo_sweep_dwell_ms", 600))
            default_asset_types = settings.get("geo_asset_types", ["APT", "VL"])
            asset_types = geo_config.get("asset_types", default_asset_types)
            try:
                self.schedule_geo_lat.setValue(float(lat))
            except (TypeError, ValueError):
                self.schedule_geo_lat.setValue(37.5608)
            try:
                self.schedule_geo_lon.setValue(float(lon))
            except (TypeError, ValueError):
                self.schedule_geo_lon.setValue(126.9888)
            try:
                self.schedule_geo_zoom.setValue(int(zoom))
            except (TypeError, ValueError):
                self.schedule_geo_zoom.setValue(15)
            try:
                self.schedule_geo_rings.setValue(int(rings))
            except (TypeError, ValueError):
                self.schedule_geo_rings.setValue(1)
            try:
                self.schedule_geo_step.setValue(int(step_px))
            except (TypeError, ValueError):
                self.schedule_geo_step.setValue(480)
            try:
                self.schedule_geo_dwell.setValue(int(dwell_ms))
            except (TypeError, ValueError):
                self.schedule_geo_dwell.setValue(600)
            self._set_schedule_geo_assets(asset_types)
        finally:
            self.check_schedule.blockSignals(False)
            self.time_edit.blockSignals(False)
            self.schedule_mode_combo.blockSignals(False)
            self.schedule_group_combo.blockSignals(False)
            self.schedule_geo_lat.blockSignals(False)
            self.schedule_geo_lon.blockSignals(False)
            self.schedule_geo_zoom.blockSignals(False)
            self.schedule_geo_rings.blockSignals(False)
            self.schedule_geo_step.blockSignals(False)
            self.schedule_geo_dwell.blockSignals(False)
            self.schedule_geo_asset_apt.blockSignals(False)
            self.schedule_geo_asset_vl.blockSignals(False)

        self._on_schedule_mode_changed()
        self._schedule_hydrating = previous_hydrating

    def _load_schedule_groups(self: Any):
        current_gid = self.schedule_group_combo.currentData()
        selected = False
        previous_hydrating = bool(getattr(self, "_schedule_hydrating", False))
        self._schedule_hydrating = True
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
                        selected = True
            if not selected:
                try:
                    self.schedule_group_combo.setCurrentIndex(-1)
                except Exception:
                    pass
        finally:
            self.schedule_group_combo.blockSignals(False)
        self._update_schedule_state()
        self._schedule_hydrating = previous_hydrating

    def _on_schedule_mode_changed(self: Any, *_args):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        self.schedule_group_widget.setVisible(mode == "complex")
        self.schedule_geo_widget.setVisible(mode == "geo_sweep")
        self._update_schedule_state()
        self._save_schedule_config()
