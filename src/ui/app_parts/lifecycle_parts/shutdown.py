from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleShutdownMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
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
        # Ensure process-wide crawl mutex never sticks after forced exit paths.
        try:
            from src.core.crawl_lock import get_crawl_lock

            get_crawl_lock().force_release()
        except Exception as lock_exc:
            ui_logger.debug(f"crawl_lock force_release 무시: {lock_exc}")
        if hasattr(self, "schedule_timer") and self.schedule_timer:
            self.schedule_timer.stop()
        # ISSUE-005: stop the OS-theme watcher poll so it cannot outlive shutdown.
        _timer_owners = [self]
        try:
            _timer_owners.append(QApplication.instance())
        except Exception:
            pass
        for _timer_owner in _timer_owners:
            try:
                _theme_timer = getattr(_timer_owner, "_theme_watcher_timer", None)
                if _theme_timer is not None:
                    _theme_timer.stop()
            except Exception as theme_exc:
                ui_logger.debug(f"테마 watcher 정리 무시: {theme_exc}")
        # ISSUE-005: wait briefly for update check/download workers.
        _update_controller = getattr(self, "_update_controller", None)
        if _update_controller is not None:
            try:
                _update_controller.wait_idle(timeout=5.0)
            except Exception as update_exc:
                ui_logger.debug(f"업데이트 워커 대기 무시: {update_exc}")
        settings.set("window_geometry", [self.x(), self.y(), self.width(), self.height()])
        try:
            for _tab_name in ("crawler_tab", "geo_tab"):
                try:
                    _tab = getattr(self, _tab_name, None)
                    _cache = getattr(_tab, "crawl_cache", None)
                    if _cache is not None and hasattr(_cache, "flush"):
                        _cache.flush()
                except Exception as cache_exc:
                    ui_logger.debug(f"캐시 flush 무시: {cache_exc}")
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
