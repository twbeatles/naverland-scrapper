from __future__ import annotations

import asyncio
from urllib.parse import urlencode

from src.core.services.detail_fetcher import apply_mobile_detail, fetch_mobile_article_detail
from src.core.services.map_geometry import build_grid_sweep_coords, clamp_korea
from src.core.services.response_capture import (
    TRADE_CODE_MAP,
    detect_trade_type,
    normalize_article_payload,
    normalize_marker_payload,
)
from src.utils.logger import get_logger
from .base import CrawlerEngine

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False


logger = get_logger("PlaywrightEngine")

_TRADE_TO_CODE = {value: key for key, value in TRADE_CODE_MAP.items()}


class PlaywrightCrawlerEngine(CrawlerEngine):
    engine_name = "playwright"

    def __init__(self, thread):
        self.thread = thread
        self._loop = asyncio.new_event_loop()
        self._playwright = None
        self._browser = None
        self._desktop_context = None
        self._desktop_page = None
        self._mobile_context = None
        self._page_pool: asyncio.Queue | None = None
        self._started = False
        self._fallback_used = False

    def run(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("playwright is not installed")
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

    async def _ensure_started(self):
        if self._started:
            return
        self._started = True
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=bool(self.thread.playwright_headless)
        )
        self._desktop_context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="ko-KR",
        )
        await self._setup_blocking(self._desktop_context)
        self._desktop_page = await self._desktop_context.new_page()
        await self._desktop_page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        device = self._playwright.devices["iPhone 14 Pro Max"]
        self._mobile_context = await self._browser.new_context(
            **device,
            locale="ko-KR",
            extra_http_headers={
                "referer": "https://m.land.naver.com/",
                "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        await self._setup_blocking(self._mobile_context)
        self._page_pool = asyncio.Queue()
        for _ in range(max(1, int(self.thread.playwright_detail_workers))):
            page = await self._mobile_context.new_page()
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.open = (u) => { location.href = u; };
                """
            )
            await self._page_pool.put(page)

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
    ) -> int:
        wait_count = len(pending_tasks)
        if wait_count <= 0:
            return 0
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
        return wait_count

    async def _run_complex_mode(self):
        await self._ensure_started()
        total = len(self.thread.targets) * len(self.thread.trade_types)
        current = 0
        processed_pairs = set()
        for name, cid in self.thread.targets:
            if self.thread._should_stop():
                break
            complex_count = 0
            for trade_type in self.thread.trade_types:
                if self.thread._should_stop():
                    break
                processed_pairs.add((str(cid), str(trade_type)))
                current += 1
                self.thread.progress_signal.emit(
                    int(current / total * 100) if total else 0,
                    f"{name} ({trade_type})",
                    self.thread._estimate_remaining_seconds(current, total),
                )
                self.thread.log(f"\n?뱧 [{current}/{total}] {name} - {trade_type}")
                try:
                    result = await self._crawl_target_with_cache(name, cid, trade_type)
                    count = int(result.get("count", 0))
                    complex_count += count
                    self.thread.stats["by_trade_type"][trade_type] = (
                        self.thread.stats["by_trade_type"].get(trade_type, 0) + count
                    )
                    self.thread.log(f"   ??{count}嫄??섏쭛")
                except Exception as exc:
                    self.thread.log(f"   ???ㅻ쪟: {exc}", 40)
                    if self.thread.fallback_engine_enabled and not self._fallback_used:
                        self._fallback_used = True
                        self.thread.log("   ??Selenium fallback?쇰줈 ?꾪솚?⑸땲??", 30)
                        self.thread._run_fallback_selenium(start_name=name, start_cid=cid, start_trade=trade_type)
                        return
                if not self.thread._sleep_interruptible(self.thread._get_speed_delay()):
                    break
            self.thread._flush_history_updates(force=True)
            self.thread.record_crawl_history(
                name,
                cid,
                ",".join(self.thread.trade_types),
                int(complex_count),
                engine=self.engine_name,
                mode=self.thread.crawl_mode,
            )
            self.thread.complex_finished_signal.emit(name, cid, ",".join(self.thread.trade_types), int(complex_count))
        self.thread._finalize_disappeared_articles(processed_pairs)

    async def _run_geo(self):
        await self._ensure_started()
        geo = self.thread.geo_config
        if not geo:
            raise RuntimeError("geo_config媛 ?놁뒿?덈떎.")
        if not self._desktop_page:
            raise RuntimeError("desktop page 珥덇린???ㅽ뙣")

        lat, lon = clamp_korea(geo.lat, geo.lon)
        zoom = int(geo.zoom or 15)
        discovered: dict[str, dict] = {}
        self.thread.log(
            f"?㎛ 吏???먯깋 ?쒖옉: lat={lat:.5f}, lon={lon:.5f}, zoom={zoom}, ?먯궛={','.join(geo.asset_types)}"
        )

        marker_handler, marker_pending_tasks, marker_stats = self._build_marker_handler(discovered)
        marker_wait_count = 0
        self._desktop_page.on("response", marker_handler)
        try:
            for asset_type in geo.asset_types:
                if self.thread._should_stop():
                    break
                for trade_type in self.thread.trade_types:
                    if self.thread._should_stop():
                        break
                    await self._scan_geo_asset_type(asset_type, trade_type, lat, lon, zoom, geo)
        finally:
            try:
                self._desktop_page.remove_listener("response", marker_handler)
            except Exception:
                pass
            marker_wait_count = await self._drain_pending_response_tasks(
                marker_pending_tasks,
                label="geo_marker",
            )

        dedup_removed = int(marker_stats.get("dedup_skipped", 0))
        self.thread.log(
            f"?뱄툘 吏???먯깋 ?붿빟: 諛쒓껄 ?⑥? ??{len(discovered)}, 以묐났 ?쒓굅 ??{dedup_removed}, ?묐떟 泥섎━ ?湲???{marker_wait_count}",
            10,
        )

        ordered = sorted(discovered.values(), key=lambda row: (-int(row.get("count", 0)), row.get("complex_name", "")))
        if not ordered:
            self.thread.log("?뱄툘 吏???먯깋 寃곌낵 ?⑥?瑜?李얠? 紐삵뻽?듬땲??", 30)
            return

        processed_pairs = set()
        total = len(ordered) * max(1, len(self.thread.trade_types))
        current = 0
        for row in ordered:
            if self.thread._should_stop():
                break
            name = str(row.get("complex_name", ""))
            cid = str(row.get("complex_id", ""))
            asset_type = str(row.get("asset_type", "APT"))
            complex_count = 0
            for trade_type in self.thread.trade_types:
                if self.thread._should_stop():
                    break
                current += 1
                processed_pairs.add((asset_type, cid, trade_type))
                self.thread.progress_signal.emit(
                    int(current / total * 100) if total else 0,
                    f"{name} ({trade_type})",
                    self.thread._estimate_remaining_seconds(current, total),
                )
                try:
                    result = await self._crawl_target_with_cache(
                        name,
                        cid,
                        trade_type,
                        asset_type=asset_type,
                        mode="geo_sweep",
                        source_lat=lat,
                        source_lon=lon,
                        source_zoom=zoom,
                        marker_id=str(row.get("marker_id", "")),
                    )
                    count = int(result.get("count", 0))
                    complex_count += count
                    self.thread.stats["by_trade_type"][trade_type] = (
                        self.thread.stats["by_trade_type"].get(trade_type, 0) + count
                    )
                except Exception as exc:
                    self.thread.log(f"   ??{name}({trade_type}) ?섏쭛 ?ㅽ뙣: {exc}", 40)
            self.thread.record_crawl_history(
                name,
                cid,
                ",".join(self.thread.trade_types),
                int(complex_count),
                engine=self.engine_name,
                mode="geo_sweep",
                source_lat=lat,
                source_lon=lon,
                source_zoom=zoom,
                asset_type=asset_type,
            )
            self.thread.complex_finished_signal.emit(name, cid, ",".join(self.thread.trade_types), int(complex_count))
        self.thread.stats["geo_discovered_count"] = len(discovered)
        self.thread.stats["geo_dedup_count"] = dedup_removed
        self.thread.emit_stats()
        self.thread._finalize_disappeared_articles(processed_pairs)

    def _build_marker_handler(self, discovered: dict[str, dict]):
        pending_tasks: set[asyncio.Task] = set()
        stats = {"dedup_skipped": 0}

        async def _consume(response):
            if self.thread._should_stop():
                return
            url = response.url
            if ("complexes/single-markers" not in url) and ("houses/single-markers" not in url):
                return
            try:
                payload = await response.json()
            except Exception:
                return
            if not isinstance(payload, list):
                return
            asset = "VL" if "houses/" in url else "APT"
            for raw_marker in payload:
                marker = normalize_marker_payload(raw_marker, asset_type=asset)
                cid = marker.get("complex_id", "")
                if not cid:
                    continue
                dedupe_key = f"{asset}:{cid}"
                current = discovered.get(dedupe_key)
                marker_count = int(marker.get("count", 0) or 0)
                current_count = int(current.get("count", 0) or 0) if current else -1
                if current is None or marker_count > current_count:
                    discovered[dedupe_key] = marker
                    self.thread.register_discovered_complex(marker)
                else:
                    stats["dedup_skipped"] = int(stats.get("dedup_skipped", 0)) + 1

        def _handle(response):
            try:
                self._spawn_response_task(pending_tasks, _consume(response))
            except Exception:
                return None

        return _handle, pending_tasks, stats

    async def _scan_geo_asset_type(
        self,
        asset_type: str,
        trade_type: str,
        lat: float,
        lon: float,
        zoom: int,
        geo,
    ):
        if not self._desktop_page:
            return
        base_kind = "houses" if asset_type == "VL" else "complexes"
        trade_code = _TRADE_TO_CODE.get(trade_type, "A1")
        url = (
            f"https://new.land.naver.com/{base_kind}?"
            + urlencode({"ms": f"{lat},{lon},{zoom}", "a": asset_type, "tradeTypes": trade_code})
        )
        await self._desktop_page.goto(url, wait_until="domcontentloaded")
        try:
            await self._desktop_page.wait_for_selector("canvas", timeout=15000)
        except Exception:
            self.thread.log("geo canvas wait timeout", 10)
        await self._human_like_recenter(lat, lon, zoom)
        await self._switch_to_listing_markers()
        coords = build_grid_sweep_coords(lat, lon, zoom, rings=geo.rings, step_px=geo.step_px)
        dwell_ms = max(100, int(geo.dwell_ms))
        total = len(coords)
        for idx, (target_lat, target_lon) in enumerate(coords, 1):
            if self.thread._should_stop():
                break
            self.thread.log(f"   ??{asset_type}/{trade_type} sweep {idx}/{total}", 10)
            await self._drag_to_latlon(target_lat, target_lon)
            try:
                await self._desktop_page.mouse.wheel(0, -40)
            except Exception:
                pass
            await self._desktop_page.wait_for_timeout(dwell_ms)

    async def _crawl_target_with_cache(
        self,
        name: str,
        cid: str,
        trade_type: str,
        *,
        asset_type: str = "",
        mode: str = "complex",
        source_lat: float | None = None,
        source_lon: float | None = None,
        source_zoom: int | None = None,
        marker_id: str = "",
    ) -> dict:
        cache = self.thread.cache
        mode_token = str(mode or "complex").strip().lower()
        is_complex_mode = mode_token == "complex"
        cache_asset_type = "APT" if is_complex_mode else str(asset_type or "")
        cache_marker_id = "" if is_complex_mode else str(marker_id or cid or "")
        cache_ctx = {
            "mode": mode_token,
            "asset_type": cache_asset_type,
            "source_lat": source_lat,
            "source_lon": source_lon,
            "source_zoom": source_zoom,
            "marker_id": cache_marker_id,
        }
        if cache:
            cached = cache.get(cid, trade_type, **cache_ctx)
            if cached is None and is_complex_mode:
                legacy_candidates = [
                    {"mode": "complex", "asset_type": "", "marker_id": str(cid or "")},
                    {"mode": "complex", "asset_type": "APT", "marker_id": str(cid or "")},
                    {},
                ]
                for legacy_ctx in legacy_candidates:
                    legacy_cached = cache.get(cid, trade_type, **legacy_ctx)
                    if legacy_cached is None:
                        continue
                    cache.set(cid, trade_type, legacy_cached, **cache_ctx)
                    cached = legacy_cached
                    break
            if cached is not None:
                self.thread.log(f"   ?뮶 罹먯떆 ?덊듃! {len(cached)}嫄?濡쒕뱶")
                self.thread.stats["cache_hits"] = self.thread.stats.get("cache_hits", 0) + 1
                matched = self.thread._process_raw_items(cached, trade_type)
                return {"count": matched, "raw_count": len(cached), "cache_hit": True}

        raw_items = await self._collect_target_raw_items(
            name,
            cid,
            trade_type,
            asset_type=cache_asset_type if is_complex_mode else asset_type,
            mode=mode_token,
            source_lat=source_lat,
            source_lon=source_lon,
            source_zoom=source_zoom,
            marker_id=cache_marker_id if is_complex_mode else marker_id,
        )
        if cache:
            if raw_items:
                cache.set(cid, trade_type, raw_items, **cache_ctx)
            else:
                ttl_seconds = int(max(0, self.thread.negative_cache_ttl_minutes) * 60)
                if ttl_seconds > 0:
                    cache.set(cid, trade_type, [], ttl_seconds=ttl_seconds, **cache_ctx)
        matched = self.thread._process_raw_items(raw_items, trade_type)
        return {"count": matched, "raw_count": len(raw_items), "cache_hit": False}

    async def _collect_target_raw_items(
        self,
        name: str,
        cid: str,
        trade_type: str,
        *,
        asset_type: str = "",
        mode: str = "complex",
        source_lat: float | None = None,
        source_lon: float | None = None,
        source_zoom: int | None = None,
        marker_id: str = "",
    ) -> list[dict]:
        await self._ensure_started()
        raw_items: list[dict] = []
        seen_ids: set[str] = set()

        for base_kind, path_asset in self._candidate_paths(asset_type):
            page = self._desktop_page
            if page is None:
                break
            pending_tasks: set[asyncio.Task] = set()

            async def _consume(response):
                url = response.url
                expected = f"/api/articles/{'house' if base_kind == 'houses' else 'complex'}/{cid}"
                if expected not in url:
                    return
                try:
                    payload = await response.json()
                except Exception:
                    return
                article_list = payload.get("articleList") or payload.get("articles") or []
                for article in article_list:
                    if detect_trade_type(article, requested_trade_type=trade_type) != trade_type:
                        continue
                    payload_marker_id = "" if mode == "complex" else str(marker_id or cid or "")
                    item = normalize_article_payload(
                        article,
                        complex_name=name,
                        complex_id=cid,
                        requested_trade_type=trade_type,
                        asset_type=path_asset,
                        mode=mode,
                        lat=source_lat,
                        lon=source_lon,
                        zoom=source_zoom,
                        marker_id=payload_marker_id,
                    )
                    aid = str(item.get("留ㅻЪID", "") or "")
                    if not aid or aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                    raw_items.append(item)

            def _handle(response):
                try:
                    self._spawn_response_task(pending_tasks, _consume(response))
                except Exception:
                    return None

            page.on("response", _handle)
            try:
                url = (
                    f"https://new.land.naver.com/{base_kind}/{cid}?"
                    + urlencode(
                        {
                            "ms": f"{source_lat or 37.5},{source_lon or 127},{source_zoom or 16}",
                            "a": path_asset,
                            "tradeTypes": _TRADE_TO_CODE.get(trade_type, "A1"),
                        }
                    )
                )
                await page.goto(url, wait_until="domcontentloaded")
                try:
                    await page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                for text in ["留ㅻЪ", trade_type]:
                    try:
                        await page.locator(f"text={text}").first.click(timeout=1000)
                        await page.wait_for_timeout(400)
                    except Exception:
                        continue
                await page.wait_for_timeout(1800)
            finally:
                try:
                    page.remove_listener("response", _handle)
                except Exception:
                    pass
                await self._drain_pending_response_tasks(
                    pending_tasks,
                    label=f"article_capture:{base_kind}/{cid}",
                )
            if raw_items:
                break

        if not raw_items:
            return []
        return await self._enrich_items_with_mobile_details(raw_items)

    async def _enrich_items_with_mobile_details(self, items: list[dict]) -> list[dict]:
        if not items or self._page_pool is None:
            return items

        async def _fetch_one(item: dict) -> dict:
            page = await self._page_pool.get()
            try:
                detail = await fetch_mobile_article_detail(page, str(item.get("留ㅻЪID", "")))
            except Exception:
                detail = {}
            finally:
                await self._page_pool.put(page)
            return apply_mobile_detail(dict(item), detail)

        tasks = [asyncio.create_task(_fetch_one(item)) for item in items]
        result = []
        interrupted = False
        try:
            pending_tasks = set(tasks)
            while pending_tasks:
                if self.thread._should_stop():
                    interrupted = True
                    break
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    try:
                        result.append(await task)
                    except Exception:
                        continue
        finally:
            if interrupted:
                for task in tasks:
                    if not task.done():
                        task.cancel()
            pending = [task for task in tasks if not task.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return result

    @staticmethod
    def _candidate_paths(asset_type: str) -> list[tuple[str, str]]:
        if asset_type == "VL":
            return [("houses", "VL"), ("complexes", "APT")]
        if asset_type == "APT":
            return [("complexes", "APT"), ("houses", "VL")]
        return [("complexes", "APT"), ("houses", "VL")]

    async def _get_ms(self):
        if not self._desktop_page:
            return None
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self._desktop_page.url)
        ms = parse_qs(parsed.query).get("ms", [None])[0]
        if not ms:
            return None
        try:
            lat, lon, zoom = ms.split(",")
            return float(lat), float(lon), float(zoom)
        except Exception:
            return None

    async def _wheel_to_zoom(self, target_zoom: int, delay_ms: int = 300):
        if not self._desktop_page:
            return
        for _ in range(20):
            if self.thread._should_stop():
                return
            current = await self._get_ms()
            if not current:
                await self._desktop_page.wait_for_timeout(delay_ms)
                continue
            _, _, zoom = current
            zoom = round(zoom)
            if zoom == target_zoom:
                return
            await self._desktop_page.mouse.move(960, 540)
            await self._desktop_page.mouse.wheel(0, -300 if target_zoom > zoom else 300)
            await self._desktop_page.wait_for_timeout(delay_ms)

    async def _drag_to_latlon(self, lat: float, lon: float, tolerance_px: float = 3.5):
        if not self._desktop_page:
            return
        import math

        from src.core.services.map_geometry import ll_to_pixel

        for _ in range(18):
            if self.thread._should_stop():
                return
            current = await self._get_ms()
            if not current:
                await self._desktop_page.wait_for_timeout(300)
                continue
            current_lat, current_lon, zoom = current
            x1, y1 = ll_to_pixel(current_lat, current_lon, zoom)
            x2, y2 = ll_to_pixel(lat, lon, zoom)
            dx, dy = x2 - x1, y2 - y1
            distance = math.hypot(dx, dy)
            if distance <= tolerance_px:
                return
            step = min(800.0, distance)
            ratio = step / (distance + 1e-9)
            mx, my = dx * ratio, dy * ratio
            await self._desktop_page.mouse.move(960, 540)
            await self._desktop_page.mouse.down()
            await self._desktop_page.mouse.move(960 - mx, 540 - my, steps=20)
            await self._desktop_page.mouse.up()
            await self._desktop_page.wait_for_timeout(350)

    async def _human_like_recenter(self, lat: float, lon: float, zoom: int):
        await self._wheel_to_zoom(max(9, zoom - 5))
        await self._drag_to_latlon(lat, lon)
        await self._wheel_to_zoom(zoom)
        await self._drag_to_latlon(lat, lon)

    async def _switch_to_listing_markers(self):
        if not self._desktop_page:
            return False
        for text in ["상세매물검색", "매물", "매물검색", "매물 보기"]:
            try:
                await self._desktop_page.locator(f"text={text}").first.click(timeout=1200)
                await self._desktop_page.wait_for_timeout(500)
                return True
            except Exception:
                continue
        try:
            await self._desktop_page.locator('button:has-text("유형")').first.click(timeout=1200)
            await self._desktop_page.wait_for_timeout(300)
            await self._desktop_page.locator("text=매물").first.click(timeout=1200)
            await self._desktop_page.wait_for_timeout(500)
            return True
        except Exception:
            return False


