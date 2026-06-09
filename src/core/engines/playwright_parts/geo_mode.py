from __future__ import annotations

from src.core.engines.playwright_parts.geo_mode_parts.map_controls import PlaywrightGeoMapControlMixin
from src.core.engines.playwright_parts.geo_mode_parts.markers import PlaywrightGeoMarkerMixin
from src.core.engines.playwright_parts.geo_mode_parts.scan import PlaywrightGeoScanMixin


class PlaywrightGeoModeMixin(
    PlaywrightGeoScanMixin,
    PlaywrightGeoMarkerMixin,
    PlaywrightGeoMapControlMixin,
):
    pass
