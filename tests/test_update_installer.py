from pathlib import Path

import pytest

from src.utils import update_installer


def test_discard_staged_update_rejects_paths_outside_staging(tmp_path, monkeypatch):
    root = tmp_path / "updates"
    monkeypatch.setattr(update_installer, "staging_root", lambda: root)
    outside = tmp_path / "outside.exe"
    outside.write_bytes(b"keep")

    update_installer.discard_staged_update(outside)

    assert outside.exists()


def test_apply_update_rejects_unknown_token(tmp_path, monkeypatch):
    monkeypatch.setattr(update_installer, "staging_root", lambda: Path(tmp_path))

    with pytest.raises(ValueError, match="ticket"):
        update_installer.apply_update(token="a" * 32, parent_pid=1)
