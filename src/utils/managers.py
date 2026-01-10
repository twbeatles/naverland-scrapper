import json
from typing import List
from threading import Lock
from src.config import DATA_DIR
from src.utils.logger import get_logger
from src.utils.helpers import DateTimeHelper

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
        except OSError:
            pass

    def add(self, article: dict):
        """최근 본 매물 추가"""
        with self._lock:
            # 중복 제거 (매물ID 기준)
            aid = article.get('매물ID')
            if not aid: return
            
            # 기존 항목 제거
            self._items = [item for item in self._items if item.get('매물ID') != aid]
            
            # 맨 앞에 추가
            self._items.insert(0, article)
            
            # 최대 개수 유지
            if len(self._items) > self.MAX_ITEMS:
                self._items = self._items[:self.MAX_ITEMS]
                
            self._save()
    
    def get_recent(self, count: int = 20):
        """최근 본 매물 목록"""
        return self._items[:count]
    
    def clear(self):
        """전체 삭제"""
        with self._lock:
            self._items = []
            if self.STORAGE_PATH.exists():
                try:
                    self.STORAGE_PATH.unlink()
                except OSError:
                    pass

DEFAULT_SETTINGS = {
    "theme": "dark", "crawl_speed": "보통", "minimize_to_tray": True,
    "show_notifications": True, "confirm_before_close": True,
    "play_sound_on_complete": True, "default_sort_column": "가격",
    "default_sort_order": "asc", "max_search_history": 20,
    "window_geometry": None, "splitter_sizes": None,
    # v7.3 설정
    "excel_template": None,  # 엑셀 컬럼 템플릿
    "show_new_badge": True,  # 신규 매물 배지 표시
    "show_price_change": True,  # 가격 변동 표시
    "price_change_threshold": 0,  # 가격 변동 알림 기준 (만원, 0=모두)
    # v12.0 설정
    "cache_enabled": True,  # 캐시 사용 여부
    "cache_ttl_minutes": 30,  # 캐시 유효시간 (분)
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
        self._settings = DEFAULT_SETTINGS.copy()
        from src.config import SETTINGS_PATH
        self.SETTINGS_PATH = SETTINGS_PATH
        self._load()
    
    def _load(self):
        if self.SETTINGS_PATH.exists():
            try:
                with open(self.SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    self._settings.update(json.load(f))
            except (OSError, json.JSONDecodeError) as e:
                get_logger('SettingsManager').warning(f"설정 로드 실패: {e}")
    
    def _save(self):
        try:
            with open(self.SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('SettingsManager').warning(f"설정 저장 실패: {e}")
    
    def get(self, key, default=None): return self._settings.get(key, default)
    def set(self, key, value): self._settings[key] = value; self._save()
    def update(self, data): self._settings.update(data); self._save()

class FilterPresetManager:
    def __init__(self):
        self._presets = {}
        from src.config import PRESETS_PATH
        self.PRESETS_PATH = PRESETS_PATH
        self._load()
    
    def _load(self):
        if self.PRESETS_PATH.exists():
            try:
                with open(self.PRESETS_PATH, 'r', encoding='utf-8') as f:
                    self._presets = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                get_logger('FilterPresetManager').warning(f"프리셋 로드 실패: {e}")
    
    def _save(self):
        try:
            with open(self.PRESETS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._presets, f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('FilterPresetManager').warning(f"프리셋 저장 실패: {e}")
            
    def add(self, name, config): self._presets[name] = config; self._save(); return True
    def get(self, name): return self._presets.get(name)
    def delete(self, name):
        if name in self._presets: del self._presets[name]; self._save(); return True
        return False
    def get_all_names(self): return list(self._presets.keys())

from src.utils.helpers import DateTimeHelper

class SearchHistoryManager:
    """최근 검색 기록 관리"""
    def __init__(self, max_items=20):
        self.max_items = max_items
        self._history = []
        from src.config import HISTORY_PATH
        self.HISTORY_PATH = HISTORY_PATH
        self._load()
    
    def _load(self):
        if self.HISTORY_PATH.exists():
            try:
                with open(self.HISTORY_PATH, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                get_logger('SearchHistoryManager').warning(f"검색 기록 로드 실패: {e}")
    
    def _save(self):
        try:
            with open(self.HISTORY_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._history[:self.max_items], f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('SearchHistoryManager').warning(f"검색 기록 저장 실패: {e}")
    
    def add(self, search_info):
        """검색 기록 추가"""
        search_info['timestamp'] = DateTimeHelper.now_string()
        # 중복 제거
        self._history = [h for h in self._history if h.get('complexes') != search_info.get('complexes')]
        self._history.insert(0, search_info)
        self._history = self._history[:self.max_items]
        self._save()
    
    def get_recent(self, count=10):
        return self._history[:count]
    
    def clear(self):
        self._history = []
        self._save()


class CrawlStateManager:
    """크롤링 진행 상태 영속화 (v13.1 - 재시작 시 이어서 진행)"""
    
    def __init__(self):
        from src.config import CRAWL_STATE_PATH
        self.STATE_PATH = CRAWL_STATE_PATH
        self._logger = get_logger('CrawlStateManager')
        self._state = {}
        self._lock = Lock()
        self._load()
    
    def _load(self):
        """저장된 상태 로드"""
        if self.STATE_PATH.exists():
            try:
                with open(self.STATE_PATH, 'r', encoding='utf-8') as f:
                    self._state = json.load(f)
                    self._logger.info(f"이전 크롤링 상태 발견: {len(self._state.get('completed', []))}개 완료됨")
            except (OSError, json.JSONDecodeError) as e:
                self._logger.warning(f"상태 로드 실패: {e}")
                self._state = {}
    
    def _save(self):
        """현재 상태 저장"""
        try:
            self.STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.STATE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self._logger.warning(f"상태 저장 실패: {e}")
    
    def start_session(self, targets: list, trade_types: list):
        """새 크롤링 세션 시작"""
        with self._lock:
            self._state = {
                'started_at': DateTimeHelper.now_string(),
                'targets': targets,  # [(name, cid), ...]
                'trade_types': trade_types,
                'completed': [],  # [(name, cid, ttype), ...]
                'collected_data': [],
                'is_complete': False
            }
            self._save()
            self._logger.info(f"크롤링 세션 시작: {len(targets)}개 대상, {trade_types}")
    
    def mark_completed(self, name: str, cid: str, ttype: str, items: list):
        """단지-거래유형 완료 표시"""
        with self._lock:
            self._state.setdefault('completed', []).append((name, cid, ttype))
            self._state.setdefault('collected_data', []).extend(items)
            self._save()
    
    def finish_session(self):
        """세션 완료 표시 및 상태 초기화"""
        with self._lock:
            self._state['is_complete'] = True
            self._state['finished_at'] = DateTimeHelper.now_string()
            self._save()
            self._logger.info("크롤링 세션 완료")
    
    def get_remaining_targets(self) -> list:
        """미완료 대상 목록 반환"""
        with self._lock:
            if not self._state or self._state.get('is_complete', True):
                return []
            
            all_targets = self._state.get('targets', [])
            trade_types = self._state.get('trade_types', [])
            completed = set(tuple(c) for c in self._state.get('completed', []))
            
            remaining = []
            for name, cid in all_targets:
                for ttype in trade_types:
                    if (name, cid, ttype) not in completed:
                        remaining.append((name, cid, ttype))
            return remaining
    
    def has_incomplete_session(self) -> bool:
        """미완료 세션 존재 여부"""
        with self._lock:
            return bool(self._state) and not self._state.get('is_complete', True)
    
    def get_collected_data(self) -> list:
        """이전에 수집된 데이터 반환"""
        with self._lock:
            return self._state.get('collected_data', [])
    
    def clear(self):
        """상태 초기화"""
        with self._lock:
            self._state = {}
            if self.STATE_PATH.exists():
                try:
                    self.STATE_PATH.unlink()
                except OSError:
                    pass


# Singleton instances
settings = SettingsManager()
crawl_state = CrawlStateManager()

