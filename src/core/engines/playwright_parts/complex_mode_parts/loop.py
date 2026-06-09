from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.response_capture import TRADE_CODE_MAP, detect_trade_type, normalize_article_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}
_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class PlaywrightComplexLoopMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    async def _run_complex_mode(self):
        await self._ensure_started()
        targets = list(self.thread._iter_targets())
        total = len(targets) * len(self.thread.trade_types)
        current = 0
        processed_pairs = set()
        for pair in set(getattr(self.thread, "_fallback_prefill_processed_target_pairs", set()) or set()):
            if not isinstance(pair, tuple) or len(pair) < 2:
                continue
            if len(pair) >= 3:
                processed_pairs.add((str(pair[0]), str(pair[1]), str(pair[2])))
            else:
                processed_pairs.add(("APT", str(pair[0]), str(pair[1])))
        for name, cid, asset_type in targets:
            if self.thread._should_stop():
                break
            complex_count = 0
            attempted_trade_types = []
            complex_trade_types = []
            for trade_type in self.thread.trade_types:
                if self.thread._should_stop():
                    break
                if trade_type not in attempted_trade_types:
                    attempted_trade_types.append(trade_type)
                await self._check_memory_and_recycle_if_needed("complex_loop")
                self.thread._current_pair = self.thread._pair_key(name, cid, trade_type, asset_type=asset_type)
                current += 1
                self.thread.progress_signal.emit(
                    int(current / total * 100) if total else 0,
                    f"{name} ({trade_type})",
                    self.thread._estimate_remaining_seconds(current, total),
                )
                self.thread.log(f"\n[{current}/{total}] {name} - {trade_type}")
                try:
                    result = await self._crawl_target_with_cache(name, cid, trade_type, asset_type=asset_type)
                    if bool(result.get("block_like_redirect", False)):
                        raise RuntimeError(str(result.get("block_reason", "") or "block-like redirect"))
                    if bool(result.get("capture_failed", False)):
                        raise RuntimeError(str(result.get("failure_reason", "") or "capture failed after navigation"))
                    count = int(result.get("count", 0))
                    complex_count += count
                    if trade_type not in complex_trade_types:
                        complex_trade_types.append(trade_type)
                    processed_pair = (str(asset_type), str(cid), str(trade_type))
                    processed_pairs.add(processed_pair)
                    self.thread._fallback_prefill_processed_target_pairs.add(processed_pair)
                    self.thread.stats["by_trade_type"][trade_type] = (
                        self.thread.stats["by_trade_type"].get(trade_type, 0) + count
                    )
                    self.thread._mark_pair_processed(name, cid, trade_type, asset_type=asset_type)
                    self.thread._reset_block_detection_streak()
                    self.thread.log(f"   {count}건 수집")
                except Exception as exc:
                    self.thread.log(f"   오류: {exc}", 40)
                    block_like = self.thread._is_block_like_error(exc)
                    if block_like:
                        should_cooldown = self.thread._register_block_detection(str(exc))
                        if should_cooldown:
                            self.thread.log(
                                f"   ⏸️ 차단 신호 3회 연속 감지, {int(self.thread._block_cooldown_seconds)}초 쿨다운",
                                30,
                            )
                            if not await self._sleep_async_interruptible(self.thread._block_cooldown_seconds):
                                self.thread._current_pair = None
                                return
                    else:
                        self.thread._reset_block_detection_streak()
                    if self.thread.fallback_engine_enabled and not self._fallback_used:
                        if str(asset_type or "APT").strip().upper() != "APT":
                            self.thread.log(
                                "   ℹ️ VL complex 대상은 Selenium fallback을 지원하지 않아 Playwright 오류로 건너뜁니다.",
                                30,
                            )
                        else:
                            self._fallback_used = True
                            self.thread.log("   Selenium fallback으로 전환합니다.", 30)
                            prefill_payload = None
                            if complex_trade_types:
                                prefill_payload = {
                                    "name": name,
                                    "cid": cid,
                                    "asset_type": asset_type,
                                    "count": int(complex_count),
                                    "trade_types": list(complex_trade_types),
                                }
                            self.thread._run_fallback_selenium(
                                start_name=name,
                                start_cid=cid,
                                start_trade=trade_type,
                                prefill_complex=prefill_payload,
                                prefill_processed_target_pairs=set(processed_pairs),
                                reason=str(exc),
                            )
                            self.thread._current_pair = None
                            return
                if not self.thread._sleep_interruptible(self.thread._get_speed_delay()):
                    break
            self.thread._flush_history_updates(force=True)
            if not attempted_trade_types:
                continue
            run_status = self.thread._determine_run_status(
                self.thread.trade_types,
                complex_trade_types,
                attempted_trade_types,
            )
            history_trade_types = complex_trade_types or attempted_trade_types
            self.thread.record_crawl_history(
                name,
                cid,
                ",".join(history_trade_types),
                int(complex_count),
                engine=self.engine_name,
                mode=self.thread.crawl_mode,
                asset_type=asset_type,
                run_status=run_status,
            )
            if complex_trade_types:
                self.thread.complex_finished_signal.emit(name, cid, ",".join(complex_trade_types), int(complex_count))
        self.thread._current_pair = None
        self.thread._finalize_disappeared_articles(processed_pairs)
