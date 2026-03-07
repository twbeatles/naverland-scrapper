from __future__ import annotations


class PlaywrightComplexModeMixin:
    async def _run_complex_mode(self):
        await self._ensure_started()
        total = len(self.thread.targets) * len(self.thread.trade_types)
        current = 0
        processed_pairs = set()
        for name, cid in self.thread.targets:
            if self.thread._should_stop():
                break
            complex_count = 0
            complex_trade_types = []
            for trade_type in self.thread.trade_types:
                if self.thread._should_stop():
                    break
                await self._check_memory_and_recycle_if_needed("complex_loop")
                self.thread._current_pair = self.thread._pair_key(name, cid, trade_type)
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
                    complex_trade_types.append(trade_type)
                    processed_pairs.add((str(cid), str(trade_type)))
                    self.thread.stats["by_trade_type"][trade_type] = (
                        self.thread.stats["by_trade_type"].get(trade_type, 0) + count
                    )
                    self.thread._mark_pair_processed(name, cid, trade_type)
                    self.thread.log(f"   ??{count}嫄??섏쭛")
                except Exception as exc:
                    self.thread.log(f"   ???ㅻ쪟: {exc}", 40)
                    if self.thread.fallback_engine_enabled and not self._fallback_used:
                        self._fallback_used = True
                        self.thread.log("   ??Selenium fallback?쇰줈 ?꾪솚?⑸땲??", 30)
                        self.thread._run_fallback_selenium(start_name=name, start_cid=cid, start_trade=trade_type)
                        self.thread._current_pair = None
                        return
                if not self.thread._sleep_interruptible(self.thread._get_speed_delay()):
                    break
            self.thread._flush_history_updates(force=True)
            if not complex_trade_types:
                continue
            self.thread.record_crawl_history(
                name,
                cid,
                ",".join(complex_trade_types),
                int(complex_count),
                engine=self.engine_name,
                mode=self.thread.crawl_mode,
            )
            self.thread.complex_finished_signal.emit(name, cid, ",".join(complex_trade_types), int(complex_count))
        self.thread._current_pair = None
        self.thread._finalize_disappeared_articles(processed_pairs)

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

        collect_result = await self._collect_target_raw_items(
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
        raw_items = list(collect_result.get("raw_items", []) or [])
        response_seen = bool(collect_result.get("response_seen", False))
        drain_timed_out = bool(collect_result.get("drain_timed_out", False))
        if cache:
            if raw_items:
                cache.set(cid, trade_type, raw_items, **cache_ctx)
            else:
                ttl_seconds = int(max(0, self.thread.negative_cache_ttl_minutes) * 60)
                if response_seen and not drain_timed_out and ttl_seconds > 0:
                    cache.set(
                        cid,
                        trade_type,
                        [],
                        ttl_seconds=ttl_seconds,
                        reason="confirmed_empty",
                        **cache_ctx,
                    )
                elif drain_timed_out:
                    self.thread.log("   ⚠️ drain timeout detected, negative cache skipped", 30)
        matched = self.thread._process_raw_items(raw_items, trade_type)
        return {
            "count": matched,
            "raw_count": len(raw_items),
            "cache_hit": False,
            "response_seen": response_seen,
            "drain_timed_out": drain_timed_out,
        }

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
    ) -> dict:
        await self._ensure_started()
        raw_items: list[dict] = []
        seen_ids: set[str] = set()
        response_seen = False
        drain_timed_out = False

        for base_kind, path_asset in self._candidate_paths(asset_type):
            page = self._desktop_page
            if page is None:
                break
            pending_tasks: set[asyncio.Task] = set()

            async def _consume(response):
                nonlocal response_seen
                url = response.url
                expected = f"/api/articles/{'house' if base_kind == 'houses' else 'complex'}/{cid}"
                if expected not in url:
                    return
                response_seen = True
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
                    aid = str(item.get("매물ID", "") or item.get("留ㅻЪID", "") or "")
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
                await self._async_retry(
                    f"article goto {base_kind}/{cid}",
                    lambda: page.goto(url, wait_until="domcontentloaded"),
                )
                try:
                    await self._async_retry(
                        f"article load {base_kind}/{cid}",
                        lambda: page.wait_for_load_state("networkidle", timeout=6000),
                    )
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
                _, timed_out = await self._drain_pending_response_tasks(
                    pending_tasks,
                    label=f"article_capture:{base_kind}/{cid}",
                )
                drain_timed_out = drain_timed_out or bool(timed_out)
            if raw_items:
                break

        if not raw_items:
            return {
                "raw_items": [],
                "response_seen": response_seen,
                "drain_timed_out": drain_timed_out,
            }
        enriched = await self._enrich_items_with_mobile_details(raw_items)
        return {
            "raw_items": enriched,
            "response_seen": response_seen,
            "drain_timed_out": drain_timed_out,
        }

    async def _enrich_items_with_mobile_details(self, items: list[dict]) -> list[dict]:
        if not items or self._page_pool is None:
            return items

        async def _fetch_one(item: dict) -> dict:
            page = await self._page_pool.get()
            try:
                article_no = str(item.get("매물ID", "") or item.get("留ㅻЪID", ""))
                detail = await self._async_retry(
                    f"mobile detail {article_no}",
                    lambda: fetch_mobile_article_detail(page, article_no),
                )
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

