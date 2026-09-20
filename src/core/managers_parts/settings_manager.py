from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any
from src.utils import paths as paths_util
from src.utils.logger import get_logger
from src.utils.json_store import atomic_write_json, load_json_with_recovery
from src.core.managers_parts.schedule_defaults import (
    DEFAULT_SETTINGS,
    DEPRECATED_SETTINGS_KEYS,
)
from src.core.managers_parts.schedule_normalize import _normalize_schedule_config
from src.core.managers_parts.settings_sanitize import _sanitize_settings_payload


class SettingsManager:
    _instance = None
    _lock = Lock()

    @classmethod
    def reset_for_tests(cls) -> None:
        with cls._lock:
            cls._instance = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._settings: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        payload = load_json_with_recovery(
            paths_util.get_settings_path(),
            default_factory=lambda: deepcopy(DEFAULT_SETTINGS),
            logger_name="SettingsManager",
            label="settings",
        )
        if isinstance(payload, dict):
            self._settings = _sanitize_settings_payload(payload)
            if payload != self._settings:
                self._save()
        else:
            self._settings = deepcopy(DEFAULT_SETTINGS)
            self._save()

    def _save(self):
        try:
            self._settings = _sanitize_settings_payload(self._settings)
            atomic_write_json(paths_util.get_settings_path(), self._settings)
        except OSError as e:
            get_logger("SettingsManager").warning(f"설정 저장 실패: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if key in DEPRECATED_SETTINGS_KEYS:
            self._settings.pop(key, None)
            self._save()
            return
        if key == "schedule_config":
            self._settings[key] = _normalize_schedule_config(value)
            self._save()
            return
        self._settings[key] = value
        self._save()

    def update(self, data: dict[str, Any]) -> None:
        payload = dict(data or {})
        for key in DEPRECATED_SETTINGS_KEYS:
            payload.pop(key, None)
        if "schedule_config" in payload:
            payload["schedule_config"] = _normalize_schedule_config(payload["schedule_config"])
        self._settings.update(payload)
        self._settings.pop("result_tab_mode", None)
        self._save()


class _SettingsAccessor:
    """Module-level accessor delegating to the SettingsManager singleton."""

    def get(self, key: str, default: Any = None) -> Any:
        return get_settings().get(key, default)

    def set(self, key: str, value: Any) -> None:
        get_settings().set(key, value)

    def update(self, data: dict[str, Any]) -> None:
        get_settings().update(data)

    @property
    def _settings(self) -> dict[str, Any]:
        return get_settings()._settings

    @_settings.setter
    def _settings(self, value: dict[str, Any]) -> None:
        get_settings()._settings = value

    def _save(self) -> None:
        get_settings()._save()


def get_settings() -> SettingsManager:
    return SettingsManager()


settings = _SettingsAccessor()
