from __future__ import annotations

import asyncio
from typing import Iterable

from src.utils.helpers import ChromeParamHelper

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


def default_live_smoke_urls() -> list[str]:
    return [
        "https://fin.land.naver.com/",
        "https://new.land.naver.com/",
        "https://m.land.naver.com/",
    ]


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


async def _run_live_smoke_async(
    urls: Iterable[str],
    *,
    headless: bool = False,
    timeout_ms: int = 12000,
) -> tuple[bool, list[str]]:
    if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
        return False, ["Playwright is not installed."]

    controller = await async_playwright().start()
    browser = None
    messages: list[str] = []
    overall_ok = True
    browser_source = "playwright_chromium"

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
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        messages.append(f"[info] browser={browser_source} mode={'headless' if headless else 'headed'}")
        for url in [str(item or "").strip() for item in urls if str(item or "").strip()]:
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=max(1000, int(timeout_ms)))
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
                prefix = "[ok]" if ok else "[fail]"
                line = f"{prefix} {url} -> {final_url or '-'} status={status if status is not None else '-'}"
                if title:
                    line += f" title={title}"
                if reason:
                    line += f" reason={reason}"
                messages.append(line)
                overall_ok = overall_ok and ok
            except Exception as exc:
                messages.append(f"[fail] {url} -> exception={exc}")
                overall_ok = False
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
    return overall_ok, messages


def run_live_smoke(
    urls: Iterable[str] | None = None,
    *,
    headless: bool = False,
    timeout_ms: int = 12000,
) -> tuple[bool, list[str]]:
    probe_urls = list(urls or default_live_smoke_urls())
    return asyncio.run(
        _run_live_smoke_async(
            probe_urls,
            headless=headless,
            timeout_ms=timeout_ms,
        )
    )
