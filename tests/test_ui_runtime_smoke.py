import importlib.util
import os
import unittest


# Ensure headless-friendly Qt platform for CI runners.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIRuntimeSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._qt_app = QApplication.instance() or QApplication([])

    def test_real_estate_app_instantiation(self):
        from src.ui.app import RealEstateApp

        w = RealEstateApp()

        # Prevent background activity leaking into other tests.
        if hasattr(w, "schedule_timer") and w.schedule_timer:
            w.schedule_timer.stop()
        if hasattr(w, "tray_icon") and w.tray_icon:
            # Avoid calling close()/quit paths; they can block in headless test runs.
            w.tray_icon.hide()

        # Close DB connections explicitly (RealEstateApp.closeEvent calls this, but close can block).
        if hasattr(w, "db") and w.db:
            w.db.close()

        w.deleteLater()
        self._qt_app.processEvents()
