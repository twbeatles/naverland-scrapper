"""Keep GUI/runtime tests away from the developer's saved application data.

Collection-time imports get a session sandbox; each test then gets its own
sandbox. This also survives path tests that reload/reset the paths module.
"""
import os
import tempfile
from pathlib import Path

import pytest


_SESSION_ROOT = Path(tempfile.mkdtemp(prefix="naverland-pytest-session-"))
_ORIGINAL_DATA_DIR = os.environ.get("NAVERLAND_DATA_DIR")


def pytest_configure(config):
    from src.utils.paths import configure_paths, bootstrap_runtime_paths

    os.environ["NAVERLAND_DATA_DIR"] = str(_SESSION_ROOT)
    configure_paths(_SESSION_ROOT)
    bootstrap_runtime_paths()


@pytest.fixture(autouse=True)
def isolated_runtime_data(tmp_path, monkeypatch):
    from src.utils.paths import configure_paths
    from src.core.managers import SettingsManager

    monkeypatch.setenv("NAVERLAND_DATA_DIR", str(tmp_path))
    configure_paths(tmp_path)
    SettingsManager.reset_for_tests()
    try:
        yield
    finally:
        SettingsManager.reset_for_tests()
        configure_paths(_SESSION_ROOT)


def pytest_unconfigure(config):
    if _ORIGINAL_DATA_DIR is None:
        os.environ.pop("NAVERLAND_DATA_DIR", None)
    else:
        os.environ["NAVERLAND_DATA_DIR"] = _ORIGINAL_DATA_DIR
