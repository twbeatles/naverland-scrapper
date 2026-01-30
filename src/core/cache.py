import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from threading import Lock
from src.utils.paths import CACHE_PATH
from src.utils.logger import get_logger

class CrawlCache:
    """크롤링 결과 캐시 (v12.0)"""
    
    def __init__(self, ttl_minutes: int = 30):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: Dict[str, dict] = {}
        self._lock = Lock()
        self._load()
    
    def _get_key(self, complex_id: str, trade_type: str) -> str:
        """캐시 키 생성"""
        return f"{complex_id}_{trade_type}"
    
    def _load(self):
        """캐시 파일 로드"""
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 만료된 항목 필터링
                    now = datetime.now()
                    for key, entry in data.items():
                        try:
                            cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                            if now - cached_at < self.ttl:
                                self._cache[key] = entry
                        except (ValueError, TypeError):
                            continue
            except (OSError, json.JSONDecodeError) as e:
                get_logger('CrawlCache').warning(f"캐시 로드 실패: {e}")
    
    def _save(self):
        """캐시 파일 저장"""
        try:
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except OSError as e:
            get_logger('CrawlCache').warning(f"캐시 저장 실패: {e}")
    
    def get(self, complex_id: str, trade_type: str) -> Optional[List[dict]]:
        """캐시된 결과 반환 (유효한 경우)"""
        with self._lock:
            key = self._get_key(complex_id, trade_type)
            entry = self._cache.get(key)
            if not entry:
                return None
            
            try:
                cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                if datetime.now() - cached_at < self.ttl:
                    get_logger('CrawlCache').debug(f"캐시 히트: {complex_id} ({trade_type})")
                    return entry.get('items', [])
                else:
                    # 만료된 캐시 삭제
                    del self._cache[key]
                    return None
            except (ValueError, TypeError):
                return None
    
    def set(self, complex_id: str, trade_type: str, items: List[dict]):
        """결과 캐시"""
        with self._lock:
            key = self._get_key(complex_id, trade_type)
            self._cache[key] = {
                'cached_at': datetime.now().isoformat(),
                'items': items
            }
            self._save()
            get_logger('CrawlCache').debug(f"캐시 저장: {complex_id} ({trade_type}) - {len(items)}건")
    
    def clear(self):
        """전체 캐시 삭제"""
        with self._lock:
            self._cache = {}
            if CACHE_PATH.exists():
                try:
                    CACHE_PATH.unlink()
                except OSError as e:
                    get_logger('CrawlCache').debug(f"캐시 파일 삭제 실패 (무시): {e}")
            get_logger('CrawlCache').info("캐시 전체 삭제")
    
    def get_stats(self) -> dict:
        """캐시 통계"""
        return {
            'total_entries': len(self._cache),
            'ttl_minutes': self.ttl.total_seconds() / 60
        }
