from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightRuntimeMixin:
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
        stats.setdefault("blocked_page_count", 0)
        stats.setdefault("playwright_recycle_count", 0)
        stats.setdefault("playwright_last_recycle_reason", "")

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
        browser = await playwright.chromium.launch(
            headless=bool(self.thread.playwright_headless)
        )
        self._browser = browser
        desktop_context = await browser.new_context(
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
        mobile_context = await browser.new_context(
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

    async def _shutdown_async(self):
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

    async def _setup_blocking(self, context):
        if not self.thread.block_heavy_resources:
            return

        async def _route(route):
            if route.request.resource_type in ("image", "media", "font"):
                await route.abort()
                return
            await route.continue_()

        await context.route("**/*", _route)

    @staticmethod
    def _spawn_response_task(pending_tasks: set[asyncio.Task], coro) -> None:
        task = asyncio.create_task(coro)
        pending_tasks.add(task)
        task.add_done_callback(lambda done: pending_tasks.discard(done))

    async def _drain_pending_response_tasks(
        self,
        pending_tasks: set[asyncio.Task],
        *,
        label: str,
        timeout_ms: int | None = None,
    ) -> tuple[int, bool]:
        wait_count = len(pending_tasks)
        timed_out = False
        if wait_count <= 0:
            return 0, False
        if timeout_ms is None:
            try:
                timeout_ms = int(getattr(self.thread, "playwright_response_drain_timeout_ms", 3000))
            except (TypeError, ValueError):
                timeout_ms = 3000
        self.thread.stats["response_drain_wait_count"] = (
            int(self.thread.stats.get("response_drain_wait_count", 0)) + wait_count
        )
        self.thread.log(f"   응답 처리 대기중 ({label}): {wait_count}", 10)
        try:
            await asyncio.wait_for(
                asyncio.gather(*list(pending_tasks), return_exceptions=True),
                timeout=max(0.1, float(timeout_ms) / 1000.0),
            )
        except asyncio.TimeoutError:
            timed_out = True
            self.thread.stats["response_drain_timeout_count"] = (
                int(self.thread.stats.get("response_drain_timeout_count", 0)) + 1
            )
            for task in list(pending_tasks):
                if not task.done():
                    task.cancel()
            if pending_tasks:
                await asyncio.gather(*list(pending_tasks), return_exceptions=True)
            self.thread.log(f"   타깃 응답 처리 대기 타임아웃 ({label}): {wait_count}", 30)
        self.thread.emit_stats()
        return wait_count, timed_out

