from __future__ import annotations

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    bundled = base_path / "ms-playwright"
    if bundled.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))
    elif os.name == "nt":
        # Slim onefile build fallback: use the user-level Playwright cache if available.
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        user_cache = local_app_data / "ms-playwright" if local_app_data else None
        if user_cache and user_cache.exists():
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(user_cache))
