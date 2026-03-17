from __future__ import annotations

import os
import sys
from pathlib import Path


def _iter_browser_path_candidates() -> list[Path]:
    if not getattr(sys, "frozen", False):
        return []

    executable_dir = Path(sys.executable).resolve().parent
    base_path = Path(getattr(sys, "_MEIPASS", executable_dir))
    candidates = [
        base_path / "ms-playwright",
        base_path / "_internal" / "ms-playwright",
        executable_dir / "ms-playwright",
        executable_dir / "_internal" / "ms-playwright",
    ]

    if os.name == "nt":
        # Slim build fallback: use the user-level Playwright cache when available.
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        if str(local_app_data):
            candidates.append(local_app_data / "ms-playwright")

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def resolve_playwright_browsers_path() -> str:
    existing = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if existing:
        return existing

    for candidate in _iter_browser_path_candidates():
        if candidate.exists():
            return str(candidate)
    return ""


def configure_playwright_browsers_path() -> str:
    resolved = resolve_playwright_browsers_path()
    if resolved:
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", resolved)
    return resolved


configure_playwright_browsers_path()
