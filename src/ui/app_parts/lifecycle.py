from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def __init__(self: Any):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1400, 900)
        geo = settings.get("window_geometry")
        if geo: self.setGeometry(*geo)
        else: self.setGeometry(100, 100, 1500, 950)
        
        self.settings_manager = SettingsManager()
        self.preset_manager = FilterPresetManager()
        self.history_manager = SearchHistoryManager(max_items=settings.get("max_search_history", 20))
        self.recently_viewed = RecentlyViewedManager()
        self.advanced_filters = None
        self.collected_data = []
        self.is_scheduled_run = False
        self.retry_handler = None
        self.tray_icon = None
        self._is_shutting_down = False
        self._maintenance_mode = False
        self._maintenance_reason = ""
        self._maintenance_enabled_snapshot: List[Tuple[Any, bool]] = []
        self.favorite_keys = set()
        self._shortcuts = {}
        self.db = ComplexDatabase()
        self._lazy_noncritical_tabs = bool(settings.get("startup_lazy_noncritical_tabs", True))
        self._noncritical_loaded = {
            "history": False,
            "stats": False,
            "favorites": False,
        }
        
        # v11.0: Toast 알림 시스템
        self.toast_widgets: List[ToastWidget] = []
        
        self.current_theme = settings.get("theme", "dark")
        self.setStyleSheet(get_stylesheet(self.current_theme))
        self._input_wheel_guard = install_global_wheel_guard(QApplication.instance())
        
        # UI 초기화
        self._init_ui()
        apply_wheel_guard_recursively(self, self._input_wheel_guard)
        self._init_menu()
        self._init_shortcuts()
        self._init_tray()
        self._init_timers()
        self._load_initial_data()
        
        # 윈도우 설정
        self._restore_window_geometry()
        
        self.show_toast(f"환영합니다! {APP_TITLE} {APP_VERSION}입니다.")

    def _restore_window_geometry(self: Any):
        geo = settings.get("window_geometry")
        if not geo:
            return
        if not isinstance(geo, (list, tuple)) or len(geo) != 4:
            return
        try:
            x, y, w, h = (int(geo[0]), int(geo[1]), int(geo[2]), int(geo[3]))
            self.setGeometry(x, y, w, h)
        except Exception:
            # Best-effort only; invalid saved geometry should not prevent startup.
            return
    
    def _init_menu(self: Any):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("📂 파일")
        self.action_backup_db = file_menu.addAction("💾 DB 백업", self._backup_db)
        self.action_restore_db = file_menu.addAction("📂 DB 복원", self._restore_db)
        file_menu.addSeparator()
        self.action_settings = file_menu.addAction("⚙️ 설정", self._show_settings)
        self.action_quit = file_menu.addAction("❌ 종료", self._quit_app)
        
        # 보기 메뉴 (v13.0)
        view_menu = menubar.addMenu("👁️ 보기")
        view_menu.addAction("🕐 최근 본 매물", self._show_recently_viewed_dialog)
        view_menu.addSeparator()
        
        # 테마 메뉴
        theme_menu = view_menu.addMenu("🎨 테마")
        self.action_theme_dark = QAction("🌙 다크 모드", self)
        self.action_theme_dark.setCheckable(True)
        self.action_theme_dark.setChecked(self.current_theme == "dark")
        self.action_theme_dark.triggered.connect(lambda: self._toggle_theme("dark"))
        theme_menu.addAction(self.action_theme_dark)
        
        self.action_theme_light = QAction("☀️ 라이트 모드", self)
        self.action_theme_light.setCheckable(True)
        self.action_theme_light.setChecked(self.current_theme == "light")
        self.action_theme_light.triggered.connect(lambda: self._toggle_theme("light"))
        theme_menu.addAction(self.action_theme_light)
        
        # 필터 메뉴
        filter_menu = menubar.addMenu("🔍 필터")
        self.action_save_preset = filter_menu.addAction("💾 현재 필터 저장", self._save_preset)
        self.action_load_preset = filter_menu.addAction("📂 필터 불러오기", self._load_preset)
        filter_menu.addSeparator()
        self.action_advanced_filter = filter_menu.addAction("⚙️ 고급 결과 필터", self._show_advanced_filter)
        self.action_clear_advanced_filter = filter_menu.addAction("🧹 고급 필터 해제", self._clear_advanced_filter)
        
        # 알림 메뉴
        alert_menu = menubar.addMenu("🔔 알림")
        alert_menu.addAction("⚙️ 알림 설정", self._show_alert_settings)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("❓ 도움말")
        help_menu.addAction("⌨️ 단축키", self._show_shortcuts)
        help_menu.addAction("ℹ️ 정보", self._show_about)
    
    def _init_shortcuts(self: Any):
        self._register_shortcut(SHORTCUTS["start_crawl"], self._start_crawling)
        self._register_shortcut(SHORTCUTS["stop_crawl"], self._stop_crawling)
        self._register_shortcut(SHORTCUTS["save_excel"], self._save_excel)
        self._register_shortcut(SHORTCUTS["save_csv"], self._save_csv)
        self._register_shortcut(SHORTCUTS["refresh"], self._refresh_tab)
        self._register_shortcut(SHORTCUTS["search"], self._focus_search)
        self._register_shortcut(SHORTCUTS["toggle_theme"], self._toggle_theme)
        self._register_shortcut(SHORTCUTS["minimize_tray"], self._minimize_to_tray)
        self._register_shortcut(SHORTCUTS["quit"], self._quit_app)
        self._register_shortcut(SHORTCUTS["settings"], self._show_settings)

    def _register_shortcut(self: Any, key_sequence, callback):
        shortcut = QShortcut(QKeySequence(key_sequence), self)
        shortcut.activated.connect(callback)
        self._shortcuts[key_sequence] = shortcut

    # Shortcut handlers (delegate to modular widgets)
    def _start_crawling(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.start_crawling()

    def _stop_crawling(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.stop_crawling()

    def _save_excel(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_excel()

    def _save_csv(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_csv()

    def _save_json(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab.save_json()
    
    def _init_tray(self: Any):
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            self.tray_icon = QSystemTrayIcon(icon, self)
            tray_menu = QMenu()
            tray_menu.addAction("🔼 열기", self._show_from_tray)
            tray_menu.addAction("❌ 종료", self._quit_app)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._tray_activated)
            self.tray_icon.show()
    
    def _init_timers(self: Any):
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self._check_schedule)
        self.schedule_timer.start(60000)
    
    def _load_initial_data(self: Any):
        # self._load_db_complexes() - Handled by DatabaseTab
        # self._load_all_groups() - Handled by GroupTab
        if hasattr(self, 'db_tab'): self.db_tab.load_data()
        if hasattr(self, 'group_tab'): self.group_tab.load_groups()

        if not self._lazy_noncritical_tabs:
            self._load_history()
            self._noncritical_loaded["history"] = True
            self._load_stats_complexes()
            self._noncritical_loaded["stats"] = True
            self._refresh_favorite_keys()
            self._noncritical_loaded["favorites"] = True
        self._load_schedule_groups()
        
        # Connect signals after loading
        try:
            self.stats_complex_combo.currentIndexChanged.disconnect(self._on_stats_complex_changed)
        except Exception:
            pass
        self.stats_complex_combo.currentIndexChanged.connect(self._on_stats_complex_changed)

    def _on_crawl_data_collected(self: Any, data):
        self.collected_data = list(data) if data else []
        self._load_history()
        self._noncritical_loaded["history"] = True
        self._load_stats_complexes()
        self._noncritical_loaded["stats"] = True
        if self.tabs.currentWidget() is self.stats_tab:
            self._load_stats()
        if self.dashboard_widget is not None:
            self.dashboard_widget.set_data(self.collected_data)
        if hasattr(self, "favorites_tab"):
            self.favorites_tab.refresh()
            self._noncritical_loaded["favorites"] = True
        self.status_bar.showMessage(f"✅ 수집 결과 반영 완료 ({len(self.collected_data)}건)")

    def _on_alert_triggered(self: Any, complex_name, trade_type, price_text, area_pyeong, alert_id):
        message = f"{complex_name} {trade_type} {price_text} ({area_pyeong:.1f}평)"
        self.show_toast(f"🔔 조건 매물 발견: {message}")
        self.show_notification("조건 매물 알림", message)

    def _on_dashboard_warning(self: Any, message: str):
        text = str(message or "").strip()
        if not text:
            return
        ui_logger.warning(f"Dashboard warning: {text}")
        self.status_bar.showMessage(f"⚠️ {text}")
    
    # Event handlers
    # Obsolete helpers removed (replaced by widgets: CrawlerTab, DatabaseTab, GroupTab)
    # _toggle_area_filter, _toggle_price_filter, _add_complex, _add_row, _delete_complex, _clear_list,
    # _save_to_db, _show_db_load_dialog, _show_group_load_dialog, _show_history_dialog, _open_complex_url,
    # _open_db_complex_url, _open_article_url, _filter_results, _filter_db_table, _sort_results,
    # _start_crawling, _stop_crawling, _update_log, _update_progress, _add_result, _update_stats,
    # _on_complex_done, _crawling_done, _save_price_snapshots, _crawling_error, _show_save_menu,
    # _save_excel, _save_csv, _save_json, _load_db_complexes, _delete_db_complex, _delete_db_complexes_multi,
    # _edit_memo, _update_db_empty_state, _update_db_action_state, _load_all_groups, _create_group,
    # _delete_group, _load_group_complexes, _add_to_group, _add_to_group_multi, _remove_from_group

    
    def _show_shortcuts(self: Any):
        ShortcutsDialog(self).exec()
    
    def _show_about(self: Any):
        AboutDialog(self, theme=self.current_theme).exec()

    def _focus_search(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            if hasattr(self.crawler_tab, "result_search"):
                self.crawler_tab.result_search.setFocus()

    def _minimize_to_tray(self: Any):
        if not self.tray_icon:
            self.status_bar.showMessage("시스템 트레이를 사용할 수 없습니다.")
            return
        self.hide()
        self.tray_icon.showMessage("알림", "트레이로 최소화되었습니다.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_from_tray(self: Any):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self: Any, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()

    def _shutdown(self: Any) -> bool:
        if self._is_shutting_down:
            return True
        self._is_shutting_down = True
        if hasattr(self, "crawler_tab"):
            ok = self.crawler_tab.shutdown_crawl(timeout_ms=8000)
            if not ok:
                self._is_shutting_down = False
                ui_logger.warning("크롤링 스레드 종료 타임아웃으로 앱 종료를 중단합니다.")
                self.status_bar.showMessage("⚠️ 크롤링 종료 후 다시 앱 종료를 시도하세요.")
                return False
        if hasattr(self, "geo_tab"):
            ok = self.geo_tab.shutdown_crawl(timeout_ms=8000)
            if not ok:
                self._is_shutting_down = False
                ui_logger.warning("지도 탐색 스레드 종료 타임아웃으로 앱 종료를 중단합니다.")
                self.status_bar.showMessage("⚠️ 지도 탐색 종료 후 다시 앱 종료를 시도하세요.")
                return False
        if hasattr(self, "schedule_timer") and self.schedule_timer:
            self.schedule_timer.stop()
        settings.set("window_geometry", [self.x(), self.y(), self.width(), self.height()])
        try:
            self.db.close()
        except Exception as e:
            ui_logger.debug(f"DB 종료 중 오류 (무시): {e}")
        if self.tray_icon:
            self.tray_icon.hide()
        return True

    def _quit_app(self: Any, skip_confirm=False):
        if not skip_confirm and settings.get("confirm_before_close"):
            if QMessageBox.question(self, "종료", "정말 종료하시겠습니까?") != QMessageBox.StandardButton.Yes:
                return
        if not self._shutdown():
            QMessageBox.warning(
                self,
                "종료 중단",
                "크롤링 스레드가 아직 종료되지 않아 앱 종료를 중단했습니다.\n잠시 후 다시 시도해주세요.",
            )
            return
        QApplication.quit()

    def closeEvent(self: Any, a0):
        event = a0
        if self._is_shutting_down:
            event.accept()
            return

        asked_confirmation = False
        if settings.get("minimize_to_tray", True) and self.tray_icon:
            event.ignore()
            self._minimize_to_tray()
            return

        if settings.get("confirm_before_close"):
            asked_confirmation = True
            reply = QMessageBox.question(
                self,
                "종료",
                "정말 종료하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        if self._shutdown():
            event.accept()
            return
        if not asked_confirmation:
            QMessageBox.warning(
                self,
                "종료 중단",
                "크롤링 스레드가 아직 종료되지 않아 창 닫기를 취소했습니다.\n잠시 후 다시 시도해주세요.",
            )
        else:
            self.status_bar.showMessage("⚠️ 크롤링 종료 후 다시 창 닫기를 시도하세요.")
        event.ignore()

    def show_toast(self: Any, message, duration=3000):
        # 화면 우측 하단에 표시
        toast = ToastWidget(message, self)
        
        # 위치 계산 (쌓이도록)
        margin = 20
        y = self.height() - margin - toast.height()
        for t in self.toast_widgets:
            y -= (t.height() + 10)
        
        x = self.width() - margin - toast.width()
        toast.move(x, y)
        toast.show_toast(duration)
        
        self.toast_widgets.append(toast)
        # 종료 시 리스트에서 제거
        QTimer.singleShot(duration + 500, lambda: self.toast_widgets.remove(toast) if toast in self.toast_widgets else None)
        QTimer.singleShot(duration + 500, self._reposition_toasts)

    def _reposition_toasts(self: Any):
        # ?????? ??? ??? ???
        alive = []
        for toast in list(self.toast_widgets):
            try:
                toast.isVisible()
                alive.append(toast)
            except RuntimeError:
                continue
            except Exception:
                continue
        self.toast_widgets = alive

        margin = 20
        y = self.height() - margin
        
        # 위치 재조정
        for t in reversed(self.toast_widgets):
            try:
                y -= t.height()
                t.move(self.width() - margin - t.width(), y)
                y -= 10
            except RuntimeError:
                continue







    def _toggle_view_mode(self: Any):
        if hasattr(self, "crawler_tab"):
            self.tabs.setCurrentWidget(self.crawler_tab)
            self.crawler_tab._toggle_view_mode()
            return
        ui_logger.warning("CrawlerTab unavailable for _toggle_view_mode.")
        
    def show_notification(self: Any, title: str, message: str):
        """시스템 트레이 알림 표시"""
        if (
            settings.get("show_notifications", True)
            and NOTIFICATION_AVAILABLE
            and notification is not None
            and hasattr(notification, "notify")
        ):
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name=APP_TITLE,
                    app_icon=None,  # 아이콘 경로 설정 가능
                    timeout=5
                )
            except Exception as e:
                ui_logger.warning(f"알림 표시 실패: {e}")

    def _show_recently_viewed_dialog(self: Any):
        """최근 본 매물 다이얼로그 (v13.0)"""
        dlg = QDialog(self)
        dlg.setWindowTitle("🕐 최근 본 매물")
        dlg.resize(900, 600)
        
        layout = QVBoxLayout(dlg)
        
        # 안내 문구
        info = QLabel("최근에 확인한 매물 목록입니다 (최대 50개).")
        info.setStyleSheet("color: #888; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # 목록 (CardView 재사용)
        recent_items = self.recently_viewed.get_recent()
        
        if not recent_items:
            empty_lbl = QLabel("최근 본 매물이 없습니다.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty_lbl)
        else:
            card_view = CardViewWidget(is_dark=(self.current_theme=="dark"))
            card_view.set_data(recent_items)
            card_view.article_clicked.connect(
                lambda d: webbrowser.open(get_article_url(d.get("단지ID"), d.get("매물ID"), d.get("자산유형", "APT")))
            )
            card_view.favorite_toggled.connect(self._on_favorite_toggled)
            layout.addWidget(card_view)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.exec()
