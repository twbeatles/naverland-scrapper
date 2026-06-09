from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabFinishMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _on_crawl_finished(self: Any, data):
        final_stats = {}
        thread = self.crawler_thread
        if thread and hasattr(thread, "stats"):
            try:
                final_stats = dict(thread.stats or {})
            except Exception:
                final_stats = {}
        try:
            self.btn_save.setEnabled(True)
            self.progress_widget.complete()
            self.append_log(f"✅ 크롤링 완료: 총 {len(data)}건 수집")
            if final_stats:
                self.append_log(
                    "📌 진단 요약: "
                    f"browser={final_stats.get('playwright_browser_source', '-')}, "
                    f"entry_plan={final_stats.get('playwright_last_entry_plan', '-')}, "
                    f"response={int(final_stats.get('response_seen_count', 0) or 0)}, "
                    f"match={int(final_stats.get('response_match_count', 0) or 0)}, "
                    f"api_hit={int(final_stats.get('article_api_fast_path_hit_count', 0) or 0)}, "
                    f"api_fallback={int(final_stats.get('article_api_fast_path_fallback_count', 0) or 0)}, "
                    f"capture_fail={int(final_stats.get('capture_failed_count', 0) or 0)}, "
                    f"block_like={int(final_stats.get('block_like_redirect_count', 0) or 0)}, "
                    f"detail_partial={int(final_stats.get('detail_partial_count', 0) or 0)}, "
                    f"detail_fail={int(final_stats.get('detail_fail_count', 0) or 0)}",
                    10,
                )

            if self.crawl_cache:
                self.crawl_cache.flush()
            
            # DB Write
            try:
                self._save_price_snapshots()
            except Exception as e:
                self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {e}", 30)

            if self._compact_duplicates and self._compact_items_by_key:
                self._schedule_compact_refresh(full=True, immediate=True)
                self._schedule_card_view_refresh(immediate=True)

            if settings.get("play_sound_on_complete", True):
                try:
                    QApplication.beep()
                except Exception as e:
                    logger.debug(f"완료 알림음 재생 실패 (무시): {e}")
            
            self.data_collected.emit(data) # Notify App
            self.crawling_stopped.emit()
            
        except Exception as e:
            self.append_log(f"❌ 크롤링 마무리 중 오류: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
        finally:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.crawler_thread = None

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
