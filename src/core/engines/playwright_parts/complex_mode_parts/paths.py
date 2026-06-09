from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.response_capture import TRADE_CODE_MAP, detect_trade_type, normalize_article_payload

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403

_TRADE_TO_CODE: dict[str, str] = {value: key for key, value in TRADE_CODE_MAP.items()}
_LEGACY_ARTICLE_ID_KEY = "\uf9cd\u317b\u042aID"


class PlaywrightComplexPathsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _candidate_paths(asset_type: str) -> list[tuple[str, str]]:
        if asset_type == "VL":
            return [("houses", "VL"), ("complexes", "APT")]
        if asset_type == "APT":
            return [("complexes", "APT"), ("houses", "VL")]
        return [("complexes", "APT"), ("houses", "VL")]
