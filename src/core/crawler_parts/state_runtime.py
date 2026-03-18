from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.crawler import *  # noqa: F403


class CrawlerStateRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
        geo_incomplete_safety_mode=True,
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
            "geo_incomplete": False,
            "geo_incomplete_count": 0,
            "geo_incomplete_reasons": [],
            "response_drain_wait_count": 0,
            "response_drain_timeout_count": 0,
            "response_seen_count": 0,
            "parse_success_count": 0,
            "parse_fail_count": 0,
            "detail_fetch_total": 0,
            "detail_fetch_success": 0,
            "detail_success_count": 0,
            "detail_fail_count": 0,
            "detail_fetch_skipped_count": 0,
            "blocked_page_count": 0,
            "playwright_recycle_count": 0,
            "playwright_last_recycle_reason": "",
            "fallback_trigger_count": 0,
            "fallback_last_reason": "",
            "block_detect_count": 0,
            "block_cooldown_count": 0,
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
        self.geo_incomplete_safety_mode = bool(geo_incomplete_safety_mode)
        self.geo_incomplete = False
        self.geo_incomplete_reasons = []
        self.geo_incomplete_count = 0
        self._engine = None
        self._last_batch_flush_at = time.monotonic()
        self._history_state_cache = {}
        self._alert_rules_cache = {}
        self._pending_history_rows = []
        self._db_write_disabled_notified = False
        self._registered_discovered_complex_keys = set()
        self._discovered_complex_status = {}
        self._pending_discovered_complexes = {}
        self._pair_sequence = self._build_pair_sequence()
        self._processed_pairs = set()
        self._current_pair = None
        self._fallback_allowed_pairs = None
        self._fallback_prefill_complexes = {}
        self._fallback_prefill_processed_target_pairs = set()
        self._seen_item_keys = set()
        self._consecutive_block_detect_count = 0
        self._block_cooldown_threshold = 3
        self._block_cooldown_seconds = 60
        self._blocked_pair_streaks = {}
        self._blocked_pair_cooldown_until = {}
        self._blocked_total_count = 0
        self._blocked_pair_streak_threshold = 2
        self._blocked_pair_cooldown_sec = 90
        self._blocked_global_threshold = 5

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

    def _pair_key(self, name, cid, trade_type):
        return (str(name or ""), str(cid or ""), str(trade_type or ""))

    def _build_pair_sequence(self):
        pairs = []
        for name, cid in self.targets:
            for trade_type in self.trade_types:
                pairs.append(self._pair_key(name, cid, trade_type))
        return pairs

    def _remaining_pairs(self):
        return [pair for pair in self._pair_sequence if pair not in self._processed_pairs]

    def _mark_pair_processed(self, name, cid, trade_type):
        self._processed_pairs.add(self._pair_key(name, cid, trade_type))

    @staticmethod
    def _unique_trade_types(trade_types):
        ordered = []
        seen = set()
        for trade_type in trade_types or []:
            token = str(trade_type or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        return ordered

    def _determine_run_status(
        self,
        requested_trade_types,
        successful_trade_types,
        attempted_trade_types,
        *,
        force_incomplete=False,
    ) -> str:
        if force_incomplete:
            return "incomplete"
        requested = self._unique_trade_types(requested_trade_types)
        attempted = self._unique_trade_types(attempted_trade_types)
        successful = self._unique_trade_types(successful_trade_types)
        if attempted and not successful:
            return "failed"
        if requested and all(token in successful for token in requested):
            return "success"
        return "partial"

    def _mark_geo_incomplete(self, reason: str, detail: str = "") -> None:
        token = str(reason or "").strip().lower()
        if not token:
            return
        self.geo_incomplete = True
        self.geo_incomplete_count = int(self.geo_incomplete_count) + 1
        if token not in self.geo_incomplete_reasons:
            self.geo_incomplete_reasons.append(token)
        self.stats["geo_incomplete"] = True
        self.stats["geo_incomplete_count"] = int(self.geo_incomplete_count)
        self.stats["geo_incomplete_reasons"] = [
            self._geo_incomplete_reason_label(reason) for reason in self.geo_incomplete_reasons
        ]
        detail_text = f" ({detail})" if detail else ""
        self.log(f"   geo incomplete flagged: {token}{detail_text}", 30)
        self.emit_stats()

    @staticmethod
    def _geo_incomplete_reason_label(reason: str) -> str:
        mapping = {
            "marker_switch_fail": "marker switch fail",
            "marker_drain_timeout": "marker drain timeout",
            "geo_scan_failure": "geo scan failure",
        }
        token = str(reason or "").strip().lower()
        return mapping.get(token, token or "unknown")

    def _geo_incomplete_reason_summary(self) -> str:
        reasons = [self._geo_incomplete_reason_label(reason) for reason in self.geo_incomplete_reasons]
        return ", ".join(reasons)

    def _should_persist_geo_results(self) -> bool:
        return not (self.crawl_mode == "geo_sweep" and self.geo_incomplete and self.geo_incomplete_safety_mode)

    def _item_dedupe_key(self, item):
        if not isinstance(item, dict):
            return None
        article_id = str(item.get("매물ID", "") or item.get("article_id", "")).strip()
        if not article_id:
            return None
        complex_id = str(item.get("단지ID", "") or item.get("complex_id", "")).strip()
        trade_type = str(item.get("거래유형", "") or item.get("trade_type", "")).strip()
        if not complex_id or not trade_type:
            return None
        return (complex_id, article_id, trade_type)

    def log(self, msg, level=20): self.log_signal.emit(msg, level)

    def _push_item(self, item):
        dedupe_key = self._item_dedupe_key(item)
        if dedupe_key is not None:
            if dedupe_key in self._seen_item_keys:
                return False
            self._seen_item_keys.add(dedupe_key)
        self.collected_data.append(item)
        self.pending_items.append(item)
        self.stats["total_found"] += 1
        if self.emit_legacy_item_signal:
            self.item_signal.emit(item)
        self._flush_pending_items_if_needed()
        return True

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
            "geo_incomplete": bool(self.stats.get("geo_incomplete", False)),
            "geo_incomplete_count": self.stats.get("geo_incomplete_count", 0),
            "geo_incomplete_reasons": list(self.stats.get("geo_incomplete_reasons", [])),
            "response_drain_wait_count": self.stats.get("response_drain_wait_count", 0),
            "response_drain_timeout_count": self.stats.get("response_drain_timeout_count", 0),
            "response_seen_count": self.stats.get("response_seen_count", 0),
            "parse_success_count": self.stats.get("parse_success_count", 0),
            "parse_fail_count": self.stats.get("parse_fail_count", 0),
            "detail_fetch_total": self.stats.get("detail_fetch_total", 0),
            "detail_fetch_success": self.stats.get("detail_fetch_success", 0),
            "detail_success_count": self.stats.get("detail_success_count", 0),
            "detail_fail_count": self.stats.get("detail_fail_count", 0),
            "detail_fetch_skipped_count": self.stats.get("detail_fetch_skipped_count", 0),
            "blocked_page_count": self.stats.get("blocked_page_count", 0),
            "playwright_recycle_count": self.stats.get("playwright_recycle_count", 0),
            "playwright_last_recycle_reason": self.stats.get("playwright_last_recycle_reason", ""),
            "fallback_trigger_count": self.stats.get("fallback_trigger_count", 0),
            "fallback_last_reason": self.stats.get("fallback_last_reason", ""),
            "block_detect_count": self.stats.get("block_detect_count", 0),
            "block_cooldown_count": self.stats.get("block_cooldown_count", 0),
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

    def _cache_key(self, *parts):
        return tuple(str(part or "") for part in parts)

    def _blocked_pair_key(self, name, cid, trade_type):
        return self._pair_key(name, cid, trade_type)

    def _get_pair_blocked_cooldown_remaining(self, name, cid, trade_type) -> float:
        key = self._blocked_pair_key(name, cid, trade_type)
        cooldown_until = float(self._blocked_pair_cooldown_until.get(key, 0.0) or 0.0)
        if cooldown_until <= 0.0:
            return 0.0
        remaining = cooldown_until - time.monotonic()
        if remaining <= 0.0:
            self._blocked_pair_cooldown_until.pop(key, None)
            return 0.0
        return remaining

    def _record_blocked_event(self, name, cid, trade_type):
        key = self._blocked_pair_key(name, cid, trade_type)
        streak = int(self._blocked_pair_streaks.get(key, 0) or 0) + 1
        self._blocked_pair_streaks[key] = streak
        self._blocked_total_count = int(self._blocked_total_count) + 1
        self.stats["blocked_page_count"] = int(self.stats.get("blocked_page_count", 0)) + 1

        pair_cooldown_started = False
        cooldown_seconds = 0
        if streak >= int(self._blocked_pair_streak_threshold):
            self._blocked_pair_streaks[key] = 0
            cooldown_seconds = int(self._blocked_pair_cooldown_sec)
            self._blocked_pair_cooldown_until[key] = time.monotonic() + float(cooldown_seconds)
            pair_cooldown_started = True

        global_abort = int(self._blocked_total_count) >= int(self._blocked_global_threshold)
        return {
            "pair_streak": streak,
            "pair_cooldown_started": pair_cooldown_started,
            "pair_cooldown_seconds": cooldown_seconds,
            "blocked_total_count": int(self._blocked_total_count),
            "global_abort": global_abort,
        }

    def _record_pair_success(self, name, cid, trade_type):
        key = self._blocked_pair_key(name, cid, trade_type)
        self._blocked_pair_streaks[key] = 0
        self._blocked_pair_cooldown_until.pop(key, None)

    def _is_block_like_error(self, error) -> bool:
        text = str(error or "").lower()
        if not text:
            return False
        if "temporary blocked page detected" in text:
            return True
        if "blocked page" in text:
            return True
        for pattern in getattr(self, "BLOCKED_PAGE_PATTERNS", ()):
            token = str(pattern or "").lower()
            if token and token in text:
                return True
        return False

    def _register_block_detection(self, reason: str = "") -> bool:
        self.stats["block_detect_count"] = int(self.stats.get("block_detect_count", 0)) + 1
        self._consecutive_block_detect_count += 1
        if reason:
            self.log(f"   ⚠️ 차단 신호 누적 {self._consecutive_block_detect_count}/{self._block_cooldown_threshold}: {reason}", 30)
        if self._consecutive_block_detect_count < int(self._block_cooldown_threshold):
            return False
        self._consecutive_block_detect_count = 0
        self.stats["block_cooldown_count"] = int(self.stats.get("block_cooldown_count", 0)) + 1
        return True

    def _reset_block_detection_streak(self):
        self._consecutive_block_detect_count = 0

