from __future__ import annotations

from typing import Any
from src.utils import paths as paths_util
from src.utils.logger import get_logger
from src.utils.json_store import atomic_write_json, load_json_with_recovery


class FilterPresetManager:
    def __init__(self):
        self._presets = {}
        self._load()

    def _load(self):
        payload = load_json_with_recovery(
            paths_util.get_presets_path(),
            default_factory=dict,
            logger_name="FilterPresetManager",
            label="presets",
        )
        self._presets = payload if isinstance(payload, dict) else {}

    def _save(self):
        try:
            atomic_write_json(paths_util.get_presets_path(), self._presets)
        except OSError as e:
            get_logger("FilterPresetManager").warning(f"프리셋 저장 실패: {e}")

    def add(self, name, config):
        self._presets[name] = config
        self._save()
        return True

    def save_preset(self, name, config):
        return self.add(name, config)

    def get(self, name):
        return self._presets.get(name)

    def delete(self, name):
        if name in self._presets:
            del self._presets[name]
            self._save()
            return True
        return False

    def get_all_names(self):
        return list(self._presets.keys())
