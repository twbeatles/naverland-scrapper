from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from src.utils.helpers import ChromeParamHelper
from src.utils.paths import BASE_DIR, DATA_DIR, is_frozen_runtime
from src.core.services.detail_fetcher import fetch_mobile_article_detail

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False
from src.utils.live_smoke_parts.helpers import (
    DEFAULT_SMOKE_ARTICLE_ID,
    DEFAULT_SMOKE_COMPLEX_ID,
    _new_smoke_page,
    _runtime_info_line,
    _runtime_metadata,
    default_live_smoke_urls,
)
from src.utils.live_smoke_parts.probes import (
    _run_article_api_probe,
    _run_article_lookup_probe,
    _run_complex_probe_detail,
    _run_detail_field_probe,
    _run_detail_probe,
    _run_geo_marker_probe,
    _run_home_probes,
)


async def _run_live_smoke_async(
    urls: Iterable[str],
    *,
    headless: bool = False,
    timeout_ms: int = 12000,
    complex_id: str = DEFAULT_SMOKE_COMPLEX_ID,
    article_id: str = DEFAULT_SMOKE_ARTICLE_ID,
    include_article_lookup: bool = True,
    include_geo_marker: bool = True,
    include_detail_fields: bool = False,
) -> tuple[bool, list[str], str]:
    if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
        return False, ["Playwright is not installed."], str(article_id or DEFAULT_SMOKE_ARTICLE_ID)

    controller = await async_playwright().start()
    browser = None
    messages: list[str] = []
    overall_ok = True
    browser_source = "playwright_chromium"
    effective_article_id = str(article_id or DEFAULT_SMOKE_ARTICLE_ID).strip()

    try:
        chrome_path = ChromeParamHelper.get_chrome_executable_path()
        if chrome_path:
            try:
                browser = await controller.chromium.launch(
                    executable_path=chrome_path,
                    headless=bool(headless),
                )
                browser_source = f"local_chrome:{chrome_path}"
            except Exception as exc:
                messages.append(f"[warn] local Chrome launch failed, fallback to Chromium: {exc}")
        if browser is None:
            browser = await controller.chromium.launch(headless=bool(headless))
            browser_source = f"playwright_chromium:{getattr(controller.chromium, 'executable_path', '') or ''}"

        context = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        messages.append(f"[info] browser={browser_source} mode={'headless' if headless else 'headed'}")
        home_page = await _new_smoke_page(context)
        try:
            home_ok, home_messages = await _run_home_probes(
                home_page,
                [str(item or "").strip() for item in urls if str(item or "").strip()],
                timeout_ms,
            )
            messages.extend(home_messages)
            overall_ok = overall_ok and home_ok
        finally:
            await home_page.close()

        article_api_ok, article_api_line, api_sample_article_id, _api_article_count = await _run_article_api_probe(
            context,
            complex_id,
            timeout_ms,
        )
        messages.append(article_api_line)
        overall_ok = overall_ok and article_api_ok
        if api_sample_article_id and (not effective_article_id or effective_article_id == DEFAULT_SMOKE_ARTICLE_ID):
            effective_article_id = api_sample_article_id

        complex_page = await _new_smoke_page(context)
        try:
            complex_ok, complex_line, sample_article_id, _article_count = await _run_complex_probe_detail(
                complex_page,
                complex_id,
                timeout_ms,
            )
            messages.append(complex_line)
            overall_ok = overall_ok and complex_ok
        finally:
            await complex_page.close()

        if sample_article_id and (not effective_article_id or effective_article_id == DEFAULT_SMOKE_ARTICLE_ID):
            effective_article_id = sample_article_id

        detail_page = await _new_smoke_page(context)
        try:
            detail_ok, detail_line = await _run_detail_probe(detail_page, effective_article_id, timeout_ms)
            messages.append(detail_line)
            overall_ok = overall_ok and detail_ok
        finally:
            await detail_page.close()

        if include_detail_fields:
            detail_fields_page = await _new_smoke_page(context)
            try:
                fields_ok, fields_line = await _run_detail_field_probe(
                    detail_fields_page,
                    effective_article_id,
                    timeout_ms,
                )
                messages.append(fields_line)
                overall_ok = overall_ok and fields_ok
            finally:
                await detail_fields_page.close()

        if include_geo_marker:
            geo_page = await _new_smoke_page(context)
            try:
                geo_ok, geo_line = await _run_geo_marker_probe(geo_page, complex_id, timeout_ms)
                messages.append(geo_line)
                overall_ok = overall_ok and geo_ok
            finally:
                await geo_page.close()
        await context.close()
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        try:
            await controller.stop()
        except Exception:
            pass
    return overall_ok, messages, effective_article_id


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
