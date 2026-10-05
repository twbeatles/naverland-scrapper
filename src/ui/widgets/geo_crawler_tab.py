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
    QVBoxLayout,
)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QWidget
from qfluentwidgets import FluentIcon as FIF

from src.core.models.crawl_models import GeoSweepConfig
from src.core.managers import collection_runtime_kwargs, settings
from src.ui.widgets.crawler_tab import (
    CrawlerTab,
    _get_crawl_cache_cls,
    _get_crawler_thread_cls,
)



CrawlerThread = None


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

    @staticmethod
    def _float_setting(key, default):
        raw = settings.get(key, default)
        if raw is None:
            return float(default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    RESULT_EMPTY_INITIAL = (
        "아직 찾은 매물이 없습니다",
        "왼쪽에서 위치를 정한 뒤 「탐색 시작」을 눌러 주세요.",
    )

    DISCOVERED_STATUS_LABELS = {
        "inserted": "새로 찾음",
        "existing": "기존",
        "pending": "대기",
        "blocked_incomplete": "보류",
        "skipped": "유지",
        "error": "오류",
    }

    def _setup_complex_list_group(self, layout):
        """위치는 지역 이름으로 고르고, 좌표·세부 값은 접어 둔다."""
        group = QGroupBox("탐색할 위치")
        outer = QVBoxLayout()
        outer.setSpacing(8)

        # 1) 위치: 지역 이름으로 찾기
        place_row = QHBoxLayout()
        place_row.setSpacing(8)
        self.btn_find_region = QPushButton("지역 찾기")
        self.btn_find_region.setIcon(FIF.SEARCH.icon())
        self.btn_find_region.setObjectName("secondaryBtn")
        self.btn_find_region.setToolTip("동·구 이름으로 검색해 탐색할 위치를 정합니다. (예: 반포동, 분당구)")
        self.btn_find_region.clicked.connect(self._show_region_search_dialog)
        place_row.addWidget(self.btn_find_region)
        self.lbl_geo_place = QLabel("")
        self.lbl_geo_place.setWordWrap(True)
        place_row.addWidget(self.lbl_geo_place, 1)
        outer.addLayout(place_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        self.spin_rings = QSpinBox()
        self.spin_rings.setRange(0, 6)
        self.spin_rings.setValue(max(0, self._int_setting("geo_grid_rings", 1)))
        self.spin_rings.setSuffix(" 단계")
        self.spin_rings.setToolTip(
            "0단계는 정한 위치의 지도 한 화면만 봅니다.\n"
            "숫자가 커질수록 주변을 더 넓게 훑고, 시간도 더 걸립니다."
        )
        grid.addWidget(self._field_label("주변까지 넓히기"), 0, 0)
        grid.addWidget(self.spin_rings, 0, 1)

        asset_layout = QHBoxLayout()
        self.check_asset_apt = QCheckBox("아파트")
        self.check_asset_vl = QCheckBox("빌라·연립")
        asset_types = settings.get("geo_asset_types", ["APT", "VL"])
        if asset_types is None:
            asset_types = ["APT", "VL"]
        self.check_asset_apt.setChecked("APT" in asset_types)
        self.check_asset_vl.setChecked("VL" in asset_types)
        asset_layout.addWidget(self.check_asset_apt)
        asset_layout.addWidget(self.check_asset_vl)
        asset_layout.addStretch()
        grid.addWidget(self._field_label("주택 종류"), 1, 0)
        grid.addLayout(asset_layout, 1, 1)
        outer.addLayout(grid)

        # 2) 좌표·세부 값 (기본 접힘)
        adv = QWidget()
        adv_grid = QGridLayout(adv)
        adv_grid.setContentsMargins(0, 0, 0, 0)
        adv_grid.setHorizontalSpacing(8)
        adv_grid.setVerticalSpacing(8)
        adv_grid.setColumnStretch(1, 1)

        self.spin_lat = QDoubleSpinBox()
        self.spin_lat.setRange(33.0, 39.5)
        self.spin_lat.setDecimals(6)
        self.spin_lat.setValue(self._float_setting("geo_last_lat", 37.5608))
        adv_grid.addWidget(self._field_label("위도"), 0, 0)
        adv_grid.addWidget(self.spin_lat, 0, 1)

        self.spin_lon = QDoubleSpinBox()
        self.spin_lon.setRange(124.0, 132.1)
        self.spin_lon.setDecimals(6)
        self.spin_lon.setValue(self._float_setting("geo_last_lon", 126.9888))
        adv_grid.addWidget(self._field_label("경도"), 1, 0)
        adv_grid.addWidget(self.spin_lon, 1, 1)

        self.spin_zoom = QSpinBox()
        self.spin_zoom.setRange(12, 18)
        self.spin_zoom.setValue(self._int_setting("geo_default_zoom", 15))
        self.spin_zoom.setToolTip("숫자가 클수록 지도를 더 가깝게(좁은 범위를 자세히) 봅니다.")
        adv_grid.addWidget(self._field_label("지도 확대 단계"), 2, 0)
        adv_grid.addWidget(self.spin_zoom, 2, 1)

        self.spin_step = QSpinBox()
        self.spin_step.setRange(120, 1600)
        self.spin_step.setSingleStep(40)
        self.spin_step.setValue(self._int_setting("geo_grid_step_px", 480))
        self.spin_step.setToolTip("한 번에 지도를 옮기는 거리입니다. 기본값을 권장합니다.")
        adv_grid.addWidget(self._field_label("지도 이동 간격"), 3, 0)
        adv_grid.addWidget(self.spin_step, 3, 1)

        self.spin_dwell = QSpinBox()
        self.spin_dwell.setRange(100, 5000)
        self.spin_dwell.setSingleStep(100)
        self.spin_dwell.setSuffix(" ms")
        self.spin_dwell.setValue(self._int_setting("geo_sweep_dwell_ms", 600))
        self.spin_dwell.setToolTip("지도를 옮긴 뒤 매물이 뜰 때까지 기다리는 시간입니다. (1000ms = 1초)")
        adv_grid.addWidget(self._field_label("옮길 때마다 대기"), 4, 0)
        adv_grid.addWidget(self.spin_dwell, 4, 1)

        save_defaults = QPushButton("지금 값을 기본으로 저장")
        save_defaults.setObjectName("secondaryBtn")
        save_defaults.setToolTip("확대 단계·범위·주택 종류를 다음에도 같은 값으로 시작합니다.")
        save_defaults.clicked.connect(self._on_save_geo_defaults_clicked)
        adv_grid.addWidget(save_defaults, 5, 0, 1, 2)

        self.btn_geo_adv_toggle = self._make_disclosure("좌표 직접 입력·세부 설정", adv, expanded=False)
        outer.addWidget(self.btn_geo_adv_toggle)
        outer.addWidget(adv)

        # 3) 탐색하며 찾은 단지
        found_title = QLabel("찾은 단지")
        found_title.setStyleSheet("font-weight: 600; margin-top: 4px;")
        outer.addWidget(found_title)
        self.lbl_discovered_placeholder = QLabel("탐색을 시작하면 그 지역에서 찾은 단지가 여기에 쌓입니다.")
        self.lbl_discovered_placeholder.setObjectName("listPlaceholder")
        self.lbl_discovered_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_discovered_placeholder.setWordWrap(True)
        outer.addWidget(self.lbl_discovered_placeholder, 1)

        self.discovered_table = QTableWidget()
        self.discovered_table.setColumnCount(5)
        self.discovered_table.setHorizontalHeaderLabels(
            ["상태", "종류", "단지 이름", "단지 번호", "매물 수"]
        )
        discovered_header = self.discovered_table.horizontalHeader()
        if discovered_header is not None:
            discovered_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            discovered_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        discovered_vheader = self.discovered_table.verticalHeader()
        if discovered_vheader is not None:
            discovered_vheader.setVisible(False)
        self.discovered_table.setMinimumHeight(140)
        self.discovered_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.discovered_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        from src.ui.widgets.components import install_token_labels
        from src.utils.ui_labels import asset_label

        install_token_labels(self.discovered_table, 1, asset_label)
        outer.addWidget(self.discovered_table, 1)

        group.setLayout(outer)
        layout.addWidget(group, 1)

        discovered_model = self.discovered_table.model()
        if discovered_model is not None:
            discovered_model.rowsInserted.connect(lambda *_: self._update_discovered_state())
            discovered_model.rowsRemoved.connect(lambda *_: self._update_discovered_state())
            discovered_model.modelReset.connect(lambda *_: self._update_discovered_state())
        self._update_discovered_state()

        self._geo_place_name = str(settings.get("geo_last_region_name", "") or "")
        self.spin_lat.valueChanged.connect(self._on_geo_coordinates_edited)
        self.spin_lon.valueChanged.connect(self._on_geo_coordinates_edited)
        self._refresh_geo_place_label()

    def _setup_action_group(self, layout):
        super()._setup_action_group(layout)
        self.btn_start.setText("탐색 시작")
        self.btn_start.setToolTip("정한 위치 주변의 단지와 매물을 찾아 수집합니다.")

    def _update_discovered_state(self):
        table = getattr(self, "discovered_table", None)
        placeholder = getattr(self, "lbl_discovered_placeholder", None)
        if table is None or placeholder is None:
            return
        has_rows = int(table.rowCount() or 0) > 0
        placeholder.setVisible(not has_rows)
        table.setVisible(has_rows)

    def _refresh_geo_place_label(self):
        label = getattr(self, "lbl_geo_place", None)
        if label is None:
            return
        name = str(getattr(self, "_geo_place_name", "") or "").strip()
        if name:
            label.setText(f"{name} 주변을 탐색합니다.")
        elif abs(self.spin_lat.value() - 37.5608) < 1e-6 and abs(self.spin_lon.value() - 126.9888) < 1e-6:
            label.setText("기본 위치(서울 중구) 주변을 탐색합니다. 「지역 찾기」로 원하는 곳을 고르세요.")
        else:
            label.setText(
                f"직접 입력한 좌표 ({self.spin_lat.value():.4f}, {self.spin_lon.value():.4f}) 주변을 탐색합니다."
            )

    def _set_geo_place_name(self, name: str):
        self._geo_place_name = str(name or "").strip()
        settings.set("geo_last_region_name", self._geo_place_name)
        self._refresh_geo_place_label()

    def _on_geo_coordinates_edited(self, *_args):
        # 좌표를 손으로 바꾸면 더 이상 고른 지역 이름과 맞지 않는다.
        if getattr(self, "_applying_geo_profile", False):
            return
        if getattr(self, "_geo_place_name", ""):
            self._set_geo_place_name("")
        else:
            self._refresh_geo_place_label()

    def _show_region_search_dialog(self):
        from src.ui.dialogs import KeywordSearchDialog

        dlg = KeywordSearchDialog(self, mode="region")
        dlg.region_chosen.connect(self._apply_region_choice)
        dlg.exec()

    def _apply_region_choice(self, region):
        region = dict(region or {})
        try:
            lat = float(str(region.get("latitude")))
            lon = float(str(region.get("longitude")))
        except (TypeError, ValueError):
            QMessageBox.information(
                self, "위치를 알 수 없습니다", "이 지역은 위치 정보가 없어 사용할 수 없습니다. 다른 지역을 골라 주세요."
            )
            return
        if not (33.0 <= lat <= 39.5 and 124.0 <= lon <= 132.1):
            QMessageBox.information(
                self, "위치를 알 수 없습니다", "이 지역의 위치가 올바르지 않습니다. 다른 지역을 골라 주세요."
            )
            return
        self._applying_geo_profile = True
        try:
            self.spin_lat.setValue(lat)
            self.spin_lon.setValue(lon)
        finally:
            self._applying_geo_profile = False
        self._set_geo_place_name(str(region.get("name", "") or "선택한 지역"))
        self._save_last_geo_coordinates()
        self.status_message.emit(f"탐색 위치를 '{self._geo_place_name}'(으)로 정했습니다.")

    def _on_save_geo_defaults_clicked(self):
        if self._save_geo_defaults():
            self.status_message.emit("지금 값을 지도 탐색 기본값으로 저장했습니다.")

    def _save_geo_defaults(self):
        asset_types = []
        if self.check_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            QMessageBox.warning(self, "주택 종류를 선택해 주세요", "아파트 또는 빌라·연립 중 하나 이상 선택해 주세요.")
            return False
        settings.update(
            {
                "geo_default_zoom": self.spin_zoom.value(),
                "geo_grid_rings": self.spin_rings.value(),
                "geo_grid_step_px": self.spin_step.value(),
                "geo_sweep_dwell_ms": self.spin_dwell.value(),
                "geo_asset_types": asset_types,
            }
        )
        return True

    def _save_last_geo_coordinates(self):
        settings.update(
            {
                "geo_last_lat": float(self.spin_lat.value()),
                "geo_last_lon": float(self.spin_lon.value()),
            }
        )

    def apply_geo_profile(
        self,
        *,
        lat: float,
        lon: float,
        zoom: int,
        rings: int,
        step_px: int,
        dwell_ms: int,
        asset_types,
        persist_last: bool = True,
        region_name: str | None = None,
    ):
        if asset_types is None:
            asset_tokens = {"APT", "VL"}
        else:
            asset_tokens = {str(asset or "").strip().upper() for asset in (asset_types or [])}
        self._applying_geo_profile = True
        try:
            self.spin_lat.setValue(float(lat))
            self.spin_lon.setValue(float(lon))
        finally:
            self._applying_geo_profile = False
        if persist_last:
            self._set_geo_place_name(str(region_name or ""))
        else:
            # 예약 실행처럼 임시로 좌표만 바꾸는 경우: 저장된 지역 이름은 건드리지 않는다.
            self._geo_place_name = str(region_name or "")
            self._refresh_geo_place_label()
        self.spin_zoom.setValue(int(zoom))
        self.spin_rings.setValue(max(0, int(rings)))
        self.spin_step.setValue(int(step_px))
        self.spin_dwell.setValue(int(dwell_ms))
        self.check_asset_apt.setChecked("APT" in asset_tokens)
        self.check_asset_vl.setChecked("VL" in asset_tokens)
        if persist_last:
            self._skip_last_geo_save_once = False
            self._save_last_geo_coordinates()
        else:
            self._skip_last_geo_save_once = True

    def update_runtime_settings(self):
        super().update_runtime_settings()
        self.spin_zoom.setValue(self._int_setting("geo_default_zoom", 15))
        self.spin_rings.setValue(max(0, self._int_setting("geo_grid_rings", 1)))
        self.spin_step.setValue(self._int_setting("geo_grid_step_px", 480))
        self.spin_dwell.setValue(self._int_setting("geo_sweep_dwell_ms", 600))
        asset_types = settings.get("geo_asset_types", ["APT", "VL"])
        if asset_types is None:
            asset_types = ["APT", "VL"]
        self.check_asset_apt.setChecked("APT" in asset_types)
        self.check_asset_vl.setChecked("VL" in asset_types)

    def start_crawling(self) -> bool:
        global CrawlerThread
        from src.core.crawl_lock import get_crawl_lock

        if self._maintenance_guard and self._maintenance_guard():
            self.status_message.emit("데이터 복원 작업이 끝난 뒤 다시 시도해 주세요.")
            return False
        if self.crawler_thread and self.crawler_thread.isRunning():
            QMessageBox.information(self, "이미 탐색 중입니다", "지도 탐색이 이미 진행 중입니다.")
            return False

        crawl_lock = get_crawl_lock()
        lock_owner = "geo"
        if not crawl_lock.try_acquire(lock_owner):
            from src.utils.ui_labels import crawl_owner_label

            other = crawl_owner_label(crawl_lock.owner())
            # Avoid modal dialogs here — they block headless/automated runs.
            self.append_log(
                f"다른 수집이 진행 중이라 지도 탐색을 시작할 수 없습니다. (진행 중: {other})",
                30,
            )
            self.status_message.emit("다른 수집이 끝나야 시작할 수 있습니다.")
            return False
        self._crawl_lock_owner = lock_owner

        trade_types = []
        if self.check_trade.isChecked():
            trade_types.append("매매")
        if self.check_jeonse.isChecked():
            trade_types.append("전세")
        if self.check_monthly.isChecked():
            trade_types.append("월세")
        if not trade_types:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(self, "거래 종류를 선택해 주세요", "매매·전세·월세 중 하나 이상을 선택해 주세요.")
            return False

        asset_types = []
        if self.check_asset_apt.isChecked():
            asset_types.append("APT")
        if self.check_asset_vl.isChecked():
            asset_types.append("VL")
        if not asset_types:
            crawl_lock.release(lock_owner)
            self._crawl_lock_owner = None
            QMessageBox.warning(self, "주택 종류를 선택해 주세요", "아파트 또는 빌라·연립 중 하나 이상 선택해 주세요.")
            return False
        skip_last_geo_save_once = bool(getattr(self, "_skip_last_geo_save_once", False))
        self._skip_last_geo_save_once = False
        if not skip_last_geo_save_once:
            self._save_last_geo_coordinates()

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
        self.discovered_table.setRowCount(0)
        self._discovered_row_map = {}
        self._last_geo_status_stats = None
        self._crawl_finished_once = False

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
            cache_cls = _get_crawl_cache_cls()
            self.crawl_cache = cache_cls(
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
        if CrawlerThread is None:
            CrawlerThread = _get_crawler_thread_cls()
        crawler_thread_cls = CrawlerThread
        self.crawler_thread = crawler_thread_cls(
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
            playwright_headless=settings.get("playwright_headless", True),
            playwright_detail_workers=settings.get("playwright_detail_workers", 4),
            block_heavy_resources=settings.get("playwright_block_heavy_resources", True),
            playwright_response_drain_timeout_ms=settings.get("playwright_response_drain_timeout_ms", 3000),
            playwright_navigation_timeout_ms=settings.get("playwright_navigation_timeout_ms", 15000),
            playwright_article_api_fast_path=settings.get("playwright_article_api_fast_path", True),
            playwright_article_api_timeout_ms=settings.get("playwright_article_api_timeout_ms", 2500),
            playwright_article_response_wait_ms=settings.get("playwright_article_response_wait_ms", 1200),
            geo_incomplete_safety_mode=settings.get("geo_incomplete_safety_mode", True),
            **collection_runtime_kwargs(settings),
        )
        self.crawler_thread.log_signal.connect(self.append_log)
        self.crawler_thread.progress_signal.connect(self.progress_widget.update_progress)
        self.crawler_thread.items_signal.connect(self._on_items_batch)
        self.crawler_thread.stats_signal.connect(self._update_stats_ui)
        self.crawler_thread.complex_finished_signal.connect(self._on_complex_finished)
        self.crawler_thread.alert_triggered_signal.connect(self._on_alert_triggered)
        self.crawler_thread.discovered_complex_signal.connect(self._on_discovered_complex)
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
            self.append_log(f"지도 탐색을 시작하지 못했습니다: {exc}", 40)
            return False
        self._update_result_empty_state()
        self.progress_widget.status_label.setText("지도 탐색을 준비하고 있습니다…")
        self.status_message.emit("지도 탐색을 시작했습니다. 찾은 단지가 왼쪽에 쌓입니다.")
        self.crawling_started.emit()
        return True

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
        status = self.DISCOVERED_STATUS_LABELS.get(status, status)
        self.discovered_table.setItem(row, 0, QTableWidgetItem(status))
        self.discovered_table.setItem(row, 1, QTableWidgetItem(asset_type))
        self.discovered_table.setItem(row, 2, QTableWidgetItem(str(payload.get("complex_name", ""))))
        self.discovered_table.setItem(row, 3, QTableWidgetItem(complex_id))
        self.discovered_table.setItem(row, 4, QTableWidgetItem(str(payload.get("count", 0))))

    @staticmethod
    def _format_geo_diagnostics(stats, *, joiner: str = " / ") -> str:
        """개발·문의용 진단 한 줄. 기본 화면이 아니라 진행 기록·툴팁에만 쓴다."""

        def _n(key):
            return int(stats.get(key, 0) or 0)

        browser_source = str(stats.get("playwright_browser_source", "") or "")
        marker_method = str(stats.get("geo_marker_switch_last_method", "") or "")
        parts = [
            f"발견 {_n('geo_discovered_count')}",
            f"중복제거 {_n('geo_dedup_count')}",
            f"drain대기 {_n('response_drain_wait_count')}",
            f"drain타임아웃 {_n('response_drain_timeout_count')}",
            f"브라우저 {browser_source or '-'}",
            f"응답 {_n('response_seen_count')}",
            f"매칭 {_n('response_match_count')}",
            f"파싱실패 {_n('parse_fail_count')}",
            f"상세부분 {_n('detail_partial_count')}",
            f"상세실패 {_n('detail_fail_count')}",
            f"상세스킵 {_n('detail_fetch_skipped_count')}",
            f"capture실패 {_n('capture_failed_count')}",
            f"block-like {_n('block_like_redirect_count')}",
            f"marker전환 {_n('geo_marker_switch_success_count')}/{_n('geo_marker_switch_attempt_count')}",
            f"marker실패 {_n('geo_marker_switch_fail_count')}",
            f"marker방법 {marker_method or '-'}",
            f"차단 {_n('blocked_page_count')}",
        ]
        entry_plan = str(stats.get("playwright_last_entry_plan", "") or "")
        block_reason = str(stats.get("playwright_last_block_reason", "") or "")
        if entry_plan:
            parts.append(f"plan {entry_plan}")
        if block_reason:
            parts.append(f"reason {block_reason}")
        if bool(stats.get("geo_incomplete", False)):
            reasons = ", ".join(str(x) for x in (stats.get("geo_incomplete_reasons", []) or []) if str(x))
            parts.append(f"incomplete {reasons or 'unknown'}")
        return joiner.join(parts)

    def _update_stats_ui(self, stats):
        super()._update_stats_ui(stats)
        diagnostics = "Geo " + self._format_geo_diagnostics(stats)
        if getattr(self, "_last_geo_status_stats", None) == diagnostics:
            return
        self._last_geo_status_stats = diagnostics
        self.last_diagnostic_text = diagnostics
        try:
            self.progress_widget.setToolTip(diagnostics)
        except Exception:
            pass
        discovered = int(stats.get("geo_discovered_count", 0) or 0)
        total = int(stats.get("total_found", 0) or 0)
        blocked = int(stats.get("blocked_page_count", 0) or 0) + int(
            stats.get("block_like_redirect_count", 0) or 0
        )
        message = f"지도 탐색 중 · 단지 {discovered}곳 발견 · 매물 {total}건"
        if blocked > 0:
            message += " · 네이버가 접속을 제한하는 것 같습니다. 속도를 낮추면 도움이 됩니다."
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
        diagnostics = self._format_geo_diagnostics(final_stats, joiner=", ")
        self.last_diagnostic_text = "Geo 완료: " + diagnostics
        self.append_log("진단(지도) " + diagnostics, 10)

        discovered = int(final_stats.get("geo_discovered_count", 0) or 0)
        try:
            item_count = len(data or [])
        except TypeError:
            item_count = 0
        self.status_message.emit(
            f"지도 탐색을 마쳤습니다. 단지 {discovered}곳 · 매물 {item_count}건"
        )

        if bool(final_stats.get("geo_incomplete", False)):
            safety_mode = bool(getattr(thread, "geo_incomplete_safety_mode", False)) if thread else False
            incomplete_message = "지도 탐색이 중간에 끊겨 일부 지역은 확인하지 못했습니다."
            if safety_mode:
                incomplete_message += " 잘못된 기록을 막기 위해 이번 결과는 가격 이력에 반영하지 않았습니다."
            incomplete_message += " 잠시 후 다시 시도하거나 탐색 범위를 줄여 보세요."
            self.append_log(incomplete_message, 30)
            self.status_message.emit(incomplete_message)
            window = self.window()
            show_toast = getattr(window, "show_toast", None)
            if callable(show_toast):
                show_toast(incomplete_message, toast_type="warning")
