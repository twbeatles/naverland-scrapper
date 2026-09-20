from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppLifecycleUpdatesMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _init_update_controller(self: Any):
        self._update_controller = UpdateController(self)
        self._update_controller.update_available.connect(self._on_update_available)
        self._update_controller.no_update.connect(self._on_no_update)
        self._update_controller.failed.connect(self._on_update_failed)
        self._update_controller.downloaded.connect(self._on_update_downloaded)
        self.menuBar().addAction("업데이트 확인", self._check_for_updates)
        self._notify_update_result()

    def _notify_update_result(self: Any):
        try:
            from src.utils.update_installer import consume_update_result
            result = consume_update_result()
        except Exception:
            return
        if not result:
            return
        if result.get("status") == "applied":
            self.status_bar.showMessage("이전 실행에서 업데이트를 완료했습니다.", 6000)
            return
        QMessageBox.warning(self, "업데이트", f"업데이트 적용에 실패해 이전 버전으로 복원했습니다.\n\n{result.get('error', '')}")

    def _check_for_updates(self: Any):
        if self._update_controller.check():
            self.status_bar.showMessage("업데이트를 확인하는 중입니다...")

    def _on_no_update(self: Any):
        self.status_bar.showMessage("현재 최신 버전을 사용 중입니다.", 5000)
        QMessageBox.information(self, "업데이트", "현재 최신 버전을 사용 중입니다.")

    def _on_update_failed(self: Any, error: str):
        self.status_bar.showMessage(f"업데이트 실패: {error}", 8000)
        QMessageBox.warning(self, "업데이트", f"업데이트를 완료하지 못했습니다.\n\n{error}")

    def _on_update_available(self: Any, manifest: Any):
        reply = QMessageBox.question(self, "업데이트 발견", f"새 버전 {manifest.version}이 있습니다.\n현재 버전: {APP_VERSION}\n\n다운로드 후 설치하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes and self._update_controller.download(manifest):
            self.status_bar.showMessage(f"업데이트 {manifest.version} 다운로드 중...")

    def _on_update_downloaded(self: Any, manifest: Any, staged: Any):
        reply = QMessageBox.question(self, "업데이트 검증 완료", f"업데이트 {manifest.version}의 서명과 파일 무결성을 확인했습니다. 지금 설치하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            from src.utils.update_installer import discard_staged_update
            discard_staged_update(staged)
            return
        if not self._shutdown():
            from src.utils.update_installer import discard_staged_update
            discard_staged_update(staged)
            QMessageBox.warning(self, "업데이트", "실행 중인 수집 작업을 종료하지 못해 업데이트를 취소했습니다.")
            return
        try:
            self._update_controller.apply(staged, manifest)
        except Exception as exc:
            self._on_update_failed(f"업데이트 설치를 시작할 수 없습니다: {exc}")
            return
        QApplication.quit()
