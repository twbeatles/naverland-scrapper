import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def _sha_size(data: bytes) -> tuple[str, int]:
    return hashlib.sha256(data).hexdigest(), len(data)


def _setup_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, target_data: bytes | None, staged_data: bytes | None, backup_data: bytes | None = None
) -> dict[str, Any]:
    """Create root/target/staged/helper/ticket for apply_update tests."""
    root = tmp_path / "updates"
    root.mkdir(parents=True, exist_ok=True)
    install_dir = tmp_path / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(update_installer, "staging_root", lambda: root)

    target = install_dir / "app.exe"
    if target_data is not None:
        target.write_bytes(target_data)
    else:
        if target.exists():
            target.unlink()

    staged = root / "staged-new.exe"
    if staged_data is not None:
        staged.write_bytes(staged_data)
    sha, size = _sha_size(staged_data or b"")

    backup = update_installer.backup_path_for(target)
    if backup_data is not None:
        backup.write_bytes(backup_data)

    helper = root / "update-helper-current.exe"
    helper.write_bytes(b"helper")
    monkeypatch.setattr(sys, "executable", str(helper))

    token = "b" * 32
    ticket = root / f"update-{token}.json"
    ticket.write_text(
        json.dumps({"token": token, "target": str(target), "staged": str(staged), "sha256": sha, "size": size}),
        encoding="utf-8",
    )

    # Parent already exited: skip the 45s wait.
    monkeypatch.setattr(os, "kill", lambda pid, sig: (_ for _ in ()).throw(OSError("no such process")))

    return {"root": root, "target": target, "staged": staged, "backup": backup, "helper": helper, "token": token}


def _mock_success_processes(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    seen: dict[str, list] = {"run": [], "popen": []}

    class Completed:
        returncode = 0

    def fake_run(*args, **kwargs):
        seen["run"].append({"args": args, "kwargs": kwargs})
        return Completed()

    def fake_popen(*args, **kwargs):
        seen["popen"].append({"args": args, "kwargs": kwargs})

        class Proc:
            pid = 1234

        return Proc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    return seen


def test_clean_bootloader_env_strips_pyinstaller_vars():
    base = {
        "_MEIPASS2": "/tmp/parent",
        "_MEI_TMP": "/tmp/x",
        "_PYI_ARCHIVE_FILE": "/tmp/a",
        "_PYI_PARENT_PROCESS_LEVEL": "1",
        "_PYINSTALLER_ARCHIVE": "y",
        "PATH": "/usr/bin",
        "NAVERLAND_DATA_DIR": "/data",
    }
    cleaned = update_installer.clean_bootloader_env(base)
    assert "PATH" in cleaned and "NAVERLAND_DATA_DIR" in cleaned
    for key in cleaned:
        assert not key.upper().startswith(("_MEI", "_PYI", "_PYINSTALLER"))


def test_apply_update_uses_two_renames_without_copy_overwrite(tmp_path, monkeypatch):
    ctx = _setup_apply(tmp_path, monkeypatch, target_data=b"old-build", staged_data=b"new-build")
    _mock_success_processes(monkeypatch)

    calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def recording_replace(src, dst, *args, **kwargs):
        calls.append((str(src), str(dst)))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", recording_replace)

    copied: list[tuple[str, str]] = []
    import shutil as shutil_module

    real_copy2 = shutil_module.copy2

    def recording_copy2(src, dst, *args, **kwargs):
        copied.append((str(src), str(dst)))
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil_module, "copy2", recording_copy2)

    update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    target = ctx["target"]
    assert target.read_bytes() == b"new-build"
    # Two renames: installed -> backup, staged -> installed.
    assert calls[0] == (str(target), str(ctx["backup"]))
    assert calls[1] == (str(ctx["staged"]), str(target))
    # Installed EXE must never be copied over in place (WinError 5 path).
    assert not any(Path(dst) == ctx["backup"] and Path(src) == target for src, dst in copied)
    assert not ctx["backup"].exists()
    result = json.loads((ctx["root"] / "last-update-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "applied"


def test_apply_update_overwrites_stale_backup(tmp_path, monkeypatch):
    ctx = _setup_apply(
        tmp_path, monkeypatch, target_data=b"old-build", staged_data=b"new-build", backup_data=b"stale-backup"
    )
    # Legacy token-style leftover from the pre-fix layout must not block us.
    legacy = ctx["target"].parent / f"{ctx['target'].name}.{'c' * 32}.bak"
    legacy.write_bytes(b"legacy")
    _mock_success_processes(monkeypatch)

    update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    assert ctx["target"].read_bytes() == b"new-build"
    assert not ctx["backup"].exists()
    assert not legacy.exists()
    result = json.loads((ctx["root"] / "last-update-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "applied"


def test_apply_update_recovers_interrupted_swap(tmp_path, monkeypatch):
    ctx = _setup_apply(tmp_path, monkeypatch, target_data=None, staged_data=b"new-build", backup_data=b"old-build")
    assert not ctx["target"].exists()
    _mock_success_processes(monkeypatch)

    update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    assert ctx["target"].read_bytes() == b"new-build"
    assert not ctx["backup"].exists()
    result = json.loads((ctx["root"] / "last-update-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "applied"


def test_apply_update_first_move_failure_keeps_installed(tmp_path, monkeypatch):
    ctx = _setup_apply(tmp_path, monkeypatch, target_data=b"old-build", staged_data=b"new-build")
    _mock_success_processes(monkeypatch)

    real_replace = os.replace

    def failing_first_replace(src, dst, *args, **kwargs):
        if str(src) == str(ctx["target"]) and str(dst) == str(ctx["backup"]):
            raise PermissionError(13, "Access is denied")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", failing_first_replace)

    with pytest.raises(RuntimeError):
        update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    assert ctx["target"].read_bytes() == b"old-build"
    assert ctx["staged"].exists()
    result = json.loads((ctx["root"] / "last-update-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "rolled_back"


def test_apply_update_smoke_failure_restores_via_rename_even_when_overwrite_locked(
    tmp_path, monkeypatch
):
    ctx = _setup_apply(tmp_path, monkeypatch, target_data=b"old-build", staged_data=b"new-build")

    class Completed:
        returncode = 1

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Completed())
    popen_calls: list = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: popen_calls.append((a, k)) or type("P", (), {"pid": 1})())

    real_replace = os.replace

    def windows_like_replace(src, dst, *args, **kwargs):
        # Simulate Windows: overwriting an existing (just-smoked, AV-scanned)
        # EXE in place fails, but renaming either file aside succeeds.
        if str(src) == str(ctx["backup"]) and str(dst) == str(ctx["target"]) and Path(dst).exists():
            raise PermissionError(13, "Access is denied")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", windows_like_replace)

    with pytest.raises(RuntimeError, match="preflight"):
        update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    # Rollback renamed the failed build aside first, so the restore succeeded.
    assert ctx["target"].read_bytes() == b"old-build"
    assert popen_calls == []
    assert not list(ctx["target"].parent.glob(ctx["target"].name + ".failed-*"))
    result = json.loads((ctx["root"] / "last-update-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "rolled_back"


def test_child_processes_use_clean_bootloader_env(tmp_path, monkeypatch):
    ctx = _setup_apply(tmp_path, monkeypatch, target_data=b"old-build", staged_data=b"new-build")
    monkeypatch.setenv("_MEIPASS2", "/tmp/stale-parent")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "/tmp/stale-archive")
    monkeypatch.setenv("_PYINSTALLER_TEST", "1")
    seen = _mock_success_processes(monkeypatch)

    update_installer.apply_update(token=str(ctx["token"]), parent_pid=999999)

    assert seen["run"], "smoke run was not invoked"
    assert seen["popen"], "restart was not invoked"
    for entry in seen["run"] + seen["popen"]:
        env = entry["kwargs"].get("env")
        assert env is not None, "child must receive an explicit cleaned env"
        for key in env:
            assert not key.upper().startswith(("_MEI", "_PYI", "_PYINSTALLER"))


def test_launch_helper_uses_clean_bootloader_env(tmp_path, monkeypatch):
    from src.utils.update_manifest import ReleaseManifest

    root = tmp_path / "updates"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(update_installer, "staging_root", lambda: root)
    target = tmp_path / "app.exe"
    target.write_bytes(b"installed")
    staged = root / "staged.exe"
    staged.write_bytes(b"staged")
    helper_target = target.resolve()
    monkeypatch.setattr(sys, "executable", str(helper_target))
    monkeypatch.setenv("_MEIPASS2", "/tmp/stale-parent")
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "/tmp/stale-archive")

    captured: dict[str, object] = {}

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        captured["args"] = args

        class Proc:
            pid = 999

        return Proc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    manifest = ReleaseManifest(
        version="15.10",
        artifact_url="https://example.com/app.exe",
        artifact_sha256="0" * 64,
        artifact_size=6,
        expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    update_installer.launch_update_helper(target=target, staged=staged, manifest=manifest, parent_pid=1234)

    env = captured.get("env")
    assert isinstance(env, dict)
    for key in env:
        assert not key.upper().startswith(("_MEI", "_PYI", "_PYINSTALLER"))
