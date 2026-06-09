from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabStartStopMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def start_crawling(self: Any) -> bool:
        from src.ui.widgets.crawler_tab import (
            _get_crawl_cache_cls,
            _get_crawler_thread_cls,
        )

        if self.crawler_thread and self.crawler_thread.isRunning():
            self.append_log("⚠️ 이미 크롤링이 실행 중입니다.", 30)
            self.status_message.emit("이미 크롤링이 실행 중입니다.")
            return False

        try:
            in_maintenance = bool(self._maintenance_guard()) if callable(self._maintenance_guard) else False
        except Exception:
            in_maintenance = False
        if in_maintenance:
            self.append_log("⛔ 유지보수 모드에서는 크롤링을 시작할 수 없습니다.", 30)
            self.status_message.emit("유지보수 모드에서는 크롤링이 차단됩니다.")
            return False

        if self.table_list.rowCount() == 0:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            return False
        
        target_list = self._normalize_task_table()
        if not target_list:
            QMessageBox.warning(self, "경고", "크롤링할 단지를 추가해주세요.")
            return False
             
        trade_types = []
        if self.check_trade.isChecked(): trade_types.append("매매")
        if self.check_jeonse.isChecked(): trade_types.append("전세")
        if self.check_monthly.isChecked(): trade_types.append("월세")
        
        if not trade_types:
            QMessageBox.warning(self, "경고", "최소 하나의 거래 유형을 선택해주세요.")
            return False

        engine_name = str(settings.get("crawl_engine", "playwright") or "playwright").strip().lower() or "playwright"
        unsupported_selenium_targets = [
            (name, cid, asset_type)
            for name, cid, asset_type in target_list
            if self._normalize_task_asset_type(asset_type) != "APT"
        ]
        if engine_name == "selenium" and unsupported_selenium_targets:
            QMessageBox.warning(
                self,
                "경고",
                "Selenium complex 모드는 현재 APT만 지원합니다. VL 대상은 Playwright 엔진으로 실행해주세요.",
            )
            self.append_log("⚠️ Selenium complex 모드는 VL 대상을 지원하지 않아 시작을 중단했습니다.", 30)
            self.status_message.emit("VL 대상은 Playwright complex 모드로 실행해주세요.")
            return False

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.log_browser.clear()
        self.progress_widget.reset()
        self.summary_card.reset()
        self.collected_data = []
        self.crawl_cache = None
        self._reset_result_state()
        self.card_view.set_data([])
        self.grouped_rows = {}
        self._last_complex_status_stats = None

        area_filter = {"enabled": self.check_area_filter.isChecked(), "min": self.spin_area_min.value(), "max": self.spin_area_max.value()}
        price_filter = {
            "enabled": self.check_price_filter.isChecked(),
            "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()},
            "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()},
            "월세": {
                "deposit_min": self.spin_monthly_deposit_min.value(),
                "deposit_max": self.spin_monthly_deposit_max.value(),
                "rent_min": self.spin_monthly_rent_min.value(),
                "rent_max": self.spin_monthly_rent_max.value(),
                # Legacy keys for backward compatibility with old readers.
                "min": self.spin_monthly_rent_min.value(),
                "max": self.spin_monthly_rent_max.value(),
            },
        }

        if self.history_manager:
            try:
                self.history_manager.add(
                    {
                        "complexes": [
                            {"name": name, "cid": cid, "asset_type": asset_type}
                            for name, cid, asset_type in target_list
                        ],
                        "trade_types": list(trade_types),
                        "area_filter": area_filter,
                        "price_filter": price_filter,
                    }
                )
            except Exception as e:
                logger.warning(f"최근 검색 기록 저장 실패: {e}")

        try:
            configured_retry_count = max(0, int(settings.get("max_retry_count", 3)))
        except (TypeError, ValueError):
            configured_retry_count = 3
        retry_on_error = bool(settings.get("retry_on_error", True))
        max_retry_count = configured_retry_count if retry_on_error else 0

        if settings.get("cache_enabled", True):
            cache_cls = _get_crawl_cache_cls()
            self.crawl_cache = cache_cls(
                ttl_minutes=settings.get("cache_ttl_minutes", 30),
                write_back_interval_sec=settings.get("cache_write_back_interval_sec", 2),
                max_entries=settings.get("cache_max_entries", 2000),
            )
        
        # Start Thread
        crawler_thread_cls = _get_crawler_thread_cls()
        self.crawler_thread = crawler_thread_cls(
            target_list, trade_types, area_filter, price_filter, self.db,
            speed=self.speed_slider.current_speed(),
            cache=self.crawl_cache,
            ui_batch_interval_ms=settings.get("ui_batch_interval_ms", 120),
            ui_batch_size=settings.get("ui_batch_size", 30),
            max_retry_count=max_retry_count,
            show_new_badge=settings.get("show_new_badge", True),
            show_price_change=settings.get("show_price_change", True),
            price_change_threshold=settings.get("price_change_threshold", 0),
            track_disappeared=settings.get("track_disappeared", True),
            history_batch_size=settings.get("history_batch_size", 200),
            negative_cache_ttl_minutes=settings.get("cache_negative_ttl_minutes", 5),
            engine_name=engine_name,
            crawl_mode="complex",
            fallback_engine_enabled=settings.get("fallback_engine_enabled", True),
            playwright_headless=settings.get("playwright_headless", False),
            playwright_detail_workers=settings.get("playwright_detail_workers", 12),
            block_heavy_resources=settings.get("playwright_block_heavy_resources", True),
            playwright_response_drain_timeout_ms=settings.get("playwright_response_drain_timeout_ms", 3000),
            playwright_navigation_timeout_ms=settings.get("playwright_navigation_timeout_ms", 15000),
            playwright_article_api_fast_path=settings.get("playwright_article_api_fast_path", True),
            playwright_article_api_timeout_ms=settings.get("playwright_article_api_timeout_ms", 2500),
            playwright_article_response_wait_ms=settings.get("playwright_article_response_wait_ms", 1200),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.error_signal.connect(lambda msg: self.append_log(f"❌ 크롤링 오류: {msg}", 40))
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        self.crawler_thread.start()
        
        self.crawling_started.emit()
        return True

    def stop_crawling(self: Any):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.append_log("🛑 중지 요청 중...", 30)
            self.btn_stop.setEnabled(False)

    def shutdown_crawl(self: Any, timeout_ms: int = 8000) -> bool:
        thread = self.crawler_thread
        if not thread:
            return True
        if not thread.isRunning():
            self.crawler_thread = None
            return True

        if hasattr(thread, "set_shutdown_mode"):
            thread.set_shutdown_mode(True)
        thread.stop()
        try:
            wait_ms = max(100, int(timeout_ms))
        except (TypeError, ValueError):
            wait_ms = 8000
        finished = bool(thread.wait(wait_ms))
        if finished:
            self.crawler_thread = None
            return True
        self.append_log(f"⚠️ 크롤링 종료 대기 타임아웃 ({wait_ms}ms)", 30)
        return False
