"""Backward-compatible re-export module.

Legacy imports from ``src.ui.widgets.dialogs`` are redirected to
``src.ui.dialogs`` to keep a single implementation source.
"""

from src.ui.dialogs import (
    PresetDialog,
    SettingsDialog,
    AlertSettingDialog,
    ShortcutsDialog,
    AdvancedFilterDialog,
    MultiSelectDialog,
    URLBatchDialog,
    ExcelTemplateDialog,
    AboutDialog,
    RecentSearchDialog,
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
