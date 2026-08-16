from __future__ import annotations

import json
import os
from threading import RLock
from pathlib import Path
from typing import Any, Callable

from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

_WRITE_LOCK = RLock()


def backup_broken_json(path: Path, *, label: str = "json") -> Path | None:
    try:
        suffix = DateTimeHelper.now_string().replace(":", "").replace(" ", "_")
        backup_path = path.with_suffix(path.suffix + f".broken.{label}.{suffix}")
        path.replace(backup_path)
        return backup_path
    except OSError:
        return None


def atomic_write_json(path: Path, payload: Any) -> None:
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{os.getpid()}.{id(payload)}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def load_json_with_recovery(
    path: Path,
    *,
    default_factory: Callable[[], Any],
    logger_name: str,
    label: str,
) -> Any:
    logger = get_logger(logger_name)
    if not path.exists():
        return default_factory()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        backup = backup_broken_json(path, label=label)
        logger.warning(f"{label} 로드 실패, 기본값으로 복구합니다: {e}")
        if backup:
            logger.warning(f"손상된 {label} 파일 백업: {backup}")
        return default_factory()
