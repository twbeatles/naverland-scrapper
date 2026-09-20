"""Lifecycle facade (SOLID split).

Single-responsibility owners live in
:mod:`src.ui.app_parts.lifecycle_parts`:

- ``bootstrap`` — window construction and initial data load.
- ``menu`` — menu bar, about/shortcuts dialogs and view switching.
- ``updates`` — update-controller wiring and event handlers.
- ``shortcuts_actions`` — keyboard shortcuts and save/crawl actions.
- ``tray`` — system-tray wiring and minimize/restore.
- ``timers_events`` — timer setup and crawl/alert/dashboard events.
- ``notify`` — toast and desktop-notification helpers.
- ``shutdown`` — graceful shutdown and close-event handling.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403

from src.ui.app_parts.lifecycle_parts.bootstrap import AppLifecycleBootstrapMixin
from src.ui.app_parts.lifecycle_parts.menu import AppLifecycleMenuMixin
from src.ui.app_parts.lifecycle_parts.updates import AppLifecycleUpdatesMixin
from src.ui.app_parts.lifecycle_parts.shortcuts_actions import (
    AppLifecycleShortcutsActionsMixin,
)
from src.ui.app_parts.lifecycle_parts.tray import AppLifecycleTrayMixin
from src.ui.app_parts.lifecycle_parts.timers_events import AppLifecycleTimersEventsMixin
from src.ui.app_parts.lifecycle_parts.notify import AppLifecycleNotifyMixin
from src.ui.app_parts.lifecycle_parts.shutdown import AppLifecycleShutdownMixin


class AppLifecycleMixin(
    AppLifecycleBootstrapMixin,
    AppLifecycleMenuMixin,
    AppLifecycleUpdatesMixin,
    AppLifecycleShortcutsActionsMixin,
    AppLifecycleTrayMixin,
    AppLifecycleTimersEventsMixin,
    AppLifecycleNotifyMixin,
    AppLifecycleShutdownMixin,
):
    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...
