from __future__ import annotations

from copy import deepcopy
from typing import Any
from src.core.managers_parts.schedule_defaults import DEFAULT_SETTINGS


def _normalize_schedule_asset_types(asset_types: Any) -> list[str]:
    if asset_types is None:
        return ["APT", "VL"]
    if isinstance(asset_types, str):
        candidates = [asset_types]
    else:
        candidates = list(asset_types or [])
    normalized: list[str] = []
    for asset in candidates:
        token = str(asset or "").strip().upper()
        if token in {"APT", "VL"} and token not in normalized:
            normalized.append(token)
    return normalized


def _normalize_schedule_config(value: Any) -> dict[str, Any]:
    default = deepcopy(DEFAULT_SETTINGS["schedule_config"])
    if not isinstance(value, dict):
        return default

    normalized = deepcopy(default)
    normalized["enabled"] = bool(value.get("enabled", default["enabled"]))
    normalized["mode"] = str(value.get("mode", default["mode"]) or default["mode"])
    normalized["time"] = str(value.get("time", default["time"]) or default["time"])
    normalized["group_id"] = value.get("group_id")
    normalized["last_run_slot"] = str(value.get("last_run_slot", "") or "")
    normalized["last_run_at"] = str(value.get("last_run_at", "") or "")

    geo_value = value.get("geo")
    if isinstance(geo_value, dict):
        geo = normalized["geo"]
        geo["lat"] = geo_value.get("lat", geo["lat"])
        geo["lon"] = geo_value.get("lon", geo["lon"])
        geo["zoom"] = geo_value.get("zoom", geo["zoom"])
        geo["rings"] = geo_value.get("rings", geo["rings"])
        geo["step_px"] = geo_value.get("step_px", geo["step_px"])
        geo["dwell_ms"] = geo_value.get("dwell_ms", geo["dwell_ms"])
        geo["asset_types"] = _normalize_schedule_asset_types(
            geo_value.get("asset_types", geo["asset_types"])
        )
    return normalized


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, min(maximum, parsed))
