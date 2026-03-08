from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, QObject
from PyQt6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QWidget


class InputWheelGuard(QObject):
    """Prevents accidental wheel value changes on form controls."""

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        watched = a0
        event = a1
        if watched is None or event is None:
            return False
        if event.type() != QEvent.Type.Wheel:
            return False

        if isinstance(watched, QComboBox):
            view = watched.view()
            if view is not None and view.isVisible():
                return False
            event.ignore()
            return True

        if isinstance(watched, QAbstractSpinBox):
            if watched.hasFocus():
                return False
            event.ignore()
            return True

        return False


def apply_wheel_guard_recursively(root: QObject, guard: InputWheelGuard) -> None:
    for spin in root.findChildren(QAbstractSpinBox):
        spin.installEventFilter(guard)
    for combo in root.findChildren(QComboBox):
        combo.installEventFilter(guard)


def install_global_wheel_guard(app: QCoreApplication | None = None) -> InputWheelGuard:
    qt_app = app or QApplication.instance()
    if qt_app is None:
        raise RuntimeError("QApplication instance is not available")

    guard = getattr(qt_app, "_input_wheel_guard", None)
    if isinstance(guard, InputWheelGuard):
        return guard

    guard = InputWheelGuard(qt_app)
    qt_app.installEventFilter(guard)
    setattr(qt_app, "_input_wheel_guard", guard)
    return guard
