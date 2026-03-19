from __future__ import annotations

import json
from copy import deepcopy
from threading import Lock
from typing import Any, List
from src.utils.paths import DATA_DIR, SETTINGS_PATH, PRESETS_PATH, HISTORY_PATH
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper
from src.utils.json_store import atomic_write_json, load_json_with_recovery

DEFAULT_SETTINGS = {
    "theme": "dark", "crawl_speed": "보통", "minimize_to_tray": True,
    "show_notifications": True, "confirm_before_close": True,
    "play_sound_on_complete": True, "default_sort_column": "가격",
    "default_sort_order": "asc", "max_search_history": 20,
    "window_geometry": None, "splitter_sizes": None,
    "crawler_main_splitter_sizes": None,
    "crawler_controls_splitter_sizes": None,
    # v7.3 설정
    "excel_template": None,  # 엑셀 컬럼 템플릿
    "show_new_badge": True,  # 신규 매물 배지 표시
    "show_price_change": True,  # 가격 변동 표시
    "price_change_threshold": 0,  # 가격 변동 알림 기준 (만원, 0=모두)
    # v12.0 설정
    "cache_enabled": True,  # 캐시 사용 여부
    "cache_ttl_minutes": 30,  # 캐시 유효시간 (분)
    "cache_negative_ttl_minutes": 5,  # 0건 결과 캐시 유효시간(분)
    "cache_write_back_interval_sec": 2,  # 캐시 파일 write-back 주기
    "cache_max_entries": 2000,  # 최대 캐시 엔트리 수
    "show_price_per_pyeong": True,  # 평당가 표시
    "track_disappeared": True,  # 매물 소멸 추적
    "visible_columns": None,  # 표시할 컬럼 목록
    # v13.0 신규 설정
    "view_mode": "table",  # table | card (뷰 모드)
    "show_trend_analysis": True,  # 트렌드 분석 표시
    "retry_on_error": True,  # 오류 시 재시도
    "max_retry_count": 3,  # 최대 재시도 횟수
    "recently_viewed_count": 50,  # 최근 본 매물 개수
    "ui_batch_interval_ms": 120,  # UI 배치 반영 주기 (ms)
    "ui_batch_size": 30,  # UI 배치 반영 최대 건수
    "history_batch_size": 200,  # 이력 DB 일괄 반영 크기
    "result_filter_debounce_ms": 220,  # 결과 검색 디바운스
    "max_log_lines": 1500,  # 로그 최대 라인 수
    "startup_lazy_noncritical_tabs": False,  # 레거시 설정키 유지(현재는 대시보드만 첫 진입 시 로드)
    "compact_duplicate_listings": True,  # 동일 매물(가격/평수/층) 묶어서 표시
    "crawl_engine": "playwright",
    "fallback_engine_enabled": True,
    "playwright_headless": False,
    "playwright_detail_workers": 12,
    "playwright_block_heavy_resources": True,
    "playwright_response_drain_timeout_ms": 3000,
    "geo_incomplete_safety_mode": True,
    "geo_default_zoom": 15,
    "geo_grid_rings": 1,
    "geo_grid_step_px": 480,
    "geo_sweep_dwell_ms": 600,
    "geo_asset_types": ["APT", "VL"],
    "geo_last_lat": 37.5608,
    "geo_last_lon": 126.9888,
    "schedule_geo_lat": 37.5608,
    "schedule_geo_lon": 126.9888,
    "schedule_config": {
        "enabled": False,
        "mode": "complex",
        "time": "09:00",
        "group_id": None,
        "last_run_slot": "",
        "last_run_at": "",
        "geo": {
            "lat": 37.5608,
            "lon": 126.9888,
            "zoom": 15,
            "rings": 1,
            "step_px": 480,
            "dwell_ms": 600,
            "asset_types": ["APT", "VL"],
        },
    },
}

DEPRECATED_SETTINGS_KEYS = {"result_tab_mode"}


def _normalize_schedule_asset_types(asset_types: Any) -> list[str]:
    normalized: list[str] = []
    for asset in asset_types or []:
        token = str(asset or "").strip().upper()
        if token in {"APT", "VL"} and token not in normalized:
            normalized.append(token)
    return normalized or ["APT", "VL"]


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


def _sanitize_settings_payload(value: Any) -> dict[str, Any]:
    sanitized = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(value, dict):
        sanitized["schedule_config"] = _normalize_schedule_config(sanitized.get("schedule_config"))
        return sanitized

    for key, raw in value.items():
        if key in DEPRECATED_SETTINGS_KEYS:
            continue
        if key == "schedule_config":
            sanitized[key] = _normalize_schedule_config(raw)
            continue
        sanitized[key] = raw

    sanitized.pop("result_tab_mode", None)
    sanitized["schedule_config"] = _normalize_schedule_config(sanitized.get("schedule_config"))
    return sanitized

class SettingsManager:
    _instance = None
    _lock = Lock()
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    def __init__(self):
        if self._initialized: return
        self._initialized = True
        self._settings: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        payload = load_json_with_recovery(
            SETTINGS_PATH,
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
            atomic_write_json(SETTINGS_PATH, self._settings)
        except OSError as e:
            get_logger('SettingsManager').warning(f"설정 저장 실패: {e}")
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

class FilterPresetManager:
    def __init__(self):
        self._presets = {}
        self._load()
    def _load(self):
        payload = load_json_with_recovery(
            PRESETS_PATH,
            default_factory=dict,
            logger_name="FilterPresetManager",
            label="presets",
        )
        self._presets = payload if isinstance(payload, dict) else {}
    def _save(self):
        try:
            atomic_write_json(PRESETS_PATH, self._presets)
        except OSError as e:
            get_logger('FilterPresetManager').warning(f"프리셋 저장 실패: {e}")
    def add(self, name, config): self._presets[name] = config; self._save(); return True
    def save_preset(self, name, config): return self.add(name, config)
    def get(self, name): return self._presets.get(name)
    def delete(self, name):
        if name in self._presets: del self._presets[name]; self._save(); return True
        return False
    def get_all_names(self): return list(self._presets.keys())

class SearchHistoryManager:
    """최근 검색 기록 관리"""
    def __init__(self, max_items=20):
        self.max_items = max_items
        self._history = []
        self._load()
    
    def _load(self):
        payload = load_json_with_recovery(
            HISTORY_PATH,
            default_factory=list,
            logger_name="SearchHistoryManager",
            label="search_history",
        )
        self._history = payload if isinstance(payload, list) else []
    
    def _save(self):
        try:
            atomic_write_json(HISTORY_PATH, self._history[:self.max_items])
        except OSError as e:
            get_logger('SearchHistoryManager').warning(f"검색 기록 저장 실패: {e}")

    @staticmethod
    def _normalize_complexes(complexes) -> list[dict]:
        normalized = []
        for item in complexes or []:
            if isinstance(item, dict):
                name = str(item.get("name", "") or "")
                cid = str(item.get("cid", "") or "")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                name = str(item[0] or "")
                cid = str(item[1] or "")
            else:
                continue
            normalized.append({"name": name, "cid": cid})
        normalized.sort(key=lambda x: (x["cid"], x["name"]))
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
        payload['timestamp'] = DateTimeHelper.now_string()
        key = self._dedupe_key(payload)
        # 중복 제거
        self._history = [h for h in self._history if self._dedupe_key(h) != key]
        self._history.insert(0, payload)
        self._history = self._history[:self.max_items]
        self._save()
    
    def get_recent(self, count=10):
        return self._history[:count]
    
    def clear(self):
        """검색 기록 전체 삭제"""
        self._history = []
        self._save()

class RecentlyViewedManager:
    """최근 본 매물 관리 (v13.0)"""
    
    MAX_ITEMS = 50
    STORAGE_PATH = DATA_DIR / "recently_viewed.json"
    
    def __init__(self, max_items: int | None = None):
        self.max_items = self._normalize_max_items(max_items)
        self._items: List[dict] = []
        self._lock = Lock()
        self._load()

    @classmethod
    def _normalize_max_items(cls, max_items: int | None) -> int:
        try:
            value = int(max_items if max_items is not None else cls.MAX_ITEMS)
        except (TypeError, ValueError):
            value = cls.MAX_ITEMS
        return max(1, value)

    @staticmethod
    def _article_identity(article: dict[str, Any]) -> tuple[str, str, str]:
        asset_type = str(article.get("자산유형", article.get("asset_type", "APT")) or "APT").strip().upper() or "APT"
        complex_id = str(article.get("단지ID", article.get("complex_id", "")) or "").strip()
        article_id = str(article.get("매물ID", article.get("article_id", "")) or "").strip()
        return asset_type, complex_id, article_id
    
    def _load(self):
        """파일에서 로드"""
        payload = load_json_with_recovery(
            self.STORAGE_PATH,
            default_factory=list,
            logger_name="RecentlyViewedManager",
            label="recently_viewed",
        )
        self._items = list(payload[:self.max_items]) if isinstance(payload, list) else []
    
    def _save(self):
        """파일에 저장"""
        try:
            atomic_write_json(self.STORAGE_PATH, self._items[:self.max_items])
        except OSError as e:
            get_logger('RecentlyViewedManager').warning(f"최근 본 매물 저장 실패: {e}")

    def set_max_items(self, max_items: int | None) -> None:
        with self._lock:
            self.max_items = self._normalize_max_items(max_items)
            self._items = self._items[:self.max_items]
            self._save()
    
    def add(self, article: dict):
        """최근 본 매물 추가"""
        with self._lock:
            article_copy = dict(article or {})
            _, _, article_id = self._article_identity(article_copy)
            if not article_id:
                return

            article_key = self._article_identity(article_copy)
            # 기존 항목 제거 (중복 방지)
            self._items = [
                item for item in self._items 
                if self._article_identity(item) != article_key
            ]
            
            # 맨 앞에 추가
            article_copy["viewed_at"] = DateTimeHelper.now_string()
            self._items.insert(0, article_copy)
            
            # 최대 개수 유지
            self._items = self._items[:self.max_items]
            self._save()
    
    def get_recent(self, count: int | None = None) -> List[dict]:
        """최근 본 매물 목록"""
        limit = self.max_items if count is None else max(1, int(count))
        return self._items[:limit]
    
    def clear(self):
        """전체 삭제"""
        with self._lock:
            self._items = []
            self._save()
