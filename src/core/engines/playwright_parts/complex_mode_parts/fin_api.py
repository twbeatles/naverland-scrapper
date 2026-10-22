from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.core.services.article_api import MAX_ARTICLE_API_PAGES
from src.core.services.fin_article_api import parse_fin_article_list, parse_fin_complex_info
from src.core.services.site_contract import (
    FIN_API_ORIGIN_PAGE,
    build_fin_article_list_body,
    build_fin_complex_info_url,
    fin_article_list_url,
)

if TYPE_CHECKING:
    from src.core.engines.playwright_engine import *  # noqa: F403


class PlaywrightFinApiMixin:
    """fin.land front-api article list (primary path since 2026-10-22).

    front-api answers 429 to out-of-browser requests, so calls run as
    ``fetch`` inside a desktop-context page parked on a fin.land origin URL.
    """

    # Class attributes, not module globals: mixin methods are rebound to the
    # playwright_engine facade globals (src/utils/mixin_rebind.py).
    FIN_FETCH_JS = """async ([url, method, body, timeoutMs]) => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutMs);
      const opt = {method, headers: {accept: 'application/json'}, signal: ctrl.signal};
      if (body !== null) { opt.body = JSON.stringify(body); opt.headers['content-type'] = 'application/json'; }
      try {
        const r = await fetch(url, opt);
        return {status: r.status, body: await r.text()};
      } catch (e) {
        return {status: 0, body: String(e)};
      } finally { clearTimeout(timer); }
    }"""

    FIN_MIN_PAGE_DELAY_SEC = 0.4

    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _fin_front_api_enabled(self, asset_type: str) -> bool:
        # APT -> /complex/article/list, VL -> /complex/villa/article/list.
        return bool(getattr(self.thread, "fin_front_api_enabled", True))

    async def _fin_complex_exists(self, cid: str, asset_type: str) -> bool | None:
        """True/False from fin info API; ``None`` when the check itself failed.

        Unknown numbers answer a success envelope without ``result`` (2026-10-22).
        """
        import json

        try:
            status, text = await self._fin_fetch(build_fin_complex_info_url(cid, asset_type=asset_type))
        except Exception:
            return None
        if status != 200:
            return None
        try:
            return bool(parse_fin_complex_info(json.loads(text)).get("name"))
        except (TypeError, ValueError):
            return None

    async def _ensure_fin_api_page(self):
        page = getattr(self, "_fin_api_page", None)
        if page is not None:
            try:
                if not page.is_closed():
                    return page
            except Exception:
                pass
        context = self._desktop_context
        if context is None:
            return None
        page = await context.new_page()
        try:
            await page.goto(
                FIN_API_ORIGIN_PAGE,
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms(),
            )
        except Exception:
            try:
                await page.close()
            except Exception:
                pass
            raise
        self._fin_api_page = page
        return page

    async def _fin_fetch(self, url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, str]:
        page = await self._ensure_fin_api_page()
        if page is None:
            return 0, "fin api page unavailable"
        timeout_ms = max(1500, self._article_api_timeout_ms() * 3)
        result = await page.evaluate(self.FIN_FETCH_JS, [url, method, body, timeout_ms])
        if not isinstance(result, dict):
            return 0, ""
        try:
            status = int(result.get("status", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        return status, str(result.get("body", "") or "")

    def _record_fin_api_failure(self, reason: str, *, status: str = "") -> None:
        stats = self.thread.stats
        stats["fin_api_fail_count"] = int(stats.get("fin_api_fail_count", 0)) + 1
        stats["fin_api_last_status"] = str(status or reason or "unknown")
        failures = stats.setdefault("fin_api_failure_reasons", {})
        key = str(reason or "unknown")
        failures[key] = int(failures.get(key, 0)) + 1

    async def _fetch_fin_article_list(
        self,
        *,
        name: str,
        cid: str,
        trade_type: str,
        path_asset: str,
        mode: str,
        source_lat: float | None,
        source_lon: float | None,
        source_zoom: int | None,
        marker_id: str,
        seen_ids: set[str],
    ) -> dict | None:
        """Cursor-paginate fin article list; ``None`` means fall back to new.land."""
        import json

        if self._desktop_context is None:
            return None
        all_raw_items: list[dict] = []
        last_info: list = []
        seed = ""
        page_no = 0
        last_successful_page = 0
        failure_reason = ""
        has_next = False
        delay_sec = max(float(self.FIN_MIN_PAGE_DELAY_SEC), self._article_api_page_delay_sec())
        list_url = fin_article_list_url(path_asset)

        while page_no < MAX_ARTICLE_API_PAGES:
            stop = getattr(self.thread, "_should_stop", None)
            if callable(stop) and stop():
                failure_reason = "cancelled"
                break
            page_no += 1
            if page_no > 1:
                await asyncio.sleep(delay_sec)
            body = build_fin_article_list_body(cid, trade_type, last_info=last_info, seed=seed)
            status, text = 0, ""
            # Retry transport/5xx once at the same cursor; never retry 429.
            for attempt in range(2):
                try:
                    status, text = await self._fin_fetch(list_url, method="POST", body=body)
                except Exception as exc:
                    status, text = 0, type(exc).__name__
                if status == 429 or (0 < status < 500):
                    break
                if attempt == 0:
                    await asyncio.sleep(0.5)
            self.thread.stats["fin_api_last_status"] = str(status)
            if status != 200:
                if status == 429:
                    failure_reason = "rate_limited"
                elif status == 0:
                    failure_reason = "request_failed"
                else:
                    failure_reason = "http_error"
                self._record_fin_api_failure(failure_reason, status=str(status))
                break
            try:
                parsed = parse_fin_article_list(json.loads(text))
            except (TypeError, ValueError):
                parsed = None
            if parsed is None:
                failure_reason = "invalid_payload"
                self._record_fin_api_failure(failure_reason, status=str(status))
                break
            raw_items, valid = self._normalize_article_api_payload(
                {"articleList": parsed["articles"]},
                name=name,
                cid=cid,
                trade_type=trade_type,
                path_asset=path_asset,
                mode=mode,
                source_lat=source_lat,
                source_lon=source_lon,
                source_zoom=source_zoom,
                marker_id=marker_id,
                seen_ids=seen_ids,
            )
            all_raw_items.extend(raw_items)
            if not valid:
                failure_reason = "invalid_payload"
                self._record_fin_api_failure(failure_reason, status=str(status))
                break
            if page_no == 1 and not parsed["articles"]:
                # Empty is valid for a real complex, but legacy IDs (e.g. old new.land
                # house numbers) are unknown to fin: let the caller fall back then.
                exists = await self._fin_complex_exists(cid, path_asset)
                if exists is False:
                    self._record_fin_api_failure("unknown_complex", status=str(status))
                    if str(path_asset or "").upper() == "VL":
                        self.thread.log(
                            f"   빌라 번호 {cid}는 새 네이버 부동산에 없습니다. 예전 번호일 수 있으니 "
                            "「지도로 찾기」나 「단지 찾기」로 다시 추가해 주세요.",
                            30,
                        )
                    return None
            last_successful_page = page_no
            has_next = bool(parsed["has_next"])
            last_info = parsed["last_info"]
            seed = parsed["seed"] or seed
            if not has_next:
                break
            if not last_info:
                failure_reason = "missing_cursor"
                self._record_fin_api_failure(failure_reason, status=str(status))
                break

        if has_next and not failure_reason and page_no >= MAX_ARTICLE_API_PAGES:
            self._mark_article_api_page_cap_truncation()
            failure_reason = "page_cap"
        if last_successful_page == 0 and not all_raw_items:
            # Nothing usable from fin: let the caller try the legacy new.land path.
            return None
        stats = self.thread.stats
        stats["fin_api_hit_count"] = int(stats.get("fin_api_hit_count", 0)) + 1
        return {
            "raw_items": all_raw_items,
            "response_seen": True,
            "parse_success": True,
            "drain_timed_out": False,
            "response_match_count": page_no,
            "final_url": list_url,
            "block_like_redirect": False,
            "block_reason": "",
            "capture_failed": False,
            "failure_reason": failure_reason,
            "api_fast_path": True,
            "collection_status": "partial" if failure_reason else "complete",
            "last_successful_page": last_successful_page,
            "failed_page": page_no if failure_reason else 0,
        }
