from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from src.core.cache import CrawlCache
from src.core.crawler import CrawlerThread
from src.core.models.crawl_models import GeoSweepConfig
from src.core.managers import SettingsManager
from src.ui.widgets.crawler_tab import CrawlerTab


settings = SettingsManager()


class GeoCrawlerTab(CrawlerTab):
    @staticmethod
    def _int_setting(key, default):
        raw = settings.get(key, default)
        if raw is None:
            return int(default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return int(default)

    def _setup_complex_list_group(self, layout):
        group = QGroupBox("4️⃣ 지리 탐색")
        grid = QGridLayout()

        self.spin_lat = QDoubleSpinBox()
        self.spin_lat.setRange(33.0, 39.5)
        self.spin_lat.setDecimals(6)
        self.spin_lat.setValue(37.5608)
        grid.addWidget(QLabel("위도:"), 0, 0)
        grid.addWidget(self.spin_lat, 0, 1)

        self.spin_lon = QDoubleSpinBox()
        self.spin_lon.setRange(124.0, 132.1)
        self.spin_lon.setDecimals(6)
        self.spin_lon.setValue(126.9888)
        grid.addWidget(QLabel("경도:"), 1, 0)
        grid.addWidget(self.spin_lon, 1, 1)

        self.spin_zoom = QSpinBox()
        self.spin_zoom.setRange(12, 18)
        self.spin_zoom.setValue(self._int_setting("geo_default_zoom", 15))
        grid.addWidget(QLabel("줌:"), 2, 0)
        grid.addWidget(self.spin_zoom, 2, 1)

        self.spin_rings = QSpinBox()
        self.spin_rings.setRange(0, 6)
        self.spin_rings.setValue(max(0, self._int_setting("geo_grid_rings", 1)))
        grid.addWidget(QLabel("링 수:"), 3, 0)
        grid.addWidget(self.spin_rings, 3, 1)

        self.spin_step = QSpinBox()
        self.spin_step.setRange(120, 1600)
        self.spin_step.setSingleStep(40)
        self.spin_step.setValue(self._int_setting("geo_grid_step_px", 480))
        grid.addWidget(QLabel("간격(px):"), 4, 0)
        grid.addWidget(self.spin_step, 4, 1)

        self.spin_dwell = QSpinBox()
        self.spin_dwell.setRange(100, 5000)
        self.spin_dwell.setSingleStep(100)
        self.spin_dwell.setValue(self._int_setting("geo_sweep_dwell_ms", 600))
        grid.addWidget(QLabel("대기(ms):"), 5, 0)
        grid.addWidget(self.spin_dwell, 5, 1)

        asset_layout = QHBoxLayout()
        self.check_asset_apt = QCheckBox("APT")
        self.check_asset_vl = QCheckBox("VL")
        asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        self.check_asset_apt.setChecked("APT" in asset_types)
        self.check_asset_vl.setChecked("VL" in asset_types)
        asset_layout.addWidget(self.check_asset_apt)
        asset_layout.addWidget(self.check_asset_vl)
        asset_layout.addStretch()
        grid.addWidget(QLabel("자산:"), 6, 0)
        grid.addLayout(asset_layout, 6, 1)

        self.discovered_table = QTableWidget()
        self.discovered_table.setColumnCount(5)
        self.discovered_table.setHorizontalHeaderLabels(["상태", "자산", "단지명", "ID", "매물수"])
        discovered_header = self.discovered_table.horizontalHeader()
        if discovered_header is not None:
            discovered_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        grid.addWidget(QLabel("발견 단지:"), 7, 0, 1, 2)
        grid.addWidget(self.discovered_table, 8, 0, 1, 2)

        save_defaults = QPushButton("💾 기본값 저장")
        save_defaults.setObjectName("secondaryBtn")
        save_defaults.clicked.connect(self._save_geo_defaults)
        grid.addWidget(save_defaults, 9, 0, 1, 2)

        group.setLayout(grid)
        layout.addWidget(group)

    def _save_geo_defaults(self):
        asset_types = []
        if self.check_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            asset_types = ["APT", "VL"]
        settings.update(
            {
                "geo_default_zoom": self.spin_zoom.value(),
                "geo_grid_rings": self.spin_rings.value(),
                "geo_grid_step_px": self.spin_step.value(),
                "geo_sweep_dwell_ms": self.spin_dwell.value(),
                "geo_asset_types": asset_types,
            }
        )

    def update_runtime_settings(self):
        super().update_runtime_settings()
        self.spin_zoom.setValue(self._int_setting("geo_default_zoom", 15))
        self.spin_rings.setValue(max(0, self._int_setting("geo_grid_rings", 1)))
        self.spin_step.setValue(self._int_setting("geo_grid_step_px", 480))
        self.spin_dwell.setValue(self._int_setting("geo_sweep_dwell_ms", 600))
        asset_types = settings.get("geo_asset_types", ["APT", "VL"]) or ["APT", "VL"]
        self.check_asset_apt.setChecked("APT" in asset_types)
        self.check_asset_vl.setChecked("VL" in asset_types)

    def start_crawling(self):
        if self._maintenance_guard and self._maintenance_guard():
            self.status_message.emit("유지보수 모드에서는 크롤링이 차단됩니다.")
            return
        if self.crawler_thread and self.crawler_thread.isRunning():
            QMessageBox.information(self, "알림", "이미 지리탐색이 실행 중입니다.")
            return

        trade_types = []
        if self.check_trade.isChecked():
            trade_types.append("매매")
        if self.check_jeonse.isChecked():
            trade_types.append("전세")
        if self.check_monthly.isChecked():
            trade_types.append("월세")
        if not trade_types:
            QMessageBox.warning(self, "경고", "최소 하나의 거래 유형을 선택해주세요.")
            return

        asset_types = []
        if self.check_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            asset_types = ["APT", "VL"]

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
        self.discovered_table.setRowCount(0)
        self._discovered_row_map = {}
        self._last_geo_status_stats = None
        if settings.get("fallback_engine_enabled", True):
            self.append_log("⚠️ Geo 모드는 Playwright 전용이며 Selenium fallback은 지원하지 않습니다.", 30)

        area_filter = {
            "enabled": self.check_area_filter.isChecked(),
            "min": self.spin_area_min.value(),
            "max": self.spin_area_max.value(),
        }
        price_filter = {
            "enabled": self.check_price_filter.isChecked(),
            "매매": {"min": self.spin_trade_min.value(), "max": self.spin_trade_max.value()},
            "전세": {"min": self.spin_jeonse_min.value(), "max": self.spin_jeonse_max.value()},
            "월세": {
                "deposit_min": self.spin_monthly_deposit_min.value(),
                "deposit_max": self.spin_monthly_deposit_max.value(),
                "rent_min": self.spin_monthly_rent_min.value(),
                "rent_max": self.spin_monthly_rent_max.value(),
                "min": self.spin_monthly_rent_min.value(),
                "max": self.spin_monthly_rent_max.value(),
            },
        }

        if settings.get("cache_enabled", True):
            self.crawl_cache = CrawlCache(
                ttl_minutes=settings.get("cache_ttl_minutes", 30),
                write_back_interval_sec=settings.get("cache_write_back_interval_sec", 2),
                max_entries=settings.get("cache_max_entries", 2000),
            )

        configured_retry_count = max(0, self._int_setting("max_retry_count", 3))
        retry_on_error = bool(settings.get("retry_on_error", True))
        max_retry_count = configured_retry_count if retry_on_error else 0

        geo_config = GeoSweepConfig(
            lat=self.spin_lat.value(),
            lon=self.spin_lon.value(),
            zoom=self.spin_zoom.value(),
            rings=self.spin_rings.value(),
            step_px=self.spin_step.value(),
            dwell_ms=self.spin_dwell.value(),
            asset_types=asset_types,
        )
        try:
            configured_retry_count = max(0, int(settings.get("max_retry_count", 3)))
        except (TypeError, ValueError):
            configured_retry_count = 3
        retry_on_error = bool(settings.get("retry_on_error", True))
        max_retry_count = configured_retry_count if retry_on_error else 0
        self.crawler_thread = CrawlerThread(
            [],
            trade_types,
            area_filter,
            price_filter,
            self.db,
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
            engine_name="playwright",
            crawl_mode="geo_sweep",
            geo_config=geo_config,
            fallback_engine_enabled=False,
            playwright_headless=settings.get("playwright_headless", False),
            playwright_detail_workers=settings.get("playwright_detail_workers", 12),
            block_heavy_resources=settings.get("playwright_block_heavy_resources", True),
            playwright_response_drain_timeout_ms=settings.get("playwright_response_drain_timeout_ms", 3000),
            geo_incomplete_safety_mode=settings.get("geo_incomplete_safety_mode", True),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.discovered_complex_signal.connect(self._on_discovered_complex)
        self.crawler_thread.error_signal.connect(lambda msg: self.append_log(f"❌ 크롤링 오류: {msg}", 40))
        self.crawler_thread.finished_signal.connect(self._on_crawl_finished)
        self.crawler_thread.start()
        self.crawling_started.emit()

    def _on_discovered_complex(self, payload: dict):
        asset_type = str(payload.get("asset_type", "") or "")
        complex_id = str(payload.get("complex_id", "") or "")
        dedupe_key = f"{asset_type}:{complex_id}"
        if not hasattr(self, "_discovered_row_map"):
            self._discovered_row_map = {}

        row = self._discovered_row_map.get(dedupe_key)
        if row is None:
            row = self.discovered_table.rowCount()
            self.discovered_table.insertRow(row)
            self._discovered_row_map[dedupe_key] = row

        status = str(payload.get("db_status", "") or "")
        if status == "inserted":
            status = "신규"
        elif status == "existing":
            status = "기존"
        elif status == "pending":
            status = "대기"
        elif status == "blocked_incomplete":
            status = "incomplete"
        elif status == "skipped":
            status = "유지"
        elif status == "error":
            status = "오류"
        self.discovered_table.setItem(row, 0, QTableWidgetItem(status))
        self.discovered_table.setItem(row, 1, QTableWidgetItem(asset_type))
        self.discovered_table.setItem(row, 2, QTableWidgetItem(str(payload.get("complex_name", ""))))
        self.discovered_table.setItem(row, 3, QTableWidgetItem(complex_id))
        self.discovered_table.setItem(row, 4, QTableWidgetItem(str(payload.get("count", 0))))

    def _update_stats_ui(self, stats):
        super()._update_stats_ui(stats)
        discovered = int(stats.get("geo_discovered_count", 0) or 0)
        dedup = int(stats.get("geo_dedup_count", 0) or 0)
        drain_wait = int(stats.get("response_drain_wait_count", 0) or 0)
        drain_timeout = int(stats.get("response_drain_timeout_count", 0) or 0)
        response_seen = int(stats.get("response_seen_count", 0) or 0)
        parse_fail = int(stats.get("parse_fail_count", 0) or 0)
        detail_fail = int(stats.get("detail_fail_count", 0) or 0)
        blocked_count = int(stats.get("blocked_page_count", 0) or 0)
        geo_incomplete = bool(stats.get("geo_incomplete", False))
        incomplete_reasons = ", ".join(
            str(x) for x in (stats.get("geo_incomplete_reasons", []) or []) if str(x)
        )
        snapshot = (
            discovered,
            dedup,
            drain_wait,
            drain_timeout,
            response_seen,
            parse_fail,
            detail_fail,
            blocked_count,
            geo_incomplete,
            incomplete_reasons,
        )
        if getattr(self, "_last_geo_status_stats", None) == snapshot:
            return
        self._last_geo_status_stats = snapshot
        message = (
            "Geo 발견 "
            f"{discovered} / 중복제거 {dedup} / drain대기 {drain_wait} / drain타임아웃 {drain_timeout}"
            f" / 응답 {response_seen} / 파싱실패 {parse_fail} / 상세실패 {detail_fail} / 차단 {blocked_count}"
        )
        if geo_incomplete:
            message += f" / incomplete {incomplete_reasons or 'unknown'}"
        self.status_message.emit(message)

    def _on_crawl_finished(self, data):
        final_stats = {}
        thread = self.crawler_thread
        if thread and hasattr(thread, "stats"):
            try:
                final_stats = dict(thread.stats or {})
            except Exception:
                final_stats = {}
        super()._on_crawl_finished(data)
        discovered = int(final_stats.get("geo_discovered_count", 0) or 0)
        dedup = int(final_stats.get("geo_dedup_count", 0) or 0)
        drain_wait = int(final_stats.get("response_drain_wait_count", 0) or 0)
        drain_timeout = int(final_stats.get("response_drain_timeout_count", 0) or 0)
        response_seen = int(final_stats.get("response_seen_count", 0) or 0)
        parse_fail = int(final_stats.get("parse_fail_count", 0) or 0)
        detail_fail = int(final_stats.get("detail_fail_count", 0) or 0)
        blocked_count = int(final_stats.get("blocked_page_count", 0) or 0)
        geo_incomplete = bool(final_stats.get("geo_incomplete", False))
        incomplete_reasons = ", ".join(
            str(x) for x in (final_stats.get("geo_incomplete_reasons", []) or []) if str(x)
        )
        safety_mode = bool(getattr(thread, "geo_incomplete_safety_mode", False)) if thread else False
        self.append_log(
            "📌 Geo 요약: "
            f"발견 {discovered}, 중복제거 {dedup}, drain대기 {drain_wait}, drain timeout {drain_timeout}, "
            f"응답 {response_seen}, 파싱실패 {parse_fail}, 상세실패 {detail_fail}, 차단 {blocked_count}",
            10,
        )
        summary_message = (
            "Geo 완료: "
            f"발견 {discovered}, 중복제거 {dedup}, drain대기 {drain_wait}, drain타임아웃 {drain_timeout}, "
            f"응답 {response_seen}, 파싱실패 {parse_fail}, 상세실패 {detail_fail}, 차단 {blocked_count}"
        )
        self.status_message.emit(summary_message)
        if geo_incomplete:
            incomplete_message = f"Geo incomplete: {incomplete_reasons or 'unknown'}"
            if safety_mode:
                incomplete_message += " (safety mode: auto-register/history/disappeared skipped)"
            self.append_log(incomplete_message, 30)
            self.status_message.emit(incomplete_message)
            window = self.window()
            show_toast = getattr(window, "show_toast", None)
            if callable(show_toast):
                show_toast(incomplete_message, toast_type="warning")
