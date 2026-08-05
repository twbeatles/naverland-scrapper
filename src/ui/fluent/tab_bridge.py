"""QTabWidget-compatible facade over QStackedWidget + Fluent navigation."""

from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QStackedWidget, QWidget


class TabCompatBridge(QObject):
    """Minimal QTabWidget API used across app mixins and tests.

    Existing code calls ``tabs.addTab``, ``setCurrentWidget``, ``currentIndex``,
    and ``currentChanged``. The real chrome is Fluent ``NavigationInterface``.
    """

    currentChanged = pyqtSignal(int)

    def __init__(
        self,
        stack: QStackedWidget,
        *,
        on_switch: Optional[Callable[[QWidget], None]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._stack = stack
        self._on_switch = on_switch
        self._widgets: list[QWidget] = []
        self._labels: list[str] = []
        self._block_signal = False
        self._stack.currentChanged.connect(self._emit_current_changed)

    # ── QTabWidget-like API ──────────────────────────────────────────

    def addTab(self, widget: QWidget, label: str = "") -> int:
        if widget is None:
            raise ValueError("widget is required")
        if widget in self._widgets:
            return self._widgets.index(widget)
        self._widgets.append(widget)
        self._labels.append(str(label or ""))
        if self._stack.indexOf(widget) < 0:
            self._stack.addWidget(widget)
        return len(self._widgets) - 1

    def widget(self, index: int) -> Any:
        # Return Any so callers (tests/mixins) keep concrete page attribute access
        # under pyright, matching the dynamic nature of tab pages.
        if index is None or index < 0 or index >= len(self._widgets):
            return None
        return self._widgets[index]

    def indexOf(self, widget: QWidget) -> int:
        try:
            return self._widgets.index(widget)
        except ValueError:
            return -1

    def count(self) -> int:
        return len(self._widgets)

    def currentIndex(self) -> int:
        w = self._stack.currentWidget()
        if w is None:
            return -1
        try:
            return self._widgets.index(w)
        except ValueError:
            return self._stack.currentIndex()

    def currentWidget(self) -> Any:
        return self._stack.currentWidget()

    def setCurrentIndex(self, index: int) -> None:
        w = self.widget(index)
        if w is not None:
            self.setCurrentWidget(w)

    def setCurrentWidget(self, widget: QWidget) -> None:
        if widget is None:
            return
        if self._stack.indexOf(widget) < 0:
            self._stack.addWidget(widget)
        if self._on_switch is not None:
            try:
                self._on_switch(widget)
            except Exception:
                pass
        self._stack.setCurrentWidget(widget)

    def setEnabled(self, enabled: bool) -> None:
        self._stack.setEnabled(bool(enabled))

    def isEnabled(self) -> bool:
        return bool(self._stack.isEnabled())

    # ── helpers ──────────────────────────────────────────────────────

    def _emit_current_changed(self, stack_index: int) -> None:
        if self._block_signal:
            return
        w = self._stack.widget(stack_index)
        try:
            idx = self._widgets.index(w) if w is not None else -1
        except ValueError:
            idx = stack_index
        self.currentChanged.emit(idx)

    def label(self, index: int) -> str:
        if 0 <= index < len(self._labels):
            return self._labels[index]
        return ""
