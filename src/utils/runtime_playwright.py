from __future__ import annotations

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    bundled = base_path / "ms-playwright"
    if bundled.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))
