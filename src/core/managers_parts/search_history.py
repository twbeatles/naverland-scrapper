from __future__ import annotations

import json
from typing import Any
from src.utils import paths as paths_util
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper
from src.utils.json_store import atomic_write_json, load_json_with_recovery


class SearchHistoryManager:
    """최근 검색 기록 관리"""

    def __init__(self, max_items=20):
        self.max_items = max_items
        self._history = []
        self._load()

    def _load(self):
        payload = load_json_with_recovery(
            paths_util.get_history_path(),
            default_factory=list,
            logger_name="SearchHistoryManager",
            label="search_history",
        )
        self._history = payload if isinstance(payload, list) else []

    def _save(self):
        try:
            atomic_write_json(paths_util.get_history_path(), self._history[: self.max_items])
        except OSError as e:
            get_logger("SearchHistoryManager").warning(f"검색 기록 저장 실패: {e}")

    @staticmethod
    def _normalize_complexes(complexes) -> list[dict]:
        normalized = []
        for item in complexes or []:
            if isinstance(item, dict):
                name = str(item.get("name", "") or "")
                cid = str(item.get("cid", "") or "")
                asset_type = str(item.get("asset_type", "APT") or "APT").strip().upper() or "APT"
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                name = str(item[0] or "")
                cid = str(item[1] or "")
                asset_type = str(item[2] if len(item) >= 3 else "APT" or "APT").strip().upper() or "APT"
            else:
                continue
            normalized.append({"name": name, "cid": cid, "asset_type": asset_type})
        normalized.sort(key=lambda x: (x["asset_type"], x["cid"], x["name"]))
        return normalized

    @staticmethod
    def _canonical_obj(value: Any):
        if isinstance(value, dict):
            return {str(k): SearchHistoryManager._canonical_obj(value[k]) for k in sorted(value.keys())}
        if isinstance(value, list):
            return [SearchHistoryManager._canonical_obj(v) for v in value]
        return value

    @classmethod
    def _dedupe_key(cls, search_info: dict) -> str:
        payload = {
            "complexes": cls._normalize_complexes(search_info.get("complexes", [])),
            "trade_types": sorted([str(t) for t in (search_info.get("trade_types") or [])]),
            "area_filter": cls._canonical_obj(search_info.get("area_filter") or {}),
            "price_filter": cls._canonical_obj(search_info.get("price_filter") or {}),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def add(self, search_info):
        """검색 기록 추가"""
        payload = dict(search_info or {})
        payload["timestamp"] = DateTimeHelper.now_string()
        key = self._dedupe_key(payload)
        self._history = [h for h in self._history if self._dedupe_key(h) != key]
        self._history.insert(0, payload)
        self._history = self._history[: self.max_items]
        self._save()

    def get_recent(self, count=10):
        return self._history[:count]

    def clear(self):
        """검색 기록 전체 삭제"""
        self._history = []
        self._save()
