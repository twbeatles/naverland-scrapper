from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.widgets.crawler_tab import *  # noqa: F403


class CrawlerTabSnapshotWorkerMixin:
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...

    def _save_price_snapshots(self: Any, *, async_save: bool = True):
        """크롤링 결과를 가격 스냅샷으로 저장"""
        items = [dict(item or {}) for item in (self.collected_data or []) if isinstance(item, dict)]
        if not items:
            return 0
        if async_save:
            return self._start_price_snapshot_worker(items)

        rows = build_price_snapshot_rows(items)
        saved = self.db.add_price_snapshots_bulk(rows) if rows else 0
        self.append_log(f"가격 변화 기록 {saved}건을 저장했습니다.", 10)
        return int(saved or 0)

    def _start_price_snapshot_worker(self: Any, items):
        worker = getattr(self, "_price_snapshot_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    self.append_log("가격 변화 기록을 이미 저장하는 중입니다.", 10)
                    return 0
            except Exception:
                pass

        worker = PriceSnapshotSaveThread(self.db, items, self)
        self._price_snapshot_worker = worker
        worker.saved_signal.connect(self._on_price_snapshot_saved)
        worker.failed_signal.connect(self._on_price_snapshot_failed)
        worker.finished.connect(lambda: setattr(self, "_price_snapshot_worker", None))
        worker.start()
        self.append_log("가격 변화 기록을 저장하는 중입니다.", 10)
        return 0

    def _wait_for_snapshot_worker(self: Any, timeout_ms: int = 5000) -> bool:
        # ISSUE-002: never destroy the tab while a snapshot bulk write is in
        # flight (Qt aborts on running-thread destruction, batch rolls back).
        worker = getattr(self, "_price_snapshot_worker", None)
        if worker is None:
            return True
        try:
            if not worker.isRunning():
                return True
        except Exception:
            return True
        try:
            wait_ms = max(100, int(timeout_ms))
        except (TypeError, ValueError):
            wait_ms = 5000
        try:
            finished = bool(worker.wait(wait_ms))
        except Exception:
            return True
        if not finished:
            try:
                self.append_log("가격 변화 기록 저장이 제때 끝나지 않았습니다.", 30)
            except Exception:
                pass
        return finished

    def _on_price_snapshot_saved(self: Any, saved: int):
        self.append_log(f"가격 변화 기록 {int(saved or 0)}건을 저장했습니다.", 10)

    def _on_price_snapshot_failed(self: Any, message: str):
        self.append_log(f"가격 변화 기록을 저장하지 못했습니다: {message}", 30)
