import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from threading import Lock
from pathlib import Path
from src.config import CACHE_PATH
from src.utils.logger import get_logger

class CrawlCache:
    """크롤링 결과 캐시 (v13.1 - 원자적 저장, 백업 지원)"""
    
    def __init__(self, ttl_minutes: int = 30):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._cache: Dict[str, dict] = {}
        self._lock = Lock()
        self._backup_path = CACHE_PATH.parent / "crawl_cache.backup.json"
        self._load()
    
    def _get_key(self, complex_id: str, trade_type: str) -> str:
        """캐시 키 생성"""
        return f"{complex_id}_{trade_type}"
    
    def _load(self):
        """캐시 파일 로드 (백업에서 복구 지원)"""
        logger = get_logger('CrawlCache')
        
        # 메인 캐시 파일 시도
        loaded = self._try_load_file(CACHE_PATH)
        
        # 메인 실패 시 백업에서 복구 시도
        if not loaded and self._backup_path.exists():
            logger.warning("메인 캐시 손상됨, 백업에서 복구 시도...")
            loaded = self._try_load_file(self._backup_path)
            if loaded:
                logger.info("백업에서 캐시 복구 성공")
                self._save()  # 복구된 캐시를 메인에 저장
    
    def _try_load_file(self, path: Path) -> bool:
        """파일에서 캐시 로드 시도"""
        if not path.exists():
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                now = datetime.now()
                for key, entry in data.items():
                    try:
                        cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                        if now - cached_at < self.ttl:
                            self._cache[key] = entry
                    except (ValueError, TypeError):
                        continue
            return True
        except (OSError, json.JSONDecodeError) as e:
            get_logger('CrawlCache').warning(f"캐시 로드 실패 ({path}): {e}")
            return False
    
    def _save(self):
        """캐시 파일 저장 (원자적 저장 - 임시 파일 + 교체)"""
        logger = get_logger('CrawlCache')
        try:
            # 1. 기존 파일이 있으면 백업
            if CACHE_PATH.exists():
                try:
                    shutil.copy2(CACHE_PATH, self._backup_path)
                except Exception as e:
                    logger.debug(f"백업 생성 실패 (무시): {e}")
            
            # 2. 임시 파일에 먼저 저장
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                suffix='.json',
                prefix='cache_',
                dir=CACHE_PATH.parent
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
                
                # 3. 원자적 교체 (os.replace는 Windows/Linux 모두에서 원자적)
                os.replace(temp_path, str(CACHE_PATH))
            except Exception:
                # 실패 시 임시 파일 정리
                try:
                    Path(temp_path).unlink()
                except:
                    pass
                raise
                
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
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
                    # 만료된 캐시 삭제 후 파일에 동기화
                    del self._cache[key]
                    self._save()
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
                except OSError:
                    pass
            get_logger('CrawlCache').info("캐시 전체 삭제")
    
    def get_stats(self) -> dict:
        """캐시 통계"""
        return {
            'total_entries': len(self._cache),
            'ttl_minutes': self.ttl.total_seconds() / 60
        }
