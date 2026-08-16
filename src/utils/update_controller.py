"""Qt bridge that keeps network update work off the GUI thread."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from src.utils.update_installer import download_verified_artifact, launch_update_helper
from src.utils.update_manifest import NoUpdateAvailableError, ReleaseManifest, download_release_manifest, verify_release_manifest
from src.utils.version import APP_VERSION, UPDATE_MANIFEST_URL, UPDATE_PUBLIC_KEY_B64


class UpdateController(QObject):
    update_available = pyqtSignal(object)
    no_update = pyqtSignal()
    failed = pyqtSignal(str)
    downloaded = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(UPDATE_MANIFEST_URL and UPDATE_PUBLIC_KEY_B64)

    def check(self) -> bool:
        if not self.configured:
            self.failed.emit("업데이트 채널이 아직 설정되지 않았습니다.")
            return False
        with self._lock:
            if self._busy: return False
            self._busy = True
        def worker():
            try:
                manifest = verify_release_manifest(download_release_manifest(UPDATE_MANIFEST_URL), public_key_b64=UPDATE_PUBLIC_KEY_B64, current_version=APP_VERSION)
            except NoUpdateAvailableError:
                self.no_update.emit()
            except Exception as exc:
                self.failed.emit(str(exc))
            else:
                self.update_available.emit(manifest)
            finally:
                with self._lock: self._busy = False
        threading.Thread(target=worker, name="UpdateCheck", daemon=True).start()
        return True

    def download(self, manifest: ReleaseManifest) -> bool:
        if not getattr(sys, "frozen", False):
            self.failed.emit("개발 실행에서는 자동 설치를 사용할 수 없습니다.")
            return False
        with self._lock:
            if self._busy: return False
            self._busy = True
        def worker():
            try: self.downloaded.emit(manifest, download_verified_artifact(manifest))
            except Exception as exc: self.failed.emit(str(exc))
            finally:
                with self._lock: self._busy = False
        threading.Thread(target=worker, name="UpdateDownload", daemon=True).start()
        return True

    @staticmethod
    def apply(staged: Path, manifest: ReleaseManifest) -> None:
        launch_update_helper(target=Path(sys.executable).resolve(), staged=staged, manifest=manifest, parent_pid=os.getpid())


import os  # kept below Qt imports to avoid altering packaged Qt startup
