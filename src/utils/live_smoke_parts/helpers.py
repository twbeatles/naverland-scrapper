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


_BLOCK_PATTERNS = (
    "captcha",
    "자동입력 방지",
    "자동 입력 방지",
    "접근이 제한",
    "접속이 제한",
    "비정상적인 접근",
    "서비스 이용이 제한",
    "verify you are human",
    "robot check",
    "access denied",
    "security check",
    "cloudflare",
    "bot detection",
)
DEFAULT_SMOKE_COMPLEX_ID = "3833"
DEFAULT_SMOKE_ARTICLE_ID = "2625154515"


def _runtime_metadata() -> dict[str, str]:
    runtime_source = "frozen" if is_frozen_runtime() else "source"
    try:
        executable = str(Path(sys.executable).resolve())
    except Exception:
        executable = str(sys.executable or "")
    return {
        "runtime_source": runtime_source,
        "executable": executable,
        "base_dir": str(BASE_DIR),
        "data_dir": str(DATA_DIR),
    }


def _runtime_info_line(meta: dict[str, str] | None = None) -> str:
    item = dict(meta or _runtime_metadata())
    return (
        "[info] "
        f"runtime_source={item.get('runtime_source', '-') or '-'} "
        f"executable={item.get('executable', '-') or '-'} "
        f"data_dir={item.get('data_dir', '-') or '-'}"
    )


def default_live_smoke_urls() -> list[str]:
    return [
        "https://fin.land.naver.com/",
        "https://new.land.naver.com/",
        "https://m.land.naver.com/",
    ]


def _build_smoke_line(
    *,
    ok: bool,
    kind: str,
    target: str,
    final_url: str,
    status: int | None,
    title: str,
    reason: str = "",
    extra: str = "",
) -> str:
    prefix = "[ok]" if ok else "[fail]"
    line = f"{prefix} [{kind}] {target} -> {final_url or '-'} status={status if status is not None else '-'}"
    if title:
        line += f" title={title}"
    if extra:
        line += f" {extra}"
    if reason:
        line += f" reason={reason}"
    return line


def _append_reason(reason: str, token: str) -> str:
    current = str(reason or "").strip()
    item = str(token or "").strip()
    if not item:
        return current
    if not current:
        return item
    if item in current.split(","):
        return current
    return f"{current},{item}"


async def _new_smoke_page(context):
    page = await context.new_page()
    await page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return page


async def _navigate_probe(page, url: str, timeout_ms: int) -> dict:
    response = None
    navigation_error = ""
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=max(1000, int(timeout_ms)))
    except Exception as exc:
        navigation_error = f"navigation_exception:{type(exc).__name__}:{exc}"
    try:
        await page.wait_for_load_state("networkidle", timeout=2500)
    except Exception:
        pass
    final_url = str(getattr(page, "url", "") or "")
    try:
        title = await page.title()
    except Exception:
        title = ""
    status = int(response.status) if response is not None and getattr(response, "status", None) is not None else None
    ok, reason = _classify_probe(final_url, title, status)
    if navigation_error:
        ok = False
        reason = _append_reason(reason, navigation_error)
    return {
        "ok": ok,
        "reason": reason,
        "status": status,
        "final_url": final_url,
        "title": title,
    }


async def _capture_response_status(page, matcher, timeout_ms: int):
    matched_status = None
    matched_event = asyncio.Event()

    def _handle(response):
        nonlocal matched_status
        try:
            if not matcher(str(getattr(response, "url", "") or "")):
                return
            matched_status = int(getattr(response, "status", 0) or 0)
            matched_event.set()
        except Exception:
            return None

    can_listen = hasattr(page, "on") and hasattr(page, "remove_listener")
    if can_listen:
        try:
            page.on("response", _handle)
        except Exception:
            can_listen = False
    try:
        try:
            await asyncio.wait_for(matched_event.wait(), timeout=max(0.1, float(timeout_ms) / 1000.0))
        except Exception:
            pass
        return bool(matched_event.is_set()), matched_status
    finally:
        if can_listen:
            try:
                page.remove_listener("response", _handle)
            except Exception:
                pass


def _detail_field_presence(detail: dict[str, Any]) -> dict[str, int | str]:
    meta = dict(detail.get("_detail_meta", {}) or {}) if isinstance(detail, dict) else {}
    office = bool(str(detail.get("부동산상호", "") or "").strip()) if isinstance(detail, dict) else False
    agent = bool(str(detail.get("중개사이름", "") or "").strip()) if isinstance(detail, dict) else False
    phone = False
    prev_jeonse = False
    if isinstance(detail, dict):
        phone = bool(str(detail.get("전화1", "") or "").strip() or str(detail.get("전화2", "") or "").strip())
        try:
            prev_jeonse = int(detail.get("기전세금(원)", 0) or 0) > 0
        except (TypeError, ValueError):
            prev_jeonse = False
    found_count = sum(1 for flag in (office, agent, phone, prev_jeonse) if flag)
    return {
        "parse_state": str(meta.get("detail_parse_state", "") or "missing"),
        "source": str(meta.get("detail_source", "") or "-"),
        "missing_field_count": int(meta.get("missing_field_count", 0) or 0),
        "network_response_count": int(meta.get("network_response_count", 0) or 0),
        "hydration_hit": int(meta.get("hydration_hit", 0) or 0),
        "core_field_count": found_count,
    }


def _classify_probe(final_url: str, title: str, status: int | None) -> tuple[bool, str]:
    lower_url = str(final_url or "").lower()
    lower_title = str(title or "").lower()
    if status is not None and int(status) >= 400:
        return False, f"http_{int(status)}"
    if "/404" in lower_url or lower_url.endswith("404"):
        return False, "redirect_404"
    if "not found" in lower_title:
        return False, "title_not_found"
    for token in _BLOCK_PATTERNS:
        lowered = token.lower()
        if lowered and (lowered in lower_url or lowered in lower_title):
            return False, f"pattern:{token}"
    return True, ""
