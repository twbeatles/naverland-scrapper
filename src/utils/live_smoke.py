from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

from src.core.services.detail_fetcher import fetch_mobile_article_detail
from src.utils.live_smoke_parts.helpers import (
    DEFAULT_SMOKE_ARTICLE_ID,
    DEFAULT_SMOKE_COMPLEX_ID,
    _BLOCK_PATTERNS,
    _append_reason,
    _build_smoke_line,
    _capture_response_status,
    _classify_probe,
    _detail_field_presence,
    _navigate_probe,
    _new_smoke_page,
    _runtime_info_line,
    _runtime_metadata,
    default_live_smoke_urls,
)
from src.utils.live_smoke_parts.probes import (
    _capture_complex_articles,
    _run_article_api_probe,
    _run_article_lookup_probe,
    _run_complex_probe,
    _run_complex_probe_detail,
    _run_detail_field_probe,
    _run_detail_probe,
    _run_geo_marker_probe,
    _run_home_probes,
)
from src.utils.live_smoke_parts import probes as _probe_module
from src.utils.live_smoke_parts import runner as _runner_module


def _sync_facade_overrides() -> None:
    _probe_module.fetch_mobile_article_detail = fetch_mobile_article_detail


async def _run_detail_field_probe(*args, **kwargs):
    _sync_facade_overrides()
    return await _probe_module._run_detail_field_probe(*args, **kwargs)


async def _run_live_smoke_async(*args, **kwargs):
    _sync_facade_overrides()
    return await _runner_module._run_live_smoke_async(*args, **kwargs)


def run_live_smoke(
    urls: Iterable[str] | None = None,
    *,
    headless: bool = False,
    timeout_ms: int = 12000,
    complex_id: str = DEFAULT_SMOKE_COMPLEX_ID,
    article_id: str = DEFAULT_SMOKE_ARTICLE_ID,
    json_log_path: str | None = None,
    include_article_lookup: bool = True,
    include_geo_marker: bool = True,
    include_detail_fields: bool = False,
) -> tuple[bool, list[str]]:
    from src.utils.paths import apply_runtime_path_overrides_from_env

    apply_runtime_path_overrides_from_env()
    _sync_facade_overrides()
    probe_urls = list(urls or default_live_smoke_urls())
    runtime_meta = _runtime_metadata()
    requested_article_id = str(article_id or DEFAULT_SMOKE_ARTICLE_ID).strip()
    effective_article_id = str(article_id or DEFAULT_SMOKE_ARTICLE_ID)
    try:
        async_result: Any = asyncio.run(
            _run_live_smoke_async(
                probe_urls,
                headless=headless,
                timeout_ms=timeout_ms,
                complex_id=str(complex_id or DEFAULT_SMOKE_COMPLEX_ID),
                article_id=str(article_id or DEFAULT_SMOKE_ARTICLE_ID),
                include_article_lookup=include_article_lookup,
                include_geo_marker=include_geo_marker,
                include_detail_fields=include_detail_fields,
            )
        )
        if isinstance(async_result, tuple) and len(async_result) >= 3:
            ok = bool(async_result[0])
            messages = list(async_result[1])
            effective_article_id = str(async_result[2] or effective_article_id)
        elif isinstance(async_result, tuple) and len(async_result) >= 2:
            ok = bool(async_result[0])
            messages = list(async_result[1])
        else:
            ok = False
            messages = [f"[fail] [live-smoke] invalid_async_result={async_result!r}"]
    except Exception as exc:
        ok = False
        messages = [f"[fail] [live-smoke] unexpected_exception={type(exc).__name__}: {exc}"]
    messages.insert(0, _runtime_info_line(runtime_meta))
    messages.append(
        f"[info] requested_article_id={requested_article_id or '-'} "
        f"effective_article_id={effective_article_id or '-'}"
    )
    if include_article_lookup:
        lookup_ok, lookup_line = _run_article_lookup_probe(effective_article_id)
        messages.append(lookup_line)
        ok = bool(ok) and lookup_ok
    if json_log_path:
        log_path = Path(str(json_log_path))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(log_path), "w", encoding="utf-8") as fp:
            json.dump(
                {
                    "ok": bool(ok),
                    "complex_id": str(complex_id or DEFAULT_SMOKE_COMPLEX_ID),
                    "article_id": str(effective_article_id or article_id or DEFAULT_SMOKE_ARTICLE_ID),
                    "effective_article_id": str(effective_article_id or article_id or DEFAULT_SMOKE_ARTICLE_ID),
                    "requested_article_id": str(article_id or DEFAULT_SMOKE_ARTICLE_ID),
                    "runtime_source": runtime_meta["runtime_source"],
                    "executable": runtime_meta["executable"],
                    "base_dir": runtime_meta["base_dir"],
                    "data_dir": runtime_meta["data_dir"],
                    "include_detail_fields": bool(include_detail_fields),
                    "messages": messages,
                },
                fp,
                ensure_ascii=False,
                indent=2,
            )
    return ok, messages

__all__ = [
    "DEFAULT_SMOKE_ARTICLE_ID",
    "DEFAULT_SMOKE_COMPLEX_ID",
    "default_live_smoke_urls",
    "run_live_smoke",
]
