"""Facade parity for the SOLID _parts/ splits.

Each long module was split into single-responsibility part packages with the
original path kept as a facade. These tests pin the contract:

- every public name of the original module is still importable from it, and
- each composed mixin actually inherits all of its part mixins, so no method
  is dropped by the split.
"""
import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestDetailFetcherFacade(unittest.TestCase):
    def test_facade_reexports_part_surface(self):
        import ast

        import src.core.services.detail_fetcher as facade

        part_names = (
            "apply", "artifacts", "detail_parse", "field_keys",
            "field_merge", "front_api", "hydration", "money",
            "orchestrator", "page_primitives", "text_extract",
        )
        expected = set()
        base = os.path.join("src", "core", "services", "detail_fetcher_parts")
        for part in part_names:
            tree = ast.parse(open(os.path.join(base, part + ".py"),
                                  encoding="utf-8").read())
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                    expected.add(node.name)
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            expected.add(target.id)
        live = set(facade.__all__)
        self.assertEqual(live, expected)
        for name in live:
            self.assertTrue(hasattr(facade, name), name)

    def test_orchestrator_entry_points_are_identical_objects(self):
        import src.core.services.detail_fetcher as facade
        from src.core.services.detail_fetcher_parts import orchestrator
        from src.core.services.detail_fetcher_parts import apply as apply_part

        self.assertIs(facade.fetch_mobile_article_detail,
                      orchestrator.fetch_mobile_article_detail)
        self.assertIs(facade.apply_mobile_detail, apply_part.apply_mobile_detail)


class TestManagersFacade(unittest.TestCase):
    def test_facade_reexports_part_surface(self):
        import src.core.managers as facade
        from src.core.managers_parts import schedule_defaults, settings_manager

        for name in facade.__all__:
            self.assertTrue(hasattr(facade, name), name)
        # singleton identity must be preserved for `patch("src.core.managers.settings")`
        self.assertIs(facade.settings, settings_manager.settings)
        self.assertIs(facade.DEFAULT_SETTINGS,
                      schedule_defaults.DEFAULT_SETTINGS)

    def test_manager_classes_live_in_dedicated_parts(self):
        from src.core.managers_parts.filter_preset import FilterPresetManager
        from src.core.managers_parts.recently_viewed import RecentlyViewedManager
        from src.core.managers_parts.search_history import SearchHistoryManager
        from src.core.managers_parts.settings_manager import SettingsManager
        import src.core.managers as facade

        self.assertIs(facade.SettingsManager, SettingsManager)
        self.assertIs(facade.FilterPresetManager, FilterPresetManager)
        self.assertIs(facade.SearchHistoryManager, SearchHistoryManager)
        self.assertIs(facade.RecentlyViewedManager, RecentlyViewedManager)


class TestMixinComposition(unittest.TestCase):
    def test_coercion_composes_all_parts(self):
        from src.core.database_parts.coercion import ComplexDatabaseCoercionMixin
        from src.core.database_parts.coercion_parts.recovery import (
            ComplexDatabaseRecoveryMixin,
        )
        from src.core.database_parts.coercion_parts.schema_normalize import (
            ComplexDatabaseSchemaNormalizeMixin,
        )
        from src.core.database_parts.coercion_parts.value_coerce import (
            ComplexDatabaseValueCoerceMixin,
        )

        for part in (ComplexDatabaseRecoveryMixin,
                     ComplexDatabaseSchemaNormalizeMixin,
                     ComplexDatabaseValueCoerceMixin):
            self.assertTrue(issubclass(ComplexDatabaseCoercionMixin, part),
                            part.__name__)

    def test_stats_schedule_composes_all_parts(self):
        from src.ui.app_parts.stats_schedule import AppStatsScheduleMixin
        from src.ui.app_parts.stats_schedule_parts import (
            geo_assets,
            group_state,
            schedule_config,
            schedule_run,
            stats_history,
        )

        for part in (geo_assets.AppStatsScheduleGeoAssetsMixin,
                     stats_history.AppStatsScheduleStatsHistoryMixin,
                     schedule_config.AppStatsScheduleConfigMixin,
                     schedule_run.AppStatsScheduleRunMixin,
                     group_state.AppStatsScheduleGroupStateMixin):
            self.assertTrue(issubclass(AppStatsScheduleMixin, part), part.__name__)
        self.assertEqual(AppStatsScheduleMixin.SCHEDULE_CATCHUP_WINDOW_MINUTES, 10)

    def test_lifecycle_composes_all_parts(self):
        from src.ui.app_parts.lifecycle import AppLifecycleMixin
        from src.ui.app_parts.lifecycle_parts import (
            bootstrap,
            menu,
            notify,
            shortcuts_actions,
            shutdown,
            timers_events,
            tray,
            updates,
        )

        for part in (bootstrap.AppLifecycleBootstrapMixin,
                     menu.AppLifecycleMenuMixin,
                     updates.AppLifecycleUpdatesMixin,
                     shortcuts_actions.AppLifecycleShortcutsActionsMixin,
                     tray.AppLifecycleTrayMixin,
                     timers_events.AppLifecycleTimersEventsMixin,
                     notify.AppLifecycleNotifyMixin,
                     shutdown.AppLifecycleShutdownMixin):
            self.assertTrue(issubclass(AppLifecycleMixin, part), part.__name__)


if __name__ == "__main__":
    unittest.main()
