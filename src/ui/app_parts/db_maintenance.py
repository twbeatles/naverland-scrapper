from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppDatabaseMaintenanceMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _shutdown_active_crawlers_for_maintenance(self: Any, timeout_ms: int = 8000) -> tuple[bool, str]:
        targets = [
            ("크롤링", getattr(self, "crawler_tab", None)),
            ("지도 탐색", getattr(self, "geo_tab", None)),
        ]
        for label, tab in targets:
            if tab is None:
                continue
            try:
                ok = bool(tab.shutdown_crawl(timeout_ms=timeout_ms))
            except Exception:
                ok = False
            if not ok:
                return False, label
        return True, ""

    def _enter_maintenance_mode(self: Any, reason: str):
        if self._maintenance_mode:
            return
        self._maintenance_mode = True
        self._maintenance_reason = str(reason or "").strip() or "유지보수"
        self._maintenance_enabled_snapshot = []

        targets = [self.tabs]
        crawler_tab = getattr(self, "crawler_tab", None)
        if crawler_tab is not None:
            targets.extend(
                [
                    crawler_tab.btn_start,
                    crawler_tab.btn_save,
                    crawler_tab.btn_advanced_filter,
                    crawler_tab.btn_clear_advanced_filter,
                ]
            )
        geo_tab = getattr(self, "geo_tab", None)
        if geo_tab is not None:
            targets.extend(
                [
                    geo_tab.btn_start,
                    geo_tab.btn_save,
                ]
            )
        for action_name in (
            "action_backup_db",
            "action_restore_db",
            "action_settings",
            "action_save_preset",
            "action_load_preset",
            "action_advanced_filter",
            "action_clear_advanced_filter",
        ):
            action = getattr(self, action_name, None)
            if action is not None:
                targets.append(action)

        for target in targets:
            try:
                enabled = bool(target.isEnabled())
                self._maintenance_enabled_snapshot.append((target, enabled))
                target.setEnabled(False)
            except Exception:
                continue
        self.status_bar.showMessage(f"🛠️ 유지보수 모드: {self._maintenance_reason}")

    def _exit_maintenance_mode(self: Any):
        if not self._maintenance_mode:
            return
        for target, was_enabled in self._maintenance_enabled_snapshot:
            try:
                target.setEnabled(bool(was_enabled))
            except Exception:
                continue
        self._maintenance_enabled_snapshot = []
        self._maintenance_mode = False
        self._maintenance_reason = ""
    
    def _backup_db(self: Any):
        path, _ = QFileDialog.getSaveFileName(self, "DB 백업", f"backup_{DateTimeHelper.file_timestamp()}.db", "Database (*.db)")
        if path:
            if self.db.backup_database(Path(path)):
                QMessageBox.information(self, "백업 완료", f"DB 백업 완료!\n{path}")
            else:
                QMessageBox.critical(self, "실패", "DB 백업에 실패했습니다.")

    def _restore_db(self: Any):
        """DB 복원 - 유지보수 모드 + 안전한 UI 처리"""
        path, _ = QFileDialog.getOpenFileName(self, "DB 복원", "", "Database (*.db)")
        if not path:
            return
        
        # 확인 대화상자
        reply = QMessageBox.question(
            self, "DB 복원 확인",
            f"현재 DB를 선택한 파일로 교체합니다.\n\n"
            f"복원 파일: {path}\n\n"
            f"계속하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        timer_was_active = bool(
            hasattr(self, "schedule_timer")
            and self.schedule_timer
            and self.schedule_timer.isActive()
        )

        self._enter_maintenance_mode("DB 복원")
        QApplication.processEvents()
        try:
            if hasattr(self, "schedule_timer") and self.schedule_timer:
                self.schedule_timer.stop()

            ok, failed_label = self._shutdown_active_crawlers_for_maintenance(timeout_ms=8000)
            if not ok:
                self.status_bar.showMessage(f"⚠️ {failed_label} 종료 후 다시 DB 복원을 시도하세요.")
                QMessageBox.warning(
                    self,
                    "복원 중단",
                    f"진행 중인 {failed_label} 작업을 안전하게 종료하지 못해 DB 복원을 중단했습니다.",
                )
                ui_logger.warning(f"DB 복원 중단: {failed_label} 스레드 종료 실패")
                return

            self.status_bar.showMessage("🔄 DB 복원 중...")
            QApplication.processEvents()
            ui_logger.info(f"DB 복원 시작: {path}")

            if not self.db.restore_database(Path(path)):
                self.status_bar.showMessage("❌ DB 복원 실패")
                QMessageBox.critical(self, "복원 실패", "DB 복원에 실패했습니다.\n콘솔 로그를 확인하세요.")
                ui_logger.error("DB 복원 실패")
                return

            ui_logger.info("DB 복원 성공, 데이터 다시 로드 중...")
            for key in self._noncritical_loaded:
                self._noncritical_loaded[key] = False
            self._load_initial_data()
            db_tab = getattr(self, "db_tab", None)
            if db_tab is not None:
                db_tab.load_data()
            group_tab = getattr(self, "group_tab", None)
            if group_tab is not None:
                group_tab.load_groups()
            self._refresh_tab(self.tabs.currentIndex())
            self.status_bar.showMessage("✅ DB 복원 완료!")
            QMessageBox.information(self, "복원 완료", "DB 복원이 완료되었습니다!")
            ui_logger.info("DB 복원 완료")

        except Exception as e:
            ui_logger.exception(f"DB 복원 중 예외: {e}")
            self.status_bar.showMessage("❌ DB 복원 중 오류 발생")
            QMessageBox.critical(self, "오류", f"DB 복원 중 오류가 발생했습니다:\n{e}")
        finally:
            self._exit_maintenance_mode()
            if (
                timer_was_active
                and hasattr(self, "schedule_timer")
                and self.schedule_timer
                and not self.schedule_timer.isActive()
            ):
                self.schedule_timer.start(60000)

