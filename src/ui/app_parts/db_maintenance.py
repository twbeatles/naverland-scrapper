from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppDatabaseMaintenanceMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _shutdown_active_crawlers_for_maintenance(self: Any, timeout_ms: int = 8000) -> tuple[bool, str]:
        targets = [
            ("매물 수집", getattr(self, "crawler_tab", None)),
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
        self.status_bar.showMessage(f"{self._maintenance_reason} 작업 중입니다. 끝날 때까지 잠시 기다려 주세요.")

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
        path, _ = QFileDialog.getSaveFileName(self, "데이터 백업", f"backup_{DateTimeHelper.file_timestamp()}.db", "백업 파일 (*.db)")
        if path:
            if self.db.backup_database(Path(path)):
                QMessageBox.information(self, "백업 완료", f"데이터를 백업했습니다.\n{path}")
            else:
                QMessageBox.critical(self, "백업하지 못했습니다", "데이터를 백업하지 못했습니다. 저장 위치를 바꿔 다시 시도해 주세요.")

    def _restore_db(self: Any):
        """DB 복원 - 유지보수 모드 + 안전한 UI 처리"""
        path, _ = QFileDialog.getOpenFileName(self, "백업에서 복원", "", "백업 파일 (*.db)")
        if not path:
            return
        
        # 확인 대화상자
        reply = QMessageBox.question(
            self, "백업에서 복원",
            f"지금 저장된 단지·기록·즐겨찾기가 모두 이 백업 파일의 내용으로 바뀝니다.\n"
            f"되돌릴 수 없으니, 필요하면 먼저 「데이터 백업」을 해 두세요.\n\n"
            f"복원할 파일: {path}\n\n"
            f"복원할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        timer_was_active = bool(
            hasattr(self, "schedule_timer")
            and self.schedule_timer
            and self.schedule_timer.isActive()
        )

        self._enter_maintenance_mode("데이터 복원")
        QApplication.processEvents()
        try:
            if hasattr(self, "schedule_timer") and self.schedule_timer:
                self.schedule_timer.stop()

            ok, failed_label = self._shutdown_active_crawlers_for_maintenance(timeout_ms=8000)
            if not ok:
                self.status_bar.showMessage(f"{failed_label}을(를) 멈춘 뒤 다시 복원해 주세요.")
                QMessageBox.warning(
                    self,
                    "복원하지 않았습니다",
                    f"진행 중인 {failed_label}을(를) 멈추지 못해 복원하지 않았습니다. 수집을 중지한 뒤 다시 시도해 주세요.",
                )
                ui_logger.warning(f"DB 복원 중단: {failed_label} 스레드 종료 실패")
                return

            self.status_bar.showMessage("데이터를 복원하고 있습니다…")
            QApplication.processEvents()
            ui_logger.info(f"DB 복원 시작: {path}")

            if not self.db.restore_database(Path(path)):
                self.status_bar.showMessage("데이터를 복원하지 못했습니다.")
                detail = str(getattr(self.db, "_last_restore_error", "") or "").strip()
                message = "데이터를 복원하지 못했습니다.\n백업 파일이 올바른지 확인해 주세요. 기존 데이터는 그대로입니다."
                if detail:
                    message = f"{message}\n\n{detail}"
                QMessageBox.critical(self, "복원 실패", message)
                ui_logger.error(f"DB 복원 실패: {detail or 'unknown'}")
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
            self.status_bar.showMessage("데이터를 복원했습니다.")
            QMessageBox.information(self, "복원 완료", "백업 파일의 내용으로 복원했습니다.")
            ui_logger.info("DB 복원 완료")

        except Exception as e:
            ui_logger.exception(f"DB 복원 중 예외: {e}")
            self.status_bar.showMessage("데이터를 복원하지 못했습니다.")
            QMessageBox.critical(self, "복원하지 못했습니다", f"데이터를 복원하는 중 문제가 생겼습니다.\n{e}")
        finally:
            self._exit_maintenance_mode()
            if (
                timer_was_active
                and hasattr(self, "schedule_timer")
                and self.schedule_timer
                and not self.schedule_timer.isActive()
            ):
                self.schedule_timer.start(60000)

