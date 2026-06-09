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
        self.append_log(f"📊 가격 스냅샷 {saved}건 저장", 10)
        return int(saved or 0)

    def _start_price_snapshot_worker(self: Any, items):
        worker = getattr(self, "_price_snapshot_worker", None)
        if worker is not None:
            try:
                if worker.isRunning():
                    self.append_log("⏳ 가격 스냅샷 저장이 이미 진행 중입니다.", 10)
                    return 0
            except Exception:
                pass

        worker = PriceSnapshotSaveThread(self.db, items, self)
        self._price_snapshot_worker = worker
        worker.saved_signal.connect(self._on_price_snapshot_saved)
        worker.failed_signal.connect(self._on_price_snapshot_failed)
        worker.finished.connect(lambda: setattr(self, "_price_snapshot_worker", None))
        worker.start()
        self.append_log("📊 가격 스냅샷 저장을 백그라운드에서 진행합니다.", 10)
        return 0

    def _on_price_snapshot_saved(self: Any, saved: int):
        self.append_log(f"📊 가격 스냅샷 {int(saved or 0)}건 저장", 10)

    def _on_price_snapshot_failed(self: Any, message: str):
        self.append_log(f"⚠️ 가격 스냅샷 저장 실패: {message}", 30)
