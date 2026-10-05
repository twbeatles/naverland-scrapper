from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabStartStopMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def start_crawling(self: Any) -> bool:
        from src.core.crawl_lock import get_crawl_lock
        from src.core.managers import collection_runtime_kwargs, settings
        from src.ui.widgets.crawler_tab import (
            _get_crawl_cache_cls,
            _get_crawler_thread_cls,
        )

        if self.crawler_thread and self.crawler_thread.isRunning():
            self.append_log("이미 수집이 진행 중입니다.", 30)
            self.status_message.emit("이미 수집이 진행 중입니다.")
            return False

        crawl_lock = get_crawl_lock()
        lock_owner = "complex"
        if not crawl_lock.try_acquire(lock_owner):
            from src.utils.ui_labels import crawl_owner_label

            other = crawl_owner_label(crawl_lock.owner())
            self.append_log(
                f"다른 수집이 진행 중이라 시작할 수 없습니다. (진행 중: {other})",
                30,
            )
            self.status_message.emit("다른 수집이 끝나야 시작할 수 있습니다.")
            return False
        self._crawl_lock_owner = lock_owner

        try:
            in_maintenance = bool(self._maintenance_guard()) if callable(self._maintenance_guard) else False
        except (TypeError, ValueError, AttributeError, RuntimeError):
            in_maintenance = False
        if in_maintenance:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            self.append_log("데이터 복원 작업 중에는 수집을 시작할 수 없습니다.", 30)
            self.status_message.emit("데이터 복원 작업이 끝난 뒤 다시 시도해 주세요.")
            return False

        if self.table_list.rowCount() == 0:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(
                self,
                "단지를 먼저 추가해 주세요",
                "수집할 단지가 없습니다.\n「단지 찾기」로 단지를 검색해 목록에 추가해 주세요.",
            )
            return False
        
        target_list = self._normalize_task_table()
        if not target_list:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(
                self,
                "단지를 먼저 추가해 주세요",
                "수집할 단지가 없습니다.\n「단지 찾기」로 단지를 검색해 목록에 추가해 주세요.",
            )
            return False
             
        trade_types = []
        if self.check_trade.isChecked(): trade_types.append("매매")
        if self.check_jeonse.isChecked(): trade_types.append("전세")
        if self.check_monthly.isChecked(): trade_types.append("월세")
        
        if not trade_types:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(self, "거래 종류를 선택해 주세요", "매매·전세·월세 중 하나 이상을 선택해 주세요.")
            return False

        engine_name = str(settings.get("crawl_engine", "playwright") or "playwright").strip().lower() or "playwright"
        unsupported_selenium_targets = [
            (name, cid, asset_type)
            for name, cid, asset_type in target_list
            if self._normalize_task_asset_type(asset_type) != "APT"
        ]
        if engine_name == "selenium" and unsupported_selenium_targets:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(
                self,
                "빌라는 기본 엔진에서만 수집할 수 있습니다",
                "지금 선택된 보조 엔진(Selenium)은 아파트만 수집할 수 있습니다.\n"
                "설정 → 고급에서 수집 엔진을 기본(Playwright)으로 바꾸거나, 목록에서 빌라를 빼 주세요.",
            )
            self.append_log("보조 엔진(Selenium)은 빌라를 수집할 수 없어 시작하지 않았습니다.", 30)
            self.status_message.emit("빌라는 기본 엔진(Playwright)에서만 수집할 수 있습니다.")
            return False

        if (
            engine_name == "playwright"
            and bool(settings.get("fallback_engine_enabled", True))
            and unsupported_selenium_targets
        ):
            skipped = ", ".join(
                f"{name} ({cid})" for name, cid, _ in unsupported_selenium_targets[:5]
            )
            self.append_log(
                "참고: 기본 엔진이 실패해 보조 엔진으로 넘어가면 빌라는 건너뜁니다: "
                + skipped,
                10,
            )

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.log_browser.clear()
        self.log_summary.clear()
        self.progress_widget.reset()
        self.summary_card.reset()
        self.collected_data = []
        self.crawl_cache = None
        self._reset_result_state()
        self.card_view.set_data([])
        self.grouped_rows = {}
        self._last_complex_status_stats = None
        self._crawl_finished_once = False

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
            playwright_headless=settings.get("playwright_headless", True),
            playwright_detail_workers=settings.get("playwright_detail_workers", 4),
            block_heavy_resources=settings.get("playwright_block_heavy_resources", True),
            playwright_response_drain_timeout_ms=settings.get("playwright_response_drain_timeout_ms", 3000),
            playwright_navigation_timeout_ms=settings.get("playwright_navigation_timeout_ms", 15000),
            playwright_article_api_fast_path=settings.get("playwright_article_api_fast_path", True),
            playwright_article_api_timeout_ms=settings.get("playwright_article_api_timeout_ms", 2500),
            playwright_article_response_wait_ms=settings.get("playwright_article_response_wait_ms", 1200),
            **collection_runtime_kwargs(settings),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.error_signal.connect(self._on_crawl_error)
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        try:
            self.crawler_thread.start()
        except RuntimeError as exc:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            self.crawler_thread = None
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.append_log(f"수집을 시작하지 못했습니다: {exc}", 40)
            return False
        
        self._update_result_empty_state()
        self.progress_widget.status_label.setText("수집을 준비하고 있습니다…")
        self.status_message.emit(f"단지 {len(target_list)}곳의 매물 수집을 시작했습니다.")
        self.crawling_started.emit()
        return True

    def _on_crawl_error(self: Any, message) -> None:
        # ISSUE-019: 에러 시그널이 로그에만 머물러 버튼이 stale 상태로 남던
        # 문제를 수정 — 로그+상태바/토스트 알림, 스레드 사망 시 버튼 복구.
        text = f"수집 중 문제가 생겼습니다: {message}"
        try:
            self.append_log(text, 40)
        except Exception:
            pass
        try:
            self.status_message.emit(str(message or "수집 중 문제가 생겼습니다."))
        except Exception:
            pass
        try:
            window = self.window() if hasattr(self, "window") else None
            show_toast = getattr(window, "show_toast", None)
            if callable(show_toast):
                show_toast(text, toast_type="error")
        except Exception:
            pass
        try:
            thread = getattr(self, "crawler_thread", None)
            running = bool(thread is not None and thread.isRunning())
        except Exception:
            running = True
        if not running:
            for name, enabled in (("btn_start", True), ("btn_stop", False)):
                try:
                    getattr(self, name).setEnabled(enabled)
                except Exception:
                    pass

    def _release_crawl_lock(self: Any) -> None:
        from src.core.crawl_lock import get_crawl_lock

        owner = getattr(self, "_crawl_lock_owner", None)
        try:
            # ISSUE-002: only the owning tab may release; a tab holding no
            # lock (owner None) must never clear another tab's lock.
            if owner:
                get_crawl_lock().release(owner)
        finally:
            self._crawl_lock_owner = None

    def stop_crawling(self: Any):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.stop()
            self.append_log("수집을 멈추는 중입니다. 잠시만 기다려 주세요…", 30)
            self.status_message.emit("수집을 멈추는 중입니다…")
            self.btn_stop.setEnabled(False)

    def shutdown_crawl(self: Any, timeout_ms: int = 8000) -> bool:
        # Snapshot bulk writes must settle before the tab (and its DB pool)
        # goes away; bounded so shutdown can never hang on them.
        try:
            waiter = getattr(self, "_wait_for_snapshot_worker", None)
            if callable(waiter):
                waiter()
        except Exception:
            pass
        thread = self.crawler_thread
        if not thread:
            self._release_crawl_lock()
            return True
        if not thread.isRunning():
            self.crawler_thread = None
            self._release_crawl_lock()
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
            self._release_crawl_lock()
            return True
        self.append_log("수집이 제때 멈추지 않았습니다. 잠시 후 다시 시도해 주세요.", 30)
        return False
