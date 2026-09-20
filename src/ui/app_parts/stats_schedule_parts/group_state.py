from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import *  # noqa: F403


class AppStatsScheduleGroupStateMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
    def _update_group_empty_state(self: Any):
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_empty_label"):
            self.group_empty_label.setVisible(not has_groups)
        self.group_list.setEnabled(has_groups)
        if not has_groups:
            self.group_complex_table.setRowCount(0)
            self._update_group_complex_empty_state(0)

    def _update_group_action_state(self: Any):
        has_selection = self.group_list.currentRow() >= 0
        has_groups = self.group_list.count() > 0
        if hasattr(self, "group_btn_delete"):
            self.group_btn_delete.setEnabled(has_selection)
        if hasattr(self, "group_btn_add"):
            self.group_btn_add.setEnabled(has_groups)
        if hasattr(self, "group_btn_add_multi"):
            self.group_btn_add_multi.setEnabled(has_groups)
        if not has_groups:
            if hasattr(self, "group_btn_remove"):
                self.group_btn_remove.setEnabled(False)

    def _update_group_complex_empty_state(self: Any, count):
        is_empty = count == 0
        if hasattr(self, "group_complex_empty_label"):
            self.group_complex_empty_label.setVisible(is_empty)
        self.group_complex_table.setEnabled(not is_empty)

    def _update_group_complex_action_state(self: Any):
        has_selection = self.group_complex_table.currentRow() >= 0
        if hasattr(self, "group_btn_remove"):
            self.group_btn_remove.setEnabled(has_selection)

    def _update_schedule_state(self: Any):
        mode = str(self.schedule_mode_combo.currentData() or "complex")
        has_groups = self.schedule_group_combo.count() > 0
        can_run = mode == "geo_sweep" or has_groups
        self.check_schedule.setEnabled(can_run)
        self.time_edit.setEnabled(can_run)
        self.schedule_mode_combo.setEnabled(True)
        self.schedule_group_combo.setEnabled(mode == "complex" and has_groups)
        self.schedule_geo_lat.setEnabled(mode == "geo_sweep")
        self.schedule_geo_lon.setEnabled(mode == "geo_sweep")
        if hasattr(self, "schedule_empty_label"):
            self.schedule_empty_label.setVisible(mode == "complex" and not has_groups)
