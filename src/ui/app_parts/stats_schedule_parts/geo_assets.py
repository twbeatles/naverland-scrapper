from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleGeoAssetsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    @staticmethod
    def _normalize_geo_asset_types(asset_types, *, default_to_all: bool = True) -> list[str]:
        normalized_assets = []
        for asset in asset_types or []:
            token = str(asset or "").strip().upper()
            if token in {"APT", "VL"} and token not in normalized_assets:
                normalized_assets.append(token)
        if normalized_assets:
            return normalized_assets
        return ["APT", "VL"] if default_to_all else []

    def _selected_schedule_geo_assets(self: Any) -> list[str]:
        selected = []
        if getattr(self, "schedule_geo_asset_apt", None) and self.schedule_geo_asset_apt.isChecked():
            selected.append("APT")
        if getattr(self, "schedule_geo_asset_vl", None) and self.schedule_geo_asset_vl.isChecked():
            selected.append("VL")
        return selected

    def _set_schedule_geo_assets(self: Any, asset_types) -> None:
        asset_tokens = set(
            self._normalize_geo_asset_types(
                asset_types,
                default_to_all=asset_types is None,
            )
        )
        if hasattr(self, "schedule_geo_asset_apt"):
            self.schedule_geo_asset_apt.setChecked("APT" in asset_tokens)
        if hasattr(self, "schedule_geo_asset_vl"):
            self.schedule_geo_asset_vl.setChecked("VL" in asset_tokens)

    def _schedule_geo_defaults(self: Any):
        raw_assets = settings.get("geo_asset_types", ["APT", "VL"])
        normalized_assets = self._normalize_geo_asset_types(
            raw_assets,
            default_to_all=raw_assets is None,
        )
        return {
            "lat": float(settings.get("schedule_geo_lat", 37.5608) or 37.5608),
            "lon": float(settings.get("schedule_geo_lon", 126.9888) or 126.9888),
            "zoom": int(settings.get("geo_default_zoom", 15) or 15),
            "rings": int(settings.get("geo_grid_rings", 1) or 1),
            "step_px": int(settings.get("geo_grid_step_px", 480) or 480),
            "dwell_ms": int(settings.get("geo_sweep_dwell_ms", 600) or 600),
            "asset_types": normalized_assets or ["APT", "VL"],
        }
