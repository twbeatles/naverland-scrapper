from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CrawlMode(str, Enum):
    COMPLEX = "complex"
    GEO_SWEEP = "geo_sweep"


@dataclass(slots=True)
class GeoSweepConfig:
    lat: float
    lon: float
    zoom: int = 15
    rings: int = 1
    step_px: int = 480
    dwell_ms: int = 600
    asset_types: list[str] = field(default_factory=lambda: ["APT", "VL"])


@dataclass(slots=True)
class CrawlRequest:
    mode: CrawlMode = CrawlMode.COMPLEX
    engine: str = "playwright"
    targets: list[tuple[str, str]] = field(default_factory=list)
    trade_types: list[str] = field(default_factory=list)
    geo: GeoSweepConfig | None = None
