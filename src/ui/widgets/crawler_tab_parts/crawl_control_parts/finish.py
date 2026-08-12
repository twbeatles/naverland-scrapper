from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabFinishMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _format_api_failure_summary(self: Any, final_stats: dict) -> str:
        reasons = final_stats.get("article_api_failure_reasons") or {}
        if not isinstance(reasons, dict) or not reasons:
            return ""
        parts = []
        for key, count in sorted(reasons.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
            parts.append(f"{key}={int(count or 0)}")
        return ", ".join(parts[:8])

    def _on_crawl_finished(self: Any, data):
        final_stats = {}
        thread = self.crawler_thread
        if thread and hasattr(thread, "stats"):
            try:
                final_stats = dict(thread.stats or {})
            except (TypeError, ValueError, AttributeError):
                final_stats = {}
        try:
            self.btn_save.setEnabled(True)
            self.progress_widget.complete()
            self.append_log(f"✅ 크롤링 완료: 총 {len(data)}건 수집")
            if final_stats:
                detail_skip = int(final_stats.get("detail_fetch_skipped_count", 0) or 0)
                detail_cap = int(final_stats.get("detail_cap_truncated", 0) or 0)
                detail_disabled = int(final_stats.get("detail_enrichment_disabled", 0) or 0)
                api_last = str(final_stats.get("article_api_last_status", "") or "-")
                fail_summary = self._format_api_failure_summary(final_stats)
                list_meta = int(final_stats.get("detail_list_meta_only_count", 0) or 0)
                host_unreach = int(final_stats.get("detail_host_unreachable_count", 0) or 0)
                rate_limited = int(final_stats.get("detail_front_api_rate_limited_count", 0) or 0)
                self.append_log(
                    "📌 진단 요약: "
                    f"browser={final_stats.get('playwright_browser_source', '-')}, "
                    f"entry_plan={final_stats.get('playwright_last_entry_plan', '-')}, "
                    f"response={int(final_stats.get('response_seen_count', 0) or 0)}, "
                    f"match={int(final_stats.get('response_match_count', 0) or 0)}, "
                    f"api_hit={int(final_stats.get('article_api_fast_path_hit_count', 0) or 0)}, "
                    f"api_fallback={int(final_stats.get('article_api_fast_path_fallback_count', 0) or 0)}, "
                    f"api_status={api_last}, "
                    f"capture_fail={int(final_stats.get('capture_failed_count', 0) or 0)}, "
                    f"block_like={int(final_stats.get('block_like_redirect_count', 0) or 0)}, "
                    f"detail_partial={int(final_stats.get('detail_partial_count', 0) or 0)}, "
                    f"detail_list_meta={list_meta}, "
                    f"detail_fail={int(final_stats.get('detail_fail_count', 0) or 0)}, "
                    f"detail_host_unreach={host_unreach}, "
                    f"detail_429={rate_limited}, "
                    f"detail_skip={detail_skip}, "
                    f"detail_cap={detail_cap}, "
                    f"detail_off={detail_disabled}",
                    10,
                )
                if fail_summary:
                    self.append_log(f"📌 목록 API 실패 사유: {fail_summary}", 10)
                if detail_disabled:
                    self.append_log("ℹ️ 상세 정보 조회가 설정에서 꺼져 있어 중개·기전세 필드는 비어 있을 수 있습니다.", 20)
                elif detail_cap > 0:
                    self.append_log(
                        f"ℹ️ 단지당 상세 조회 상한으로 {detail_cap}건은 상세 없이 목록만 반영했습니다.",
                        20,
                    )
                elif detail_skip > 0:
                    self.append_log(
                        f"ℹ️ 상세 조회를 건너뛴 매물 {detail_skip}건이 있습니다.",
                        20,
                    )
                if host_unreach > 0 or rate_limited > 0:
                    self.append_log(
                        "ℹ️ 상세 호스트(fin) 불안정 또는 front-api 429로 전화·기전세가 비어 있을 수 있습니다. "
                        "목록의 중개소명(realtorName)은 유지됩니다.",
                        20,
                    )
                elif list_meta > 0:
                    self.append_log(
                        f"ℹ️ {list_meta}건은 상세 API 없이 목록 메타(중개소명 등)만 반영했습니다.",
                        20,
                    )

            if self.crawl_cache:
                self.crawl_cache.flush()
            
            # DB Write
            try:
                self._save_price_snapshots()
            except (OSError, RuntimeError, ValueError, TypeError) as e:
                self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {e}", 30)

            if self._compact_duplicates and self._compact_items_by_key:
                self._schedule_compact_refresh(full=True, immediate=True)
                self._schedule_card_view_refresh(immediate=True)

            if settings.get("play_sound_on_complete", True):
                try:
                    QApplication.beep()
                except RuntimeError as e:
                    logger.debug(f"완료 알림음 재생 실패 (무시): {e}")
            
            self.data_collected.emit(data) # Notify App
            self.crawling_stopped.emit()
            
        except (RuntimeError, AttributeError, TypeError, ValueError) as e:
            self.append_log(f"❌ 크롤링 마무리 중 오류: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
        finally:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.crawler_thread = None
            if hasattr(self, "_release_crawl_lock"):
                self._release_crawl_lock()

    def _on_complex_finished(self: Any, name, cid, trade_types, count):
        self.append_log(f"📌 단지 완료: {name} ({cid}) {count}건", 10)

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        self.append_log(
            f"🔔 알림 조건 충족: {complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)",
            30,
        )
        self.alert_triggered.emit(complex_name, trade_type, price_text, area_pyeong, int(alert_id or 0))

    def _update_stats_ui(self: Any, stats):
        self.summary_card.update_stats(
            total=stats["total_found"],
            trade=stats["by_trade_type"].get("매매", 0),
            jeonse=stats["by_trade_type"].get("전세", 0),
            monthly=stats["by_trade_type"].get("월세", 0),
            filtered=stats["filtered_out"],
            new_count=stats.get("new_count", 0),
            price_up=stats.get("price_up", 0),
            price_down=stats.get("price_down", 0),
        )
        browser_source = str(stats.get("playwright_browser_source", "") or "")
        response_seen = int(stats.get("response_seen_count", 0) or 0)
        response_match = int(stats.get("response_match_count", 0) or 0)
        parse_fail = int(stats.get("parse_fail_count", 0) or 0)
        capture_failed = int(stats.get("capture_failed_count", 0) or 0)
        block_like = int(stats.get("block_like_redirect_count", 0) or 0)
        api_hit = int(stats.get("article_api_fast_path_hit_count", 0) or 0)
        api_fallback = int(stats.get("article_api_fast_path_fallback_count", 0) or 0)
        detail_partial = int(stats.get("detail_partial_count", 0) or 0)
        detail_fail = int(stats.get("detail_fail_count", 0) or 0)
        final_url = str(stats.get("playwright_last_final_url", "") or "")
        block_reason = str(stats.get("playwright_last_block_reason", "") or "")
        entry_plan = str(stats.get("playwright_last_entry_plan", "") or "")
        snapshot = (
            browser_source,
            response_seen,
            response_match,
            parse_fail,
            capture_failed,
            block_like,
            api_hit,
            api_fallback,
            detail_partial,
            detail_fail,
            final_url,
            block_reason,
            entry_plan,
        )
        if getattr(self, "_last_complex_status_stats", None) == snapshot:
            return
        self._last_complex_status_stats = snapshot
        message = (
            f"PW {browser_source or '-'} / 응답 {response_seen} / 매칭 {response_match}"
            f" / API {api_hit}/{api_fallback}"
            f" / 파싱실패 {parse_fail} / capture실패 {capture_failed}"
            f" / block-like {block_like} / 상세부분 {detail_partial} / 상세실패 {detail_fail}"
        )
        if entry_plan:
            message += f" / plan {entry_plan}"
        if block_reason:
            message += f" / reason {block_reason}"
        elif final_url:
            message += f" / final {final_url}"
        self.status_message.emit(message)
