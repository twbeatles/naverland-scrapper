from __future__ import annotations

import json
from threading import Lock
from typing import Any, List
from pathlib import Path
from src.utils.paths import DATA_DIR, SETTINGS_PATH, PRESETS_PATH, HISTORY_PATH
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper

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
    "result_tab_mode": "combined",  # combined | separate (거래유형별 탭)
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
    "startup_lazy_noncritical_tabs": True,  # 비핵심 탭 초기 로드 지연
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
    "schedule_geo_lat": 37.5608,
    "schedule_geo_lon": 126.9888,
    "schedule_config": {
        "enabled": False,
        "mode": "complex",
        "time": "09:00",
        "group_id": None,
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
        self._settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
        self._load()

    @staticmethod
    def _backup_broken_settings(path: Path) -> Path | None:
        try:
            suffix = DateTimeHelper.now_string().replace(":", "").replace(" ", "_")
            backup_path = path.with_suffix(path.suffix + f".broken.{suffix}")
            path.replace(backup_path)
            return backup_path
        except OSError:
            return None

    def _load(self):
        logger = get_logger("SettingsManager")
        if SETTINGS_PATH.exists():
            try:
                with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    self._settings.update(json.load(f))
            except (OSError, json.JSONDecodeError) as e:
                backup = self._backup_broken_settings(SETTINGS_PATH)
                logger.warning(f"설정 로드 실패, 기본값으로 복구합니다: {e}")
                if backup:
                    logger.warning(f"손상된 설정 파일 백업: {backup}")
                self._settings = DEFAULT_SETTINGS.copy()
                self._save()
    def _save(self):
        try:
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('SettingsManager').warning(f"설정 저장 실패: {e}")
    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save()

    def update(self, data: dict[str, Any]) -> None:
        self._settings.update(data)
        self._save()

class FilterPresetManager:
    def __init__(self):
        self._presets = {}
        self._load()
    def _load(self):
        if PRESETS_PATH.exists():
            try:
                with open(PRESETS_PATH, 'r', encoding='utf-8') as f:
                    self._presets = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                get_logger('FilterPresetManager').warning(f"프리셋 로드 실패: {e}")
    def _save(self):
        try:
            with open(PRESETS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._presets, f, ensure_ascii=False, indent=2)
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
        if HISTORY_PATH.exists():
            try:
                with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                get_logger('SearchHistoryManager').warning(f"검색 기록 로드 실패: {e}")
    
    def _save(self):
        try:
            with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._history[:self.max_items], f, ensure_ascii=False, indent=2)
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
    
    def __init__(self):
        self._items: List[dict] = []
        self._lock = Lock()
        self._load()
    
    def _load(self):
        """파일에서 로드"""
        if self.STORAGE_PATH.exists():
            try:
                with open(self.STORAGE_PATH, 'r', encoding='utf-8') as f:
                    self._items = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._items = []
    
    def _save(self):
        """파일에 저장"""
        try:
            with open(self.STORAGE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._items[:self.MAX_ITEMS], f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('RecentlyViewedManager').warning(f"최근 본 매물 저장 실패: {e}")
    
    def add(self, article: dict):
        """최근 본 매물 추가"""
        with self._lock:
            article_id = article.get("매물ID", "")
            if not article_id:
                return
            
            # 기존 항목 제거 (중복 방지)
            self._items = [
                item for item in self._items 
                if item.get("매물ID") != article_id
            ]
            
            # 맨 앞에 추가
            article["viewed_at"] = DateTimeHelper.now_string()
            self._items.insert(0, article)
            
            # 최대 개수 유지
            self._items = self._items[:self.MAX_ITEMS]
            self._save()
    
    def get_recent(self, count: int = 20) -> List[dict]:
        """최근 본 매물 목록"""
        return self._items[:count]
    
    def clear(self):
        """전체 삭제"""
        with self._lock:
            self._items = []
            self._save()
