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

    @staticmethod
    def _finish_status_text(count: int) -> str:
        if count > 0:
            return f"수집을 마쳤습니다. 매물 {count}건 · 「결과 저장」으로 파일에 담을 수 있습니다."
        return "수집을 마쳤지만 조건에 맞는 매물이 없습니다."

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
            self._crawl_finished_once = True
            self.append_log(f"수집을 마쳤습니다. 매물 {len(data)}건을 찾았습니다.")
            self.status_message.emit(self._finish_status_text(len(data)))
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
                    "진단 요약: "
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
                    self.append_log(f"진단: 목록 조회 실패 사유 {fail_summary}", 10)
                if detail_disabled:
                    self.append_log("참고: 설정에서 상세 정보 가져오기가 꺼져 있어 중개소·기존 전세금 칸이 비어 있을 수 있습니다.", 20)
                elif detail_cap > 0:
                    self.append_log(
                        f"참고: 단지마다 정해 둔 상세 조회 한도를 넘어 {detail_cap}건은 기본 정보만 담았습니다.",
                        20,
                    )
                elif detail_skip > 0:
                    self.append_log(
                        f"참고: 매물 {detail_skip}건은 상세 정보를 가져오지 못해 기본 정보만 담았습니다.",
                        20,
                    )
                if host_unreach > 0 or rate_limited > 0:
                    self.append_log(
                        "참고: 네이버 상세 페이지 응답이 불안정해 전화번호·기존 전세금이 비어 있을 수 있습니다. "
                        "중개소 이름은 그대로 표시됩니다.",
                        20,
                    )
                elif list_meta > 0:
                    self.append_log(
                        f"참고: {list_meta}건은 상세 정보 없이 목록의 기본 정보(중개소 이름 등)만 담았습니다.",
                        20,
                    )

            if self.crawl_cache:
                self.crawl_cache.flush()
            
            # DB Write (ISSUE-007: synchronous while the crawl lock is held,
            # so the save cannot outlive the finally-block lock release).
            try:
                self._save_price_snapshots(async_save=False)
            except (OSError, RuntimeError, ValueError, TypeError) as e:
                self.append_log(f"가격 변화 기록을 저장하지 못했습니다: {e}", 30)

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
            self.append_log(f"수집 결과를 정리하는 중 문제가 생겼습니다: {e}", 40)
            logger.error(f"Crawl finish handler failed: {e}")
        finally:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.crawler_thread = None
            if hasattr(self, "_release_crawl_lock"):
                self._release_crawl_lock()
            if hasattr(self, "_update_result_empty_state"):
                self._update_result_empty_state()

    def _on_complex_finished(self: Any, name, cid, trade_types, count):
        self.append_log(f"{name}: 매물 {count}건", 20)

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        try:
            safe_alert_id = int(alert_id or 0)
        except (TypeError, ValueError):
            safe_alert_id = 0
        try:
            safe_area = float(area_pyeong)
            area_text = f"{safe_area:.1f}평"
        except (TypeError, ValueError):
            safe_area = 0.0
            fallback = "" if area_pyeong is None else str(area_pyeong).strip()
            area_text = f"{fallback}평" if fallback else "평형 미상"
        self.append_log(
            f"알림 조건에 맞는 매물: {complex_name} {trade_type} {price_text} ({area_text})",
            30,
        )
        self.alert_triggered.emit(complex_name, trade_type, price_text, safe_area, safe_alert_id)

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
        diagnostics = self._format_complex_diagnostics(stats)
        if getattr(self, "_last_complex_status_stats", None) == diagnostics:
            return
        self._last_complex_status_stats = diagnostics
        # 기술 진단 수치는 상태 표시줄 대신 진행 표시의 툴팁에만 남긴다.
        self.last_diagnostic_text = diagnostics
        try:
            self.progress_widget.setToolTip(diagnostics)
        except Exception:
            pass
        total = int(stats.get("total_found", 0) or 0)
        blocked = int(stats.get("block_like_redirect_count", 0) or 0)
        if blocked > 0:
            self.status_message.emit(
                f"수집 중 · 매물 {total}건 · 네이버가 접속을 제한하는 것 같습니다. 속도를 낮추면 도움이 됩니다."
            )
        else:
            self.status_message.emit(f"수집 중 · 지금까지 매물 {total}건")

    @staticmethod
    def _format_complex_diagnostics(stats) -> str:
        """개발·문의용 진단 한 줄 (사용자 기본 화면에는 노출하지 않는다)."""
        browser_source = str(stats.get("playwright_browser_source", "") or "")
        message = (
            f"PW {browser_source or '-'}"
            f" / 응답 {int(stats.get('response_seen_count', 0) or 0)}"
            f" / 매칭 {int(stats.get('response_match_count', 0) or 0)}"
            f" / API {int(stats.get('article_api_fast_path_hit_count', 0) or 0)}"
            f"/{int(stats.get('article_api_fast_path_fallback_count', 0) or 0)}"
            f" / 파싱실패 {int(stats.get('parse_fail_count', 0) or 0)}"
            f" / capture실패 {int(stats.get('capture_failed_count', 0) or 0)}"
            f" / block-like {int(stats.get('block_like_redirect_count', 0) or 0)}"
            f" / 상세부분 {int(stats.get('detail_partial_count', 0) or 0)}"
            f" / 상세실패 {int(stats.get('detail_fail_count', 0) or 0)}"
        )
        entry_plan = str(stats.get("playwright_last_entry_plan", "") or "")
        block_reason = str(stats.get("playwright_last_block_reason", "") or "")
        final_url = str(stats.get("playwright_last_final_url", "") or "")
        if entry_plan:
            message += f" / plan {entry_plan}"
        if block_reason:
            message += f" / reason {block_reason}"
        elif final_url:
            message += f" / final {final_url}"
        return message
