import time
import random
import gc
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from src.utils.constants import CRAWL_SPEED_PRESETS
from src.utils.helpers import PriceConverter, ChromeParamHelper
from src.utils.retry_handler import RetryCancelledError, RetryHandler
from src.core.engines import PlaywrightCrawlerEngine, SeleniumCrawlerEngine
from src.core.item_parser import ItemParser
from src.core.models.crawl_models import GeoSweepConfig

# 메모리 임계치 (MB) - 초과 시 드라이버 재시작
MEMORY_THRESHOLD_MB = 500

class CrawlerThread(QThread):
    log_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str, int)  # percent, current_name, remaining_seconds
    item_signal = pyqtSignal(dict)  # deprecated: items_signal(list[dict]) 사용 권장
    items_signal = pyqtSignal(list)
    stats_signal = pyqtSignal(dict)
    complex_finished_signal = pyqtSignal(str, str, str, int)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    alert_triggered_signal = pyqtSignal(str, str, str, float, int)
    discovered_complex_signal = pyqtSignal(dict)
    BLOCKED_PAGE_PATTERNS = (
        "captcha",
        "캡차",
        "자동입력 방지",
        "자동 입력 방지",
        "접근이 제한",
        "접속이 제한",
        "비정상적인 접근",
        "서비스 이용이 제한",
        "verify you are human",
        "robot check",
        "access denied",
        "security check",
        "cloudflare",
        "bot detection",
    )
    
    def __init__(
        self,
        targets,
        trade_types,
        area_filter,
        price_filter,
        db,
        speed="보통",
        cache=None,
        ui_batch_interval_ms=120,
        ui_batch_size=30,
        emit_legacy_item_signal=False,
        max_retry_count=3,
        show_new_badge=True,
        show_price_change=True,
        price_change_threshold=0,
        track_disappeared=True,
        history_batch_size=200,
        negative_cache_ttl_minutes=5,
        engine_name="playwright",
        crawl_mode="complex",
        geo_config=None,
        fallback_engine_enabled=True,
        playwright_headless=False,
        playwright_detail_workers=12,
        block_heavy_resources=True,
        playwright_response_drain_timeout_ms=3000,
    ):
        super().__init__()
        self.targets = targets
        self.trade_types = trade_types
        self.area_filter = area_filter
        self.price_filter = price_filter
        self.db = db
        self.speed = speed
        self.cache = cache  # v12.0: CrawlCache 인스턴스
        self._running = True
        self.collected_data = []
        self.pending_items = []
        self.stats = {
            "total_found": 0,
            "filtered_out": 0,
            "cache_hits": 0,
            "new_count": 0,
            "price_up": 0,
            "price_down": 0,
            "geo_discovered_count": 0,
            "geo_dedup_count": 0,
            "response_drain_wait_count": 0,
            "response_drain_timeout_count": 0,
            "by_trade_type": {"매매": 0, "전세": 0, "월세": 0},
        }
        self.start_time = None
        self.items_per_second = 0
        try:
            retries = max(0, int(max_retry_count))
        except (TypeError, ValueError):
            retries = 3
        self.retry_handler = RetryHandler(max_retries=retries)
        self._shutdown_mode = False
        self.ui_batch_interval_ms = max(20, int(ui_batch_interval_ms))
        self.ui_batch_size = max(1, int(ui_batch_size))
        self.emit_legacy_item_signal = bool(emit_legacy_item_signal)
        self.show_new_badge = bool(show_new_badge)
        self.show_price_change = bool(show_price_change)
        try:
            self.price_change_threshold = max(0, int(price_change_threshold))
        except (TypeError, ValueError):
            self.price_change_threshold = 0
        self.track_disappeared = bool(track_disappeared)
        try:
            self.history_batch_size = max(20, int(history_batch_size))
        except (TypeError, ValueError):
            self.history_batch_size = 200
        try:
            self.negative_cache_ttl_minutes = max(0, int(negative_cache_ttl_minutes))
        except (TypeError, ValueError):
            self.negative_cache_ttl_minutes = 5
        self.engine_name = str(engine_name or "playwright").strip().lower()
        self.crawl_mode = str(crawl_mode or "complex").strip().lower()
        if isinstance(geo_config, GeoSweepConfig):
            self.geo_config = geo_config
        elif isinstance(geo_config, dict) and geo_config:
            try:
                self.geo_config = GeoSweepConfig(**geo_config)
            except TypeError:
                self.geo_config = None
        else:
            self.geo_config = None
        self.fallback_engine_enabled = bool(fallback_engine_enabled)
        self.playwright_headless = bool(playwright_headless)
        try:
            self.playwright_detail_workers = max(1, int(playwright_detail_workers))
        except (TypeError, ValueError):
            self.playwright_detail_workers = 12
        self.block_heavy_resources = bool(block_heavy_resources)
        try:
            self.playwright_response_drain_timeout_ms = max(100, int(playwright_response_drain_timeout_ms))
        except (TypeError, ValueError):
            self.playwright_response_drain_timeout_ms = 3000
        self._engine = None
        self._last_batch_flush_at = time.monotonic()
        self._history_state_cache = {}
        self._alert_rules_cache = {}
        self._pending_history_rows = []
        self._db_write_disabled_notified = False
        self._registered_discovered_complex_keys = set()
        self._discovered_complex_status = {}
    
    def stop(self):
        self._running = False
        try:
            self.requestInterruption()
        except Exception:
            pass

    def set_shutdown_mode(self, enabled: bool = True):
        self._shutdown_mode = bool(enabled)
        if self._shutdown_mode:
            self.retry_handler.max_retries = 0

    def _should_stop(self) -> bool:
        return (not self._running) or bool(self.isInterruptionRequested())

    def _sleep_interruptible(self, seconds: float, chunk_seconds: float = 0.2) -> bool:
        remaining = max(0.0, float(seconds or 0.0))
        chunk = min(0.2, max(0.05, float(chunk_seconds or 0.2)))
        while remaining > 0:
            if self._should_stop():
                return False
            step = chunk if remaining > chunk else remaining
            time.sleep(step)
            remaining -= step
        return True

    def _create_engine(self):
        if self.engine_name == "selenium":
            return SeleniumCrawlerEngine(self)
        return PlaywrightCrawlerEngine(self)

    def _estimate_remaining_seconds(self, current: int, total: int) -> int:
        elapsed = time.time() - self.start_time if self.start_time else 0.0
        avg_time = elapsed / current if current > 0 else 5
        return int(avg_time * max(0, total - current))

    def _get_speed_delay(self) -> float:
        speed_cfg = CRAWL_SPEED_PRESETS.get(self.speed, CRAWL_SPEED_PRESETS["보통"])
        return random.uniform(speed_cfg["min"], speed_cfg["max"])

    def register_discovered_complex(self, payload: dict):
        if not isinstance(payload, dict):
            return
        cid = str(payload.get("complex_id", "") or "")
        asset_type = str(payload.get("asset_type", "APT") or "APT").upper()
        name = str(payload.get("complex_name", "") or "")
        if not cid or not name:
            return
        dedupe_key = f"{asset_type}:{cid}"
        status = self._discovered_complex_status.get(dedupe_key, "skipped")
        if dedupe_key not in self._registered_discovered_complex_keys:
            self._registered_discovered_complex_keys.add(dedupe_key)
            if self.db:
                try:
                    status = str(self.db.add_complex(name, cid, return_status=True) or "skipped")
                except Exception as e:
                    self.log(f"⚠️ 발견 단지 자동 등록 실패: {name} ({cid}) - {e}", 30)
                    status = "error"
            self._discovered_complex_status[dedupe_key] = status
        emitted = dict(payload)
        emitted["db_status"] = status
        self.discovered_complex_signal.emit(emitted)

    def record_crawl_history(
        self,
        name,
        cid,
        types,
        count,
        *,
        engine="",
        mode="complex",
        source_lat=None,
        source_lon=None,
        source_zoom=None,
        asset_type="",
    ):
        if not self.db:
            return
        try:
            self.db.add_crawl_history(
                name,
                cid,
                types,
                int(count or 0),
                engine=engine or self.engine_name,
                mode=mode or self.crawl_mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                asset_type=asset_type,
            )
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
        except Exception as e:
            self.log(f"⚠️ 크롤링 기록 저장 실패: {e}", 30)

    def _finalize_disappeared_articles(self, processed_target_pairs):
        if self.track_disappeared and (not self._should_stop()) and self.db:
            try:
                if processed_target_pairs and hasattr(self.db, "mark_disappeared_articles_for_targets"):
                    disappeared = int(
                        self.db.mark_disappeared_articles_for_targets(
                            list(sorted(processed_target_pairs))
                        )
                        or 0
                    )
                else:
                    disappeared = int(self.db.mark_disappeared_articles() or 0)
                if disappeared > 0:
                    self.log(f"🗑️ 소멸 매물 {disappeared}건 처리")
            except Exception as e:
                if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                    self._notify_db_write_disabled()
                self.log(f"⚠️ 소멸 매물 처리 실패: {e}", 30)

    def _process_raw_items(self, raw_items, requested_trade_type):
        matched_count = 0
        for raw_item in raw_items or []:
            if not isinstance(raw_item, dict):
                continue
            processed_item = self._enrich_item_with_history_and_alerts(dict(raw_item))
            trade_type = str(processed_item.get("거래유형", requested_trade_type) or requested_trade_type)
            if self._check_filters(processed_item, trade_type):
                self._push_item(processed_item)
                matched_count += 1
            else:
                self.stats["filtered_out"] += 1
        self._flush_history_updates(force=True)
        self._flush_pending_items_if_needed(force=True)
        return matched_count

    def _run_fallback_selenium(self, start_name="", start_cid="", start_trade=""):
        original_engine = self.engine_name
        try:
            self.engine_name = "selenium"
            if start_name and start_cid and start_trade:
                prefixed_targets = [(start_name, start_cid)] + [
                    target for target in self.targets if not (target[0] == start_name and target[1] == start_cid)
                ]
                self.targets = prefixed_targets
                prefixed_trades = [start_trade] + [tt for tt in self.trade_types if tt != start_trade]
                self.trade_types = prefixed_trades
            SeleniumCrawlerEngine(self).run()
        finally:
            self.engine_name = original_engine

    def log(self, msg, level=20): self.log_signal.emit(msg, level)

    def _push_item(self, item):
        self.collected_data.append(item)
        self.pending_items.append(item)
        self.stats["total_found"] += 1
        if self.emit_legacy_item_signal:
            self.item_signal.emit(item)
        self._flush_pending_items_if_needed()

    def _flush_pending_items_if_needed(self, force=False):
        if not self.pending_items:
            return
        elapsed_ms = (time.monotonic() - self._last_batch_flush_at) * 1000
        if force or len(self.pending_items) >= self.ui_batch_size or elapsed_ms >= self.ui_batch_interval_ms:
            batch = list(self.pending_items)
            self.pending_items.clear()
            self.items_signal.emit(batch)
            self.emit_stats()
            self._last_batch_flush_at = time.monotonic()

    def _build_stats_payload(self) -> dict:
        return {
            "total_found": self.stats.get("total_found", 0),
            "filtered_out": self.stats.get("filtered_out", 0),
            "cache_hits": self.stats.get("cache_hits", 0),
            "new_count": self.stats.get("new_count", 0),
            "price_up": self.stats.get("price_up", 0),
            "price_down": self.stats.get("price_down", 0),
            "geo_discovered_count": self.stats.get("geo_discovered_count", 0),
            "geo_dedup_count": self.stats.get("geo_dedup_count", 0),
            "response_drain_wait_count": self.stats.get("response_drain_wait_count", 0),
            "response_drain_timeout_count": self.stats.get("response_drain_timeout_count", 0),
            "by_trade_type": dict(self.stats.get("by_trade_type", {})),
        }

    def emit_stats(self):
        self.stats_signal.emit(self._build_stats_payload())

    @staticmethod
    def _row_get(row, key, default=None):
        if row is None:
            return default
        try:
            if isinstance(row, dict):
                return row.get(key, default)
            return row[key]
        except Exception:
            return default

    def _cache_key(self, complex_id, trade_type):
        return (str(complex_id or ""), str(trade_type or ""))

    def _get_history_state_map(self, complex_id, trade_type):
        key = (str(complex_id or ""), "*")
        if key in self._history_state_cache:
            return self._history_state_cache[key]
        history_map = {}
        if self.db and complex_id:
            try:
                history_map = self.db.get_article_history_state_bulk(complex_id)
            except Exception as e:
                self.log(f"   ⚠️ 이력 상태 로드 실패: {e}", 30)
        self._history_state_cache[key] = history_map or {}
        return self._history_state_cache[key]

    def _get_alert_rules(self, complex_id, trade_type):
        key = self._cache_key(complex_id, trade_type)
        if key in self._alert_rules_cache:
            return self._alert_rules_cache[key]
        rules = []
        if self.db and complex_id and trade_type:
            try:
                rules = self.db.get_enabled_alert_rules(complex_id, trade_type)
            except Exception as e:
                self.log(f"   ⚠️ 알림 룰 로드 실패: {e}", 30)
        self._alert_rules_cache[key] = rules or []
        return self._alert_rules_cache[key]

    def _flush_history_updates_fallback(self, rows):
        if not self.db:
            return 0
        if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
            self._notify_db_write_disabled()
            return 0
        saved = 0
        for row in rows:
            try:
                ok = self.db.update_article_history(
                    article_id=row.get("article_id", ""),
                    complex_id=row.get("complex_id", ""),
                    complex_name=row.get("complex_name", ""),
                    trade_type=row.get("trade_type", ""),
                    price=int(row.get("price", 0) or 0),
                    price_text=row.get("price_text", ""),
                    area=float(row.get("area", 0) or 0),
                    floor=row.get("floor", ""),
                    feature=row.get("feature", ""),
                    extra=row,
                )
                if ok:
                    saved += 1
            except Exception:
                continue
        return saved

    def _notify_db_write_disabled(self):
        if self._db_write_disabled_notified:
            return
        self._db_write_disabled_notified = True
        reason = ""
        if self.db and hasattr(self.db, "get_write_disabled_reason"):
            try:
                reason = str(self.db.get_write_disabled_reason() or "")
            except Exception:
                reason = ""
        suffix = f" ({reason})" if reason else ""
        self.log(
            f"⚠️ DB 쓰기 기능이 비활성화되었습니다{suffix}. 수집은 계속되지만 이력/기록 저장이 제한됩니다.",
            40,
        )

    def _flush_history_updates(self, force=False):
        if not self._pending_history_rows:
            return 0
        if not force and len(self._pending_history_rows) < self.history_batch_size:
            return 0
        rows = list(self._pending_history_rows)
        self._pending_history_rows.clear()
        if not self.db:
            return 0
        if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
            self._notify_db_write_disabled()
            return 0

        try:
            saved = int(self.db.upsert_article_history_bulk(rows) or 0)
            if saved == len(rows):
                return saved
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
                return 0
            self.log(
                f"   ⚠️ 이력 일괄 저장 일부 실패 ({saved}/{len(rows)}), 개별 재시도...",
                30,
            )
        except Exception as e:
            if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                self._notify_db_write_disabled()
                return 0
            self.log(f"   ⚠️ 이력 일괄 저장 실패: {e} (개별 재시도)", 30)
        return self._flush_history_updates_fallback(rows)

    def _enrich_item_with_history_and_alerts(self, data):
        if not isinstance(data, dict):
            return data

        trade_type = str(data.get("거래유형", "") or "")
        complex_id = str(data.get("단지ID", "") or "")
        article_id = str(data.get("매물ID", "") or "")
        complex_name = str(data.get("단지명", "") or "")

        if trade_type == "매매":
            price_text = str(data.get("매매가", "") or "")
        else:
            deposit = str(data.get("보증금", "") or "")
            monthly = str(data.get("월세", "") or "")
            price_text = f"{deposit}/{monthly}" if monthly else deposit
        price_int = PriceConverter.to_int(price_text.split("/")[0] if "/" in price_text else price_text)

        area_pyeong = 0.0
        try:
            area_pyeong = float(data.get("면적(평)", 0) or 0)
        except (TypeError, ValueError):
            area_pyeong = 0.0

        is_new = False
        raw_price_change = 0
        if article_id and complex_id and price_int > 0:
            history_map = self._get_history_state_map(complex_id, trade_type)
            prev = history_map.get(article_id)
            prev_price = int(self._row_get(prev, "price", 0) or 0)
            is_new = prev is None
            raw_price_change = 0 if is_new else price_int - prev_price

            history_map[article_id] = {
                "price": price_int,
                "status": "active",
                "last_price": prev_price if prev_price > 0 else price_int,
                "price_change": raw_price_change,
            }

            self._pending_history_rows.append(
                {
                    "article_id": article_id,
                    "complex_id": complex_id,
                    "complex_name": complex_name,
                    "trade_type": trade_type,
                    "price": price_int,
                    "price_text": price_text,
                    "area": area_pyeong,
                    "floor": str(data.get("층/방향", "") or ""),
                    "feature": str(data.get("타입/특징", "") or ""),
                    "last_price": prev_price if prev_price > 0 else price_int,
                    "asset_type": str(data.get("자산유형", "") or ""),
                    "source_mode": str(data.get("수집모드", self.crawl_mode) or self.crawl_mode),
                    "source_lat": float(data.get("위도", 0.0) or 0.0),
                    "source_lon": float(data.get("경도", 0.0) or 0.0),
                    "source_zoom": int(data.get("줌", 0) or 0),
                    "marker_id": str(data.get("마커ID", "") or ""),
                    "broker_office": str(data.get("부동산상호", "") or ""),
                    "broker_name": str(data.get("중개사이름", "") or ""),
                    "broker_phone1": str(data.get("전화1", "") or ""),
                    "broker_phone2": str(data.get("전화2", "") or ""),
                    "prev_jeonse_won": int(data.get("기전세금(원)", 0) or 0),
                    "jeonse_period_years": int(data.get("전세_기간(년)", 0) or 0),
                    "jeonse_max_won": int(data.get("전세_기간내_최고(원)", 0) or 0),
                    "jeonse_min_won": int(data.get("전세_기간내_최저(원)", 0) or 0),
                    "gap_amount_won": int(data.get("갭금액(원)", 0) or 0),
                    "gap_ratio": float(data.get("갭비율", 0.0) or 0.0),
                }
            )
            self._flush_history_updates(force=False)

        price_change = int(raw_price_change)
        if self.price_change_threshold > 0 and abs(price_change) < self.price_change_threshold:
            price_change = 0
        if is_new:
            self.stats["new_count"] = int(self.stats.get("new_count", 0)) + 1
        if price_change > 0:
            self.stats["price_up"] = int(self.stats.get("price_up", 0)) + 1
        elif price_change < 0:
            self.stats["price_down"] = int(self.stats.get("price_down", 0)) + 1

        visible_is_new = bool(is_new) if self.show_new_badge else False
        visible_price_change = int(price_change) if self.show_price_change else 0

        data["is_new"] = visible_is_new
        data["신규여부"] = visible_is_new
        data["price_change"] = visible_price_change
        data["가격변동"] = visible_price_change

        if complex_id and trade_type and area_pyeong > 0 and price_int > 0:
            rules = self._get_alert_rules(complex_id, trade_type)
            for rule in rules:
                area_min = float(self._row_get(rule, "area_min", 0) or 0)
                area_max = float(self._row_get(rule, "area_max", 999999) or 999999)
                price_min = int(self._row_get(rule, "price_min", 0) or 0)
                price_max = int(self._row_get(rule, "price_max", 999999999) or 999999999)
                if not (area_min <= area_pyeong <= area_max):
                    continue
                if not (price_min <= price_int <= price_max):
                    continue
                alert_id = int(self._row_get(rule, "id", 0) or 0)
                alert_name = str(self._row_get(rule, "complex_name", complex_name) or complex_name)
                should_emit = True
                if alert_id > 0 and article_id:
                    if hasattr(self.db, "is_write_disabled") and self.db.is_write_disabled():
                        should_emit = True
                    else:
                        try:
                            should_emit = bool(
                                self.db.record_alert_notification(
                                    alert_id=alert_id,
                                    article_id=article_id,
                                    complex_id=complex_id,
                                )
                            )
                        except Exception as e:
                            should_emit = True
                            self.log(f"   ⚠️ 알림 dedup 기록 실패 (emit 유지): {e}", 30)
                elif alert_id > 0 and not article_id:
                    self.log("   ℹ️ 매물ID 없음: 알림 dedup 생략", 10)

                if not should_emit:
                    continue
                self.alert_triggered_signal.emit(
                    alert_name,
                    trade_type,
                    price_text,
                    float(area_pyeong),
                    alert_id,
                )

        return data
    
    def _init_driver(self):
        """Chrome 드라이버 초기화 및 설정"""
        
        # Chrome 버전 자동 감지
        detected_version = ChromeParamHelper.get_chrome_major_version()
        version_msg = f" (감지된 버전: {detected_version})" if detected_version else " (버전 자동 감지)"
        self.log(f"🔧 Chrome 드라이버 초기화 중...{version_msg}")
        
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        options.add_argument("--log-level=3")
        
        driver = None
        try:
            # 감지된 버전이 있으면 해당 버전 사용, 없으면 None (최신/자동)
            driver = uc.Chrome(options=options, version_main=detected_version)
            self.log("✅ Chrome 드라이버 초기화 성공")
        except Exception as e:
            self.log(f"⚠️ Headless 실패, 일반 모드 시도... ({e})", 30)
            options2 = uc.ChromeOptions()
            options2.add_argument("--no-sandbox")
            options2.add_argument("--disable-dev-shm-usage")
            options2.add_argument("--disable-gpu")
            options2.add_argument("--window-size=1920,1080")
            options2.add_argument("--start-minimized")
            driver = uc.Chrome(options=options2, version_main=detected_version)
            self.log("✅ Chrome 드라이버 초기화 성공 (일반 모드)")
        
        if driver:
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(5)
            
        return driver

    def run(self):
        self.start_time = time.time()
        self._engine = None
        try:
            self.log("🚀 크롤링 시작...")
            self._engine = self._create_engine()
            self._engine.run()
            self._flush_pending_items_if_needed(force=True)
            self._flush_history_updates(force=True)
            self.log(f"\n{'='*50}\n✅ 완료! 총 {len(self.collected_data)}건")
        except RetryCancelledError:
            self.log("⏹ 중단 요청으로 크롤링을 종료했습니다.", 20)
        except Exception as e:
            self.log(f"❌ 치명적 오류: {e}", 40)
            self.log(f"상세:\n{traceback.format_exc()}", 40)
            self.error_signal.emit(str(e))
        finally:
            self._flush_pending_items_if_needed(force=True)
            self._flush_history_updates(force=True)
            if self._engine is not None:
                try:
                    self._engine.close()
                except Exception as e:
                    self.log(f"⚠️ 엔진 종료 중 오류: {e}", 30)
            self.finished_signal.emit(self.collected_data)

    def _run_selenium_loop(self):
        if not UC_AVAILABLE or not BS4_AVAILABLE:
            self.error_signal.emit("필수 라이브러리 미설치\npip install undetected-chromedriver beautifulsoup4")
            return
            
        driver = None
        
        try:
            driver = self._init_driver()
            if not driver:
                raise Exception("드라이버 초기화 실패")
            
            total = len(self.targets) * len(self.trade_types)
            current = 0
            processed_complexes = 0  # 처리한 단지 수
            processed_target_pairs = set()
            
            for name, cid in self.targets:
                if self._should_stop():
                    break
                
                # v14.0: 메모리 기반 드라이버 재시작 (500MB 임계치)
                should_restart = False
                if PSUTIL_AVAILABLE:
                    memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                    if memory_mb > MEMORY_THRESHOLD_MB:
                        should_restart = True
                        self.log(f"🔄 메모리 사용량 {memory_mb:.0f}MB 초과, 드라이버 재시작...")
                else:
                    # psutil 미설치 시 기존 방식 (3단지마다)
                    if processed_complexes > 0 and processed_complexes % 3 == 0:
                        should_restart = True
                        self.log("🔄 Chrome 드라이버 재시작 (메모리 정리)...")
                
                if should_restart:
                    try:
                        driver.quit()
                    except Exception as e:
                        self.log(f"⚠️ 드라이버 종료 실패 (무시): {e}", 30)
                    driver = None
                    gc.collect()
                    if not self._sleep_interruptible(1.0):
                        break
                    
                    driver = self._init_driver()
                    if not driver:
                        raise Exception("드라이버 재시작 실패")
                
                complex_count = 0
                for ttype in self.trade_types:
                    if self._should_stop():
                        break
                    if cid and ttype:
                        processed_target_pairs.add((str(cid), str(ttype)))
                    current += 1
                    
                    # 예상 남은 시간 계산
                    remaining = self._estimate_remaining_seconds(current, total)

                    self.progress_signal.emit(int(current / total * 100), f"{name} ({ttype})", remaining)
                    self.log(f"\\n📍 [{current}/{total}] {name} - {ttype}")
                    
                    try:
                        batch_result = self._crawl(driver, name, cid, ttype)
                        count = int(batch_result.get("count", 0))
                        complex_count += count
                        self.stats["by_trade_type"][ttype] = self.stats["by_trade_type"].get(ttype, 0) + count
                        self.log(f"   ✅ {count}건 수집")
                    except RetryCancelledError:
                        self.log("   ⏹ 중단 요청으로 현재 작업을 종료합니다.", 20)
                        self.stop()
                        break
                    except Exception as e:
                        self.log(f"   ❌ 오류: {e}", 40)
                        self.log(f"   상세: {traceback.format_exc()}", 40)
                        
                        # 치명적 오류(세션 종료 등) 발생 시 드라이버 재시작 시도
                        if "SessionNotCreatedException" in str(e) or "NoSuchWindowException" in str(e) or "WebDriverException" in str(e):
                             self.log("⚠️ 드라이버 세션 오류 감지, 재시작 시도...", 30)
                             try:
                                 driver.quit()
                             except Exception as quit_err:
                                 self.log(f"⚠️ 드라이버 종료 실패 (무시): {quit_err}", 30)
                             driver = self._init_driver()
                    
                    if not self._sleep_interruptible(self._get_speed_delay()):
                        break

                self._flush_history_updates(force=True)
                self.record_crawl_history(
                    name,
                    cid,
                    ",".join(self.trade_types),
                    int(complex_count),
                    engine="selenium",
                    mode=self.crawl_mode,
                )
                
                self.complex_finished_signal.emit(name, cid, ",".join(self.trade_types), complex_count)
                processed_complexes += 1

            self._finalize_disappeared_articles(processed_target_pairs)
        except RetryCancelledError:
            raise
        except Exception:
            raise
        finally:
            if driver:
                try:
                    driver.quit()
                    self.log("✅ Chrome 드라이버 종료 완료")
                except Exception as e:
                    self.log(f"⚠️ Chrome 드라이버 종료 중 오류: {e}", 30)
    
    def _crawl(self, driver, name, cid, ttype):
        # v12.0: 캐시 확인
        if self.cache:
            cached_items = self.cache.get(
                cid,
                ttype,
                mode=self.crawl_mode,
                asset_type="APT",
            )
            if cached_items is not None:
                self.log(f"   💾 캐시 히트! {len(cached_items)}건 로드")
                self.stats["cache_hits"] = self.stats.get("cache_hits", 0) + 1
                matched_count = 0
                for raw_item in cached_items:
                    if not isinstance(raw_item, dict):
                        continue
                    processed_item = self._enrich_item_with_history_and_alerts(dict(raw_item))
                    if self._check_filters(processed_item, ttype):
                        self._push_item(processed_item)
                        matched_count += 1
                    else:
                        self.stats["filtered_out"] += 1
                self._flush_history_updates(force=True)
                self._flush_pending_items_if_needed(force=True)
                return {"count": matched_count, "cache_hit": True, "raw_count": len(cached_items)}
        
        trade_param = {"매매": "A1", "전세": "B1", "월세": "B2"}.get(ttype, "A1")
        url = f"https://new.land.naver.com/complexes/{cid}?ms=37.5,127,16&a=APT&e=RETAIL&tradeTypes={trade_param}"

        try:
            parse_result = self.retry_handler.execute_with_retry(
                self._crawl_once,
                driver,
                name,
                cid,
                ttype,
                url,
                cancel_checker=self._should_stop,
            )
        except RetryCancelledError:
            raise
        except Exception as e:
            self.log(f"   ❌ {name}({ttype}) 크롤링 실패: {e}", 40)
            raise
        count = int(parse_result.get("count", 0))
        
        # v14.2: 필터 통과 여부와 무관하게 raw_items 캐시 저장
        if self.cache:
            raw_items = parse_result.get("raw_items", [])
            if raw_items:
                self.cache.set(
                    cid,
                    ttype,
                    raw_items,
                    mode=self.crawl_mode,
                    asset_type="APT",
                )
            else:
                negative_ttl_seconds = max(0, int(self.negative_cache_ttl_minutes * 60))
                if negative_ttl_seconds > 0:
                    self.cache.set(
                        cid,
                        ttype,
                        [],
                        ttl_seconds=negative_ttl_seconds,
                        mode=self.crawl_mode,
                        asset_type="APT",
                    )
        
        self._flush_history_updates(force=True)
        self._flush_pending_items_if_needed(force=True)
        return {
            "count": count,
            "cache_hit": False,
            "raw_count": int(parse_result.get("raw_count", 0)),
        }

    def _crawl_once(self, driver, name, cid, ttype, url):
        self.log("   🔗 URL 접속 중...")
        driver.get(url)
        self._assert_not_blocked_page(driver, context="초기 페이지")

        # v14.0: 동적 대기 - 페이지 로드 완료까지 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(("css selector", ".article_list, .item_list, .complex_list, [class*='article']"))
            )
        except TimeoutException:
            self.log("   ⚠️ 매물 리스트 로드 대기 시간 초과, 계속 진행...", 30)
        self._assert_not_blocked_page(driver, context="목록 대기")

        try:
            article_tab = driver.find_element("css selector", "a[href*='articleList'], .tab_item[data-tab='article']")
            article_tab.click()
            # v14.0: 탭 클릭 후 동적 대기
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(("css selector", ".item_article, .item_inner"))
                )
            except TimeoutException:
                self.log("   ℹ️ 매물 탭 로드 대기 시간 초과 (무시)", 10)
        except (NoSuchElementException, Exception) as e:
            # 탭 클릭 실패는 정상적인 상황일 수 있음 (탭이 없는 경우)
            self.log(f"   ℹ️ 매물 탭 찾기 실패 (정상): {type(e).__name__}", 10)

        self._assert_not_blocked_page(driver, context="탭 진입")
        self._scroll(driver)
        self._assert_not_blocked_page(driver, context="스크롤 완료")

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        return self._parse(soup, name, cid, ttype)

    def _detect_block_signal(self, title, page_source):
        title_lower = str(title or "").lower()
        source_lower = str(page_source or "").lower()
        source_head = source_lower[:20000]
        haystack = f"{title_lower}\n{source_head}"
        for pattern in self.BLOCKED_PAGE_PATTERNS:
            if pattern in haystack:
                return pattern
        return None

    def _assert_not_blocked_page(self, driver, context=""):
        try:
            title = driver.title
        except Exception:
            title = ""
        try:
            page_source = driver.page_source
        except Exception:
            page_source = ""

        signal = self._detect_block_signal(title, page_source)
        if signal:
            ctx = f" ({context})" if context else ""
            self.log(f"   ⚠️ 차단/방어 페이지 감지{ctx}: {signal}", 30)
            raise RuntimeError(f"temporary blocked page detected{ctx}: {signal}")

    def _get_item_state(self, driver, selectors):
        script = """
            const selector = arguments[0];
            const nodes = Array.from(document.querySelectorAll(selector));
            const ids = [];
            for (const node of nodes) {
                let id =
                    node.getAttribute('data-article-id') ||
                    node.getAttribute('data-id') ||
                    node.getAttribute('id') ||
                    '';
                if (!id) {
                    const anchor = node.querySelector("a[href*='articleId=']");
                    if (anchor) {
                        const href = anchor.getAttribute('href') || '';
                        const m = href.match(/articleId=(\\d+)/);
                        if (m) {
                            id = m[1];
                        }
                    }
                }
                if (id) {
                    ids.push(String(id));
                }
            }
            return {count: nodes.length, ids: ids};
        """
        try:
            state = driver.execute_script(script, selectors) or {}
        except Exception:
            return 0, set()
        count = int(state.get("count", 0) or 0)
        raw_ids = state.get("ids", [])
        if not isinstance(raw_ids, list):
            raw_ids = []
        return count, {str(x) for x in raw_ids if x is not None}

    def _detect_scroll_container(self, driver):
        script = """
            const candidates = [];
            const seedSelectors = [
                '.article_list',
                '.item_list',
                '.list_contents',
                '[class*="article_list"]',
                '[class*="item_list"]',
                '[class*="ArticleList"]',
                '[class*="List"]'
            ];
            for (const sel of seedSelectors) {
                candidates.push(...Array.from(document.querySelectorAll(sel)));
            }
            if (candidates.length === 0) {
                candidates.push(...Array.from(document.querySelectorAll('div, section, ul')));
            }
            let best = null;
            let bestScroll = 0;
            for (const el of candidates.slice(0, 400)) {
                const style = window.getComputedStyle(el);
                const overflowY = style.overflowY || '';
                if (!(overflowY.includes('auto') || overflowY.includes('scroll'))) {
                    continue;
                }
                const scrollGap = el.scrollHeight - el.clientHeight;
                if (scrollGap > 40 && scrollGap > bestScroll) {
                    best = el;
                    bestScroll = scrollGap;
                }
            }
            window.__naver_scroll_container = best;
            return !!best;
        """
        try:
            return bool(driver.execute_script(script))
        except Exception:
            return False

    def _scroll_once(self, driver, use_container):
        if use_container:
            script = """
                const container = window.__naver_scroll_container;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                    return true;
                }
                return false;
            """
            try:
                if bool(driver.execute_script(script)):
                    return True
            except Exception:
                pass
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        return False
    
    def _scroll(self, driver):
        """v14.2: 내부 컨테이너 우선 + window 폴백 스크롤"""
        try:
            selectors = ".item_article, .item_inner, .article_item, [class*='ArticleItem']"
            seen_ids = set()
            last_count = -1
            stable_count = 0
            max_scroll_attempts = 18
            use_container = self._detect_scroll_container(driver)
            if use_container:
                self.log("   ℹ️ 내부 스크롤 컨테이너 감지, 컨테이너 스크롤 우선 적용", 10)
            
            for _ in range(max_scroll_attempts):
                if self._should_stop():
                    break

                current_count, current_ids = self._get_item_state(driver, selectors)
                new_ids = current_ids - seen_ids
                seen_ids.update(current_ids)

                if current_count == last_count and not new_ids:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                    last_count = current_count

                used_container = self._scroll_once(driver, use_container=use_container)
                if use_container and not used_container:
                    self.log("   ℹ️ 내부 컨테이너 스크롤 실패, window 스크롤로 폴백", 10)
                    use_container = False

                if not self._sleep_interruptible(0.8):
                    break
                
        except Exception as e:
            self.log(f"   ⚠️ 스크롤 오류: {e}", 30)
    
    def _parse(self, soup, name, cid, ttype):
        raw_items = []
        found_items = ItemParser.find_items(soup)
        
        if found_items:
            # 선택자 로깅 (ItemParser 내부 디버그 로그와 별개로 사용자에게 진행상황 표시)
            self.log(f"   🔍 파싱 대상: {len(found_items)}개")
        else:
            self.log("   ⚠️ 파싱 대상 항목을 찾지 못했습니다.", 10)
            return {"count": 0, "raw_items": [], "raw_count": 0}
        
        matched_count, skipped_type = 0, 0
        
        for item in found_items:
            if self._should_stop():
                break
            try:
                data = ItemParser.parse_element(item, name, cid, ttype)
                if data and data.get("면적(㎡)", 0) > 0:
                    detected_type = data.get("거래유형", "")
                    if detected_type == ttype:
                        raw_items.append(dict(data))
                        enriched = self._enrich_item_with_history_and_alerts(data)
                        if self._check_filters(enriched, ttype):
                            self._push_item(enriched)
                            matched_count += 1
                        else:
                            self.stats["filtered_out"] += 1
                    else:
                        skipped_type += 1
            except Exception as e:
                self.log(f"   ⚠️ 항목 파싱 중 오류: {e}", 30)
        
        if skipped_type > 0:
            self.log(f"   ℹ️ 다른 거래유형 {skipped_type}건 제외 (요청: {ttype})")
        
        return {
            "count": matched_count,
            "raw_items": raw_items,
            "raw_count": len(found_items),
        }

        
    def _check_filters(self, data, ttype):
        if self.area_filter.get("enabled"):
            sqm = data.get("면적(㎡)", 0)
            if sqm < self.area_filter.get("min", 0) or sqm > self.area_filter.get("max", 999):
                return False
        if self.price_filter.get("enabled"):
            price_range = self.price_filter.get(ttype, {}) or {}
            if ttype == "매매":
                min_p = price_range.get("min", 0)
                max_p = price_range.get("max", 999999)
                price = PriceConverter.to_int(data.get("매매가", "0"))
                if price < min_p or price > max_p:
                    return False
            elif ttype == "월세":
                deposit_min = price_range.get("deposit_min", price_range.get("min", 0))
                deposit_max = price_range.get("deposit_max", price_range.get("max", 999999))
                rent_min = price_range.get("rent_min", price_range.get("min", 0))
                rent_max = price_range.get("rent_max", price_range.get("max", 999999))
                deposit = PriceConverter.to_int(data.get("보증금", "0"))
                monthly_rent = PriceConverter.to_int(data.get("월세", "0"))
                if deposit < deposit_min or deposit > deposit_max:
                    return False
                if monthly_rent < rent_min or monthly_rent > rent_max:
                    return False
            else:
                min_p = price_range.get("min", 0)
                max_p = price_range.get("max", 999999)
                price = PriceConverter.to_int(data.get("보증금", "0"))
                if price < min_p or price > max_p:
                    return False
        return True
