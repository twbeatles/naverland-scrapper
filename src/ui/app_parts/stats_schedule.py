"""Stats/schedule facade (SOLID split).

Single-responsibility owners live in
:mod:`src.ui.app_parts.stats_schedule_parts`:

- ``geo_assets`` — scheduled geo-sweep asset-type selection.
- ``stats_history`` — stats/history table loading and metric headers.
- ``schedule_config`` — schedule-config persistence and slot bookkeeping.
- ``schedule_run`` — schedule triggering and scheduled-run execution.
- ``group_state`` — group/complex empty- and action-state refresh.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403

from src.ui.app_parts.stats_schedule_parts.geo_assets import (
    AppStatsScheduleGeoAssetsMixin,
)
from src.ui.app_parts.stats_schedule_parts.stats_history import (
    AppStatsScheduleStatsHistoryMixin,
)
from src.ui.app_parts.stats_schedule_parts.schedule_config import (
    AppStatsScheduleConfigMixin,
)
from src.ui.app_parts.stats_schedule_parts.schedule_run import (
    AppStatsScheduleRunMixin,
)
from src.ui.app_parts.stats_schedule_parts.group_state import (
    AppStatsScheduleGroupStateMixin,
)


class AppStatsScheduleMixin(
    AppStatsScheduleGeoAssetsMixin,
    AppStatsScheduleStatsHistoryMixin,
    AppStatsScheduleConfigMixin,
    AppStatsScheduleRunMixin,
    AppStatsScheduleGroupStateMixin,
):
    SCHEDULE_CATCHUP_WINDOW_MINUTES = 10

    if TYPE_CHECKING:
        def __getattr__(self: Any, name: str) -> Any: ...
