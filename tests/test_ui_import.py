import importlib.util
import unittest


@unittest.skipIf(importlib.util.find_spec("PyQt6") is None, "PyQt6 is not installed")
class TestUIImport(unittest.TestCase):
    def test_ui_app_module_importable(self):
        __import__("src.ui.app")
