"""Verified, recoverable installation of one-file Windows updates."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from src.utils.update_manifest import MAX_ARTIFACT_BYTES, REQUEST_TIMEOUT_SECONDS, ReleaseManifest


def staging_root() -> Path:
    from src.utils.paths import get_base_dir
    return (get_base_dir() / "updates").resolve()


def _result_path(root: Path) -> Path:
    return root / "last-update-result.json"


def _write_json(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def consume_update_result() -> dict[str, object] | None:
    root = staging_root()
    for stale in root.glob("update-helper-*.exe"):
        try: stale.unlink()
        except OSError: pass
    path = _result_path(root)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
        return result if isinstance(result, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _is_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def download_verified_artifact(manifest: ReleaseManifest) -> Path:
    root = staging_root(); root.mkdir(parents=True, exist_ok=True)
    staged = root / f"update-{manifest.version}-{uuid4().hex}.exe"
    digest = hashlib.sha256(); total = 0
    try:
        with urlopen(Request(manifest.artifact_url, headers={"User-Agent": "NaverlandScrapper-Updater"}), timeout=REQUEST_TIMEOUT_SECONDS) as response, staged.open("xb") as output:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or not final.hostname:
                raise ValueError("Artifact redirect must remain HTTPS")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > manifest.artifact_size or total > MAX_ARTIFACT_BYTES:
                    raise ValueError("Update artifact size mismatch")
                digest.update(chunk); output.write(chunk)
            output.flush(); os.fsync(output.fileno())
        if total != manifest.artifact_size or digest.hexdigest().lower() != manifest.artifact_sha256:
            raise ValueError("Update artifact integrity check failed")
        return staged
    except Exception:
        staged.unlink(missing_ok=True); raise


def discard_staged_update(staged: Path) -> None:
    if _is_child(staged, staging_root()):
        staged.unlink(missing_ok=True)


def launch_update_helper(*, target: Path, staged: Path, manifest: ReleaseManifest, parent_pid: int) -> None:
    root = staging_root(); target, staged = target.resolve(), staged.resolve()
    if not _is_child(staged, root) or target != Path(sys.executable).resolve():
        raise ValueError("Update paths are not trusted")
    token = uuid4().hex
    helper = root / f"update-helper-{token}.exe"
    ticket = root / f"update-{token}.json"
    _write_json(ticket, {"token": token, "target": str(target), "staged": str(staged), "sha256": manifest.artifact_sha256, "size": manifest.artifact_size})
    try:
        shutil.copy2(target, helper)
        subprocess.Popen([str(helper), "--apply-update", "--update-token", token, "--update-parent-pid", str(parent_pid)], close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        helper.unlink(missing_ok=True); ticket.unlink(missing_ok=True); raise


def _load_ticket(token: str) -> tuple[Path, dict[str, object]]:
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("Invalid update token")
    root = staging_root(); ticket = root / f"update-{token}.json"
    try: data = json.loads(ticket.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ValueError("Update ticket is unavailable") from exc
    if not isinstance(data, dict) or data.get("token") != token: raise ValueError("Invalid update ticket")
    return ticket, data


def _verify_staged(staged: Path, expected_sha256: str, expected_size: int) -> None:
    if staged.stat().st_size != int(expected_size): raise ValueError("Staged update size changed before installation")
    digest = hashlib.sha256()
    with staged.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    if digest.hexdigest().lower() != str(expected_sha256).lower(): raise ValueError("Staged update hash changed before installation")


def apply_update(*, token: str, parent_pid: int, smoke_timeout: int = 60) -> None:
    root = staging_root(); ticket, data = _load_ticket(token)
    target_value, staged_value, sha_value, size_value = data.get("target"), data.get("staged"), data.get("sha256"), data.get("size")
    if not isinstance(target_value, str) or not isinstance(staged_value, str) or not isinstance(sha_value, str) or not isinstance(size_value, int):
        raise ValueError("Invalid update ticket")
    target, staged = Path(target_value).resolve(), Path(staged_value).resolve()
    helper = Path(sys.executable).resolve()
    if helper.parent != root or not _is_child(staged, root) or target.suffix.lower() != ".exe" or not target.is_file() or not staged.is_file():
        raise ValueError("Invalid update paths")
    _verify_staged(staged, sha_value, size_value)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try: os.kill(parent_pid, 0)
        except OSError: break
        time.sleep(.2)
    else: raise TimeoutError("Application did not exit before update")
    backup = target.with_name(f"{target.name}.{token}.bak")
    status: dict[str, object] = {"version": staged.name, "backup": str(backup)}
    shutil.copy2(target, backup)
    try:
        os.replace(staged, target)
        smoke = subprocess.run([str(target), "--preflight"], timeout=smoke_timeout, check=False, capture_output=True)
        if smoke.returncode != 0: raise RuntimeError(f"Updated executable preflight failed ({smoke.returncode})")
        subprocess.Popen([str(target)], close_fds=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        status["status"] = "applied"
    except Exception as exc:
        if backup.exists(): os.replace(backup, target)
        status.update(status="rolled_back", error=str(exc))
        raise
    finally:
        _write_json(_result_path(root), status)
        ticket.unlink(missing_ok=True)
    if backup.exists(): backup.unlink(missing_ok=True)
