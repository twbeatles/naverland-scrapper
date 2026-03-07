from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum

DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


class CrawlMode(str, Enum):
    COMPLEX = "complex"
    GEO_SWEEP = "geo_sweep"


@dataclass(**DATACLASS_KWARGS)
class GeoSweepConfig:
    lat: float
    lon: float
    zoom: int = 15
    rings: int = 1
    step_px: int = 480
    dwell_ms: int = 600
    asset_types: list[str] = field(default_factory=lambda: ["APT", "VL"])


@dataclass(**DATACLASS_KWARGS)
class CrawlRequest:
    mode: CrawlMode = CrawlMode.COMPLEX
    engine: str = "playwright"
    targets: list[tuple[str, str]] = field(default_factory=list)
    trade_types: list[str] = field(default_factory=list)
    geo: GeoSweepConfig | None = None
