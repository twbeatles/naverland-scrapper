"""Managers facade (SOLID split).

Single-responsibility owners live in :mod:`src.core.managers_parts`:

- ``schedule_defaults`` — default settings payload and deprecated keys.
- ``schedule_normalize`` — schedule-config normalization helpers.
- ``settings_sanitize`` — settings payload sanitization.
- ``settings_manager`` — :class:`SettingsManager` singleton + accessor.
- ``runtime_kwargs`` — collection runtime kwargs builder.
- ``filter_preset`` — :class:`FilterPresetManager` (ISP: preset persistence).
- ``search_history`` — :class:`SearchHistoryManager` (ISP: search history).
- ``recently_viewed`` — :class:`RecentlyViewedManager` (ISP: viewed articles).

This module re-exports the full previous public surface so existing
``from src.core.managers import ...`` imports keep working.
"""
from __future__ import annotations

from src.core.managers_parts.schedule_defaults import (
    DEFAULT_SETTINGS,
    DEPRECATED_SETTINGS_KEYS,
)
from src.core.managers_parts.schedule_normalize import (
    _clamp_int,
    _normalize_schedule_asset_types,
    _normalize_schedule_config,
)
from src.core.managers_parts.settings_sanitize import _sanitize_settings_payload
from src.core.managers_parts.settings_manager import (
    SettingsManager,
    _SettingsAccessor,
    get_settings,
    settings,
)
from src.core.managers_parts.runtime_kwargs import collection_runtime_kwargs
from src.core.managers_parts.filter_preset import FilterPresetManager
from src.core.managers_parts.search_history import SearchHistoryManager
from src.core.managers_parts.recently_viewed import RecentlyViewedManager

__all__ = [
    "DEFAULT_SETTINGS",
    "DEPRECATED_SETTINGS_KEYS",
    "SettingsManager",
    "get_settings",
    "settings",
    "FilterPresetManager",
    "SearchHistoryManager",
    "RecentlyViewedManager",
    "collection_runtime_kwargs",
    "_normalize_schedule_asset_types",
    "_normalize_schedule_config",
    "_clamp_int",
    "_sanitize_settings_payload",
    "_SettingsAccessor",
]
