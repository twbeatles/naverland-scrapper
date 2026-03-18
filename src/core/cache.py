import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from threading import Lock
from src.utils.paths import CACHE_PATH
from src.utils.logger import get_logger
from src.utils.json_store import atomic_write_json, load_json_with_recovery

class CrawlCache:
    """크롤링 결과 캐시 (v12.0)"""
    
    def __init__(
        self,
        ttl_minutes: int = 30,
        write_back_interval_sec: int = 2,
        max_entries: int = 2000,
    ):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.write_back_interval_sec = max(1, int(write_back_interval_sec))
        self.max_entries = max(100, int(max_entries))
        self._cache: Dict[str, dict] = {}
        self._lock = Lock()
        self._dirty = False
        self._last_flush_at = datetime.now()
        self._load()
    
    @staticmethod
    def _normalize_float_token(value) -> str:
        try:
            return f"{float(value):.5f}"
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _normalize_int_token(value) -> str:
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return ""

    def _context_namespace(
        self,
        *,
        mode: str = "",
        asset_type: str = "",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        marker_id: str = "",
    ) -> str:
        parts = []
        mode_token = str(mode or "").strip().lower()
        asset_token = str(asset_type or "").strip().upper()
        lat_token = self._normalize_float_token(source_lat)
        lon_token = self._normalize_float_token(source_lon)
        zoom_token = self._normalize_int_token(source_zoom)
        marker_token = str(marker_id or "").strip()

        if mode_token:
            parts.append(f"mode={mode_token}")
        if asset_token:
            parts.append(f"asset={asset_token}")
        if lat_token:
            parts.append(f"lat={lat_token}")
        if lon_token:
            parts.append(f"lon={lon_token}")
        if zoom_token:
            parts.append(f"zoom={zoom_token}")
        if marker_token:
            parts.append(f"marker={marker_token}")
        return "|".join(parts)

    def _get_key(
        self,
        complex_id: str,
        trade_type: str,
        *,
        mode: str = "",
        asset_type: str = "",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        marker_id: str = "",
    ) -> str:
        """캐시 키 생성 (기본 키 + 컨텍스트 네임스페이스)"""
        base = f"{complex_id}_{trade_type}"
        context_ns = self._context_namespace(
            mode=mode,
            asset_type=asset_type,
            source_lat=source_lat,
            source_lon=source_lon,
            source_zoom=source_zoom,
            marker_id=marker_id,
        )
        if not context_ns:
            return base
        return f"{base}__ctx__{context_ns}"

    def _entry_ttl(self, entry: dict) -> timedelta:
        try:
            ttl_seconds = int(entry.get("ttl_seconds", 0) or 0)
        except (TypeError, ValueError):
            ttl_seconds = 0
        if ttl_seconds > 0:
            return timedelta(seconds=ttl_seconds)
        return self.ttl
    
    def _load(self):
        """캐시 파일 로드"""
        data = load_json_with_recovery(
            CACHE_PATH,
            default_factory=dict,
            logger_name="CrawlCache",
            label="crawl_cache",
        )
        if isinstance(data, dict):
            now = datetime.now()
            for key, entry in data.items():
                try:
                    cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                    has_payload = isinstance(entry.get("raw_items"), list) or isinstance(
                        entry.get("items"), list
                    )
                    if now - cached_at < self._entry_ttl(entry) and has_payload:
                        self._cache[key] = entry
                except (ValueError, TypeError):
                    continue
        self._evict_if_needed()
    
    def _save(self):
        """캐시 파일 저장"""
        try:
            atomic_write_json(CACHE_PATH, self._cache)
            self._dirty = False
            self._last_flush_at = datetime.now()
        except OSError as e:
            get_logger('CrawlCache').warning(f"캐시 저장 실패: {e}")

    def _evict_if_needed(self):
        """최대 엔트리 수를 초과하면 오래된 항목부터 제거"""
        over = len(self._cache) - self.max_entries
        if over <= 0:
            return

        def _cache_time(entry: dict):
            try:
                return datetime.fromisoformat(entry.get("cached_at", ""))
            except (ValueError, TypeError):
                return datetime.min

        sorted_keys = sorted(self._cache.keys(), key=lambda k: _cache_time(self._cache.get(k, {})))
        for key in sorted_keys[:over]:
            self._cache.pop(key, None)

    def _flush_if_needed(self):
        if not self._dirty:
            return
        now = datetime.now()
        if (now - self._last_flush_at).total_seconds() >= self.write_back_interval_sec:
            self._save()

    def get(
        self,
        complex_id: str,
        trade_type: str,
        *,
        mode: str = "",
        asset_type: str = "",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        marker_id: str = "",
    ) -> Optional[List[dict]]:
        """캐시된 결과 반환 (유효한 경우)"""
        with self._lock:
            context_ns = self._context_namespace(
                mode=mode,
                asset_type=asset_type,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
            )
            key = self._get_key(
                complex_id,
                trade_type,
                mode=mode,
                asset_type=asset_type,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
            )
            entry = self._cache.get(key)
            # 레거시 호환: 무컨텍스트 조회 경로에서만 legacy 기본 키를 읽는다.
            if entry is None and not context_ns:
                legacy_key = f"{complex_id}_{trade_type}"
                if legacy_key != key:
                    entry = self._cache.get(legacy_key)
                    key = legacy_key
            if not entry:
                return None
            
            try:
                cached_at = datetime.fromisoformat(entry.get('cached_at', ''))
                if datetime.now() - cached_at < self._entry_ttl(entry):
                    suffix = f", context={context_ns}" if context_ns else ""
                    get_logger('CrawlCache').debug(f"캐시 히트: {complex_id} ({trade_type}{suffix})")
                    # v14.2: raw_items 우선 사용, legacy items 포맷과 호환 유지
                    raw_items = entry.get("raw_items")
                    if isinstance(raw_items, list):
                        return raw_items
                    legacy_items = entry.get("items")
                    if isinstance(legacy_items, list):
                        return legacy_items
                    return []
                else:
                    # 만료된 캐시 삭제
                    del self._cache[key]
                    self._dirty = True
                    self._flush_if_needed()
                    return None
            except (ValueError, TypeError):
                return None
    
    def set(
        self,
        complex_id: str,
        trade_type: str,
        raw_items: List[dict],
        ttl_seconds: Optional[int] = None,
        reason: str = "",
        *,
        mode: str = "",
        asset_type: str = "",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        marker_id: str = "",
    ):
        """결과 캐시"""
        with self._lock:
            context_ns = self._context_namespace(
                mode=mode,
                asset_type=asset_type,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
            )
            key = self._get_key(
                complex_id,
                trade_type,
                mode=mode,
                asset_type=asset_type,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
            )
            payload = {
                'cached_at': datetime.now().isoformat(),
                'raw_items': list(raw_items),
            }
            if context_ns:
                payload["context"] = context_ns
            try:
                ttl = int(ttl_seconds or 0)
            except (TypeError, ValueError):
                ttl = 0
            if ttl > 0:
                payload["ttl_seconds"] = ttl
            reason_token = str(reason or "").strip()
            if reason_token:
                payload["reason"] = reason_token
            self._cache[key] = payload
            self._evict_if_needed()
            self._dirty = True
            self._flush_if_needed()
            suffix = f", context={context_ns}" if context_ns else ""
            get_logger('CrawlCache').debug(
                f"캐시 저장: {complex_id} ({trade_type}{suffix}) - {len(raw_items)}건"
            )

    def flush(self):
        """dirty 상태가 있으면 즉시 파일에 반영"""
        with self._lock:
            if self._dirty:
                self._save()
    
    def clear(self):
        """전체 캐시 삭제"""
        with self._lock:
            self._cache = {}
            self._dirty = False
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
            'ttl_minutes': self.ttl.total_seconds() / 60,
            'dirty': self._dirty,
            'write_back_interval_sec': self.write_back_interval_sec,
            'max_entries': self.max_entries,
        }
