"""Fluent InfoBar helpers with Toast fallback."""

from __future__ import annotations

from typing import Any, Optional


def show_info_bar(
    parent: Any,
    message: str,
    *,
    toast_type: str = "info",
    duration: int = 3000,
    title: str = "",
) -> bool:
    """Show qfluentwidgets InfoBar. Returns False if unavailable."""
    try:
        from qfluentwidgets import InfoBar, InfoBarPosition
    except Exception:
        return False
    if parent is None:
        return False

    content = str(message or "").strip()
    if not content:
        return False

    kind = str(toast_type or "info").lower()
    factory = {
        "success": InfoBar.success,
        "error": InfoBar.error,
        "warning": InfoBar.warning,
        "info": InfoBar.info,
    }.get(kind, InfoBar.info)

    bar_title = title or {
        "success": "완료",
        "error": "오류",
        "warning": "주의",
        "info": "알림",
    }.get(kind, "알림")

    try:
        factory(
            bar_title,
            content,
            duration=max(800, int(duration)),
            position=InfoBarPosition.TOP_RIGHT,
            parent=parent,
        )
        return True
    except Exception:
        return False
