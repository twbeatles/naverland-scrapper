from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.utils.helpers import ChromeParamHelper

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightBrowserRuntimeMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def __init__(self, thread):
        self.thread = thread
        self._loop = asyncio.new_event_loop()
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._desktop_context: Any | None = None
        self._desktop_page: Any | None = None
        self._mobile_context: Any | None = None
        self._page_pool: asyncio.Queue[Any] | None = None
        self._started: bool = False
        self._fallback_used: bool = False
        self._launch_headless_override: bool | None = None
        self._launched_headless: bool | None = None
        self._headed_fallback_used: bool = False
        self._entry_plan_success_by_key: dict[tuple[str, str, str], str] = {}
        self._article_api_auth_header: str = ""

    def run(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed")
        self._ensure_runtime_stats()
        if self.thread.crawl_mode == "geo_sweep":
            self._run(self._run_geo())
            return
        self._run(self._run_complex_mode())

    def close(self) -> None:
        try:
            if self._started:
                self._run(self._shutdown_async())
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    def _run(self, coro):
        try:
            asyncio.set_event_loop(self._loop)
        except Exception:
            pass
        return self._loop.run_until_complete(coro)

    def _ensure_runtime_stats(self):
        stats = getattr(self.thread, "stats", None)
        if not isinstance(stats, dict):
            return
        stats.setdefault("response_seen_count", 0)
        stats.setdefault("parse_success_count", 0)
        stats.setdefault("parse_fail_count", 0)
        stats.setdefault("detail_success_count", 0)
        stats.setdefault("detail_fail_count", 0)
        stats.setdefault("detail_partial_count", 0)
        stats.setdefault("detail_missing_field_total", 0)
        stats.setdefault("detail_fetch_skipped_count", 0)
        stats.setdefault("blocked_page_count", 0)
        stats.setdefault("geo_incomplete", False)
        stats.setdefault("geo_incomplete_count", 0)
        stats.setdefault("geo_incomplete_reasons", [])
        stats.setdefault("geo_marker_switch_attempt_count", 0)
        stats.setdefault("geo_marker_switch_success_count", 0)
        stats.setdefault("geo_marker_switch_fail_count", 0)
        stats.setdefault("geo_marker_switch_last_method", "")
        stats.setdefault("playwright_recycle_count", 0)
        stats.setdefault("playwright_last_recycle_reason", "")
        stats.setdefault("playwright_browser_source", "")
        stats.setdefault("playwright_browser_path", "")
        stats.setdefault("playwright_profile_dir", "")
        stats.setdefault("playwright_session_reused", 0)
        stats.setdefault("playwright_headed_fallback_used", 0)
        stats.setdefault("playwright_warmup_count", 0)
        stats.setdefault("playwright_last_entry_plan", "")
        stats.setdefault("playwright_last_final_url", "")
        stats.setdefault("playwright_last_page_title", "")
        stats.setdefault("playwright_last_block_reason", "")
        stats.setdefault("response_match_count", 0)
        stats.setdefault("capture_failed_count", 0)
        stats.setdefault("block_like_redirect_count", 0)
        stats.setdefault("article_api_fast_path_hit_count", 0)
        stats.setdefault("article_api_fast_path_fail_count", 0)
        stats.setdefault("article_api_fast_path_fallback_count", 0)
        stats.setdefault("article_api_last_status", "")
        stats.setdefault("detail_network_response_total", 0)
        stats.setdefault("detail_hydration_hit_count", 0)

    async def _sleep_async_interruptible(self, seconds: float, chunk: float = 0.1) -> bool:
        remaining = max(0.0, float(seconds or 0.0))
        unit = min(0.2, max(0.05, float(chunk or 0.1)))
        while remaining > 0:
            if self.thread._should_stop():
                return False
            step = unit if remaining > unit else remaining
            await asyncio.sleep(step)
            remaining -= step
        return True

    async def _async_retry(self, label: str, func, *, attempts: int = 3):
        last_exc = None
        tries = max(1, int(attempts or 1))
        for attempt in range(1, tries + 1):
            if self.thread._should_stop():
                raise RuntimeError(f"{label} aborted by stop request")
            try:
                return await func()
            except Exception as exc:
                last_exc = exc
                if attempt >= tries:
                    break
                self.thread.log(f"   retry in {PLAYWRIGHT_RETRY_BASE_DELAY_SEC * attempt:.1f}s ({attempt}/{tries - 1}): {label}", 10)
                if not await self._sleep_async_interruptible(PLAYWRIGHT_RETRY_BASE_DELAY_SEC * attempt):
                    raise RuntimeError(f"{label} aborted during retry backoff") from exc
        self.thread.log(f"   ⚠️ retry exhausted: {label} ({last_exc})", 30)
        raise last_exc if last_exc is not None else RuntimeError(f"{label} failed")

    def _navigation_timeout_ms(self) -> int:
        try:
            return min(60000, max(1000, int(getattr(self.thread, "playwright_navigation_timeout_ms", 15000))))
        except (TypeError, ValueError):
            return 15000

    async def _check_memory_and_recycle_if_needed(self, reason: str):
        self._ensure_runtime_stats()
        if not PSUTIL_AVAILABLE:
            return
        try:
            memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            return
        if memory_mb <= PLAYWRIGHT_MEMORY_THRESHOLD_MB:
            return

        self.thread.stats["playwright_recycle_count"] = int(self.thread.stats.get("playwright_recycle_count", 0)) + 1
        self.thread.stats["playwright_last_recycle_reason"] = f"{reason}:{memory_mb:.0f}MB"
        self.thread.log(
            f"⚠️ Playwright memory {memory_mb:.0f}MB > {PLAYWRIGHT_MEMORY_THRESHOLD_MB}MB, recycling browser context...",
            30,
        )
        await self._shutdown_async()
        await self._ensure_started()
        self.thread.emit_stats()

    async def _ensure_started(self):
        if self._started:
            return
        self._started = True
        playwright = await async_playwright().start()
        self._playwright = playwright
        preferred_headless = (
            bool(self._launch_headless_override)
            if self._launch_headless_override is not None
            else bool(self.thread.playwright_headless)
        )
        browser, browser_source, browser_path, actual_headless = await self._launch_browser(
            playwright,
            preferred_headless=preferred_headless,
        )
        self._browser = browser
        self._launched_headless = actual_headless
        self.thread.stats["playwright_browser_source"] = browser_source
        self.thread.stats["playwright_browser_path"] = browser_path
        self.thread.stats["playwright_profile_dir"] = self._profile_root()
        desktop_context = await self._create_context(
            browser,
            "desktop",
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="ko-KR",
        )
        self._desktop_context = desktop_context
        await self._setup_blocking(desktop_context)
        desktop_page = await desktop_context.new_page()
        self._desktop_page = desktop_page
        await desktop_page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        device = playwright.devices["iPhone 14 Pro Max"]
        mobile_context = await self._create_context(
            browser,
            "mobile",
            **device,
            locale="ko-KR",
            extra_http_headers={
                "referer": "https://m.land.naver.com/",
                "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        self._mobile_context = mobile_context
        await self._setup_blocking(mobile_context)
        page_pool: asyncio.Queue[Any] = asyncio.Queue()
        self._page_pool = page_pool
        for _ in range(max(1, int(self.thread.playwright_detail_workers))):
            page = await mobile_context.new_page()
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.open = (u) => { location.href = u; };
                """
            )
            await page_pool.put(page)
        await self._warmup_runtime_pages()
        self.thread.emit_stats()

    async def _shutdown_async(self):
        await self._save_context_state(self._desktop_context, "desktop")
        await self._save_context_state(self._mobile_context, "mobile")
        if self._page_pool is not None:
            while not self._page_pool.empty():
                page = await self._page_pool.get()
                try:
                    await page.close()
                except Exception:
                    pass
        for obj in [self._desktop_page, self._mobile_context, self._desktop_context, self._browser]:
            if obj is None:
                continue
            try:
                await obj.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._desktop_page = None
        self._mobile_context = None
        self._desktop_context = None
        self._browser = None
        self._playwright = None
        self._page_pool = None
        self._started = False

    async def _launch_browser(self, playwright, *, preferred_headless: bool):
        launch_kwargs = {"headless": bool(preferred_headless)}
        try:
            browser, browser_source, browser_path = await self._launch_browser_once(playwright, launch_kwargs)
            return browser, browser_source, browser_path, bool(preferred_headless)
        except Exception as exc:
            if not bool(preferred_headless):
                raise
            self.thread.log(f"Playwright headless 실행 실패, headed 재시도합니다: {exc}", 30)
            self._headed_fallback_used = True
            self.thread.stats["playwright_headed_fallback_used"] = 1
            launch_kwargs["headless"] = False
            browser, browser_source, browser_path = await self._launch_browser_once(playwright, launch_kwargs)
            return browser, browser_source, browser_path, False

    async def _launch_browser_once(self, playwright, launch_kwargs: dict):
        browser_source = "playwright_chromium"
        browser_path = ""
        chrome_path = ChromeParamHelper.get_chrome_executable_path()
        if chrome_path:
            try:
                browser = await playwright.chromium.launch(
                    executable_path=chrome_path,
                    **launch_kwargs,
                )
                browser_source = "local_chrome"
                browser_path = chrome_path
                mode_label = "headless" if bool(launch_kwargs.get("headless")) else "headed"
                self.thread.log(f"Playwright 브라우저: local Chrome 사용 ({mode_label}, {chrome_path})", 10)
                return browser, browser_source, browser_path
            except Exception as exc:
                self.thread.log(
                    f"Playwright local Chrome 실행 실패, Chromium으로 fallback 합니다: {exc}",
                    30,
                )
        browser = await playwright.chromium.launch(**launch_kwargs)
        browser_path = str(getattr(playwright.chromium, "executable_path", "") or "")
        mode_label = "headless" if bool(launch_kwargs.get("headless")) else "headed"
        self.thread.log(f"Playwright 브라우저: Chromium fallback 사용 ({mode_label})", 10)
        return browser, browser_source, browser_path

    def _profile_root(self) -> str:
        from src.utils.paths import DATA_DIR, ensure_directories

        ensure_directories()
        root = DATA_DIR / "playwright_profiles"
        root.mkdir(parents=True, exist_ok=True)
        return str(root)

    def _storage_state_path(self, label: str) -> str:
        from pathlib import Path

        safe_label = str(label or "default").strip().lower() or "default"
        return str(Path(self._profile_root()) / f"{safe_label}_storage_state.json")
