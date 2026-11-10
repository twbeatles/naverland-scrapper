"""Backward-compatible re-export module.

Legacy imports from ``src.ui.widgets.dialogs`` are redirected to
``src.ui.dialogs`` to keep a single implementation source.
"""

from src.ui.dialogs import (
    AboutDialog,
    AdvancedFilterDialog,
    AlertSettingDialog,
    ExcelTemplateDialog,
    MultiSelectDialog,
    PresetDialog,
    RecentSearchDialog,
    SettingsDialog,
    ShortcutsDialog,
    URLBatchDialog,
)

__all__ = [
    "PresetDialog",
    "SettingsDialog",
    "AlertSettingDialog",
    "ShortcutsDialog",
    "AdvancedFilterDialog",
    "MultiSelectDialog",
    "URLBatchDialog",
    "ExcelTemplateDialog",
    "AboutDialog",
    "RecentSearchDialog",
]
