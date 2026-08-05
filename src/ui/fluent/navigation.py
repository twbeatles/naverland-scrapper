"""Register Fluent navigation items for the main window IA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence, TypeVar

from PyQt6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, NavigationInterface, NavigationItemPosition

_TWidget = TypeVar("_TWidget", bound=QWidget)


@dataclass(frozen=True)
class NavEntry:
    route_key: str
    text: str
    icon: Any
    position: NavigationItemPosition = NavigationItemPosition.TOP
    selectable: bool = True


# Route keys (stable objectName / navigation keys)
ROUTE_CRAWLER = "page_crawler"
ROUTE_GEO = "page_geo"
ROUTE_DB = "page_db"
ROUTE_GROUP = "page_group"
ROUTE_FAVORITES = "page_favorites"
ROUTE_DASHBOARD = "page_dashboard"
ROUTE_STATS = "page_stats"
ROUTE_HISTORY = "page_history"
ROUTE_SCHEDULE = "page_schedule"
ROUTE_GUIDE = "page_guide"
ROUTE_SETTINGS = "page_settings"


def _icon(name: str, fallback: Any = FluentIcon.APPLICATION) -> Any:
    return getattr(FluentIcon, name, fallback)


NAV_ENTRIES: Sequence[tuple[str, NavEntry | str]] = (
    # group markers use str "separator"
    ("collect", "separator"),
    (
        ROUTE_CRAWLER,
        NavEntry(ROUTE_CRAWLER, "매물 수집", _icon("HOME"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_GEO,
        NavEntry(ROUTE_GEO, "지도로 찾기", _icon("GLOBE"), NavigationItemPosition.TOP),
    ),
    ("library", "separator"),
    (
        ROUTE_DB,
        NavEntry(ROUTE_DB, "내 단지", _icon("LIBRARY"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_GROUP,
        NavEntry(ROUTE_GROUP, "단지 묶음", _icon("FOLDER"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_FAVORITES,
        NavEntry(ROUTE_FAVORITES, "즐겨찾기", _icon("HEART"), NavigationItemPosition.TOP),
    ),
    ("analyze", "separator"),
    (
        ROUTE_DASHBOARD,
        NavEntry(ROUTE_DASHBOARD, "대시보드", _icon("PIE_SINGLE"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_STATS,
        NavEntry(ROUTE_STATS, "가격 통계", _icon("MARKET"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_HISTORY,
        NavEntry(ROUTE_HISTORY, "수집 기록", _icon("HISTORY"), NavigationItemPosition.TOP),
    ),
    ("auto", "separator"),
    (
        ROUTE_SCHEDULE,
        NavEntry(ROUTE_SCHEDULE, "예약 수집", _icon("CALENDAR"), NavigationItemPosition.TOP),
    ),
    (
        ROUTE_GUIDE,
        NavEntry(ROUTE_GUIDE, "가이드", _icon("HELP"), NavigationItemPosition.BOTTOM),
    ),
    (
        ROUTE_SETTINGS,
        NavEntry(
            ROUTE_SETTINGS,
            "설정",
            _icon("SETTING"),
            NavigationItemPosition.BOTTOM,
            selectable=False,
        ),
    ),
)


def prepare_page(widget: _TWidget, route_key: str) -> _TWidget:
    """Set objectName for Fluent routing while preserving the concrete widget type."""
    widget.setObjectName(route_key)
    return widget


def register_navigation(
    nav: NavigationInterface,
    *,
    pages: dict[str, QWidget],
    on_select: Callable[[QWidget], None],
    on_settings: Optional[Callable[[], None]] = None,
) -> None:
    """Wire navigation items. ``pages`` maps route_key -> page widget."""

    first_key: Optional[str] = None
    for key, entry in NAV_ENTRIES:
        if entry == "separator":
            nav.addSeparator()
            continue
        assert isinstance(entry, NavEntry)
        page = pages.get(entry.route_key)
        if entry.route_key == ROUTE_SETTINGS:
            def _settings_click(checked=False, _cb=on_settings):
                if _cb is not None:
                    _cb()

            nav.addItem(
                routeKey=entry.route_key,
                icon=entry.icon,
                text=entry.text,
                onClick=_settings_click,
                selectable=False,
                position=entry.position,
                tooltip=entry.text,
            )
            continue
        if page is None:
            continue
        prepare_page(page, entry.route_key)

        def _make_click(w: QWidget):
            return lambda checked=False, _w=w: on_select(_w)

        nav.addItem(
            routeKey=entry.route_key,
            icon=entry.icon,
            text=entry.text,
            onClick=_make_click(page),
            selectable=entry.selectable,
            position=entry.position,
            tooltip=entry.text,
        )
        if first_key is None and entry.position == NavigationItemPosition.TOP:
            first_key = entry.route_key

    if first_key:
        nav.setCurrentItem(first_key)


def sync_nav_selection(nav: NavigationInterface, widget: QWidget | None) -> None:
    if widget is None:
        return
    key = widget.objectName()
    if key:
        try:
            nav.setCurrentItem(key)
        except Exception:
            pass
