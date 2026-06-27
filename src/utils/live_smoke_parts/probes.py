from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from src.core.services.article_api import build_article_api_url
from src.utils.helpers import ChromeParamHelper
from src.utils.paths import BASE_DIR, DATA_DIR, is_frozen_runtime
from src.core.services.detail_fetcher import fetch_mobile_article_detail

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False
from src.core.parser import NaverURLParser
from src.utils.live_smoke_parts.helpers import (
    DEFAULT_SMOKE_ARTICLE_ID,
    DEFAULT_SMOKE_COMPLEX_ID,
    _append_reason,
    _build_smoke_line,
    _capture_response_status,
    _detail_field_presence,
    _navigate_probe,
    _new_smoke_page,
)


async def _run_home_probes(page, urls: list[str], timeout_ms: int) -> tuple[bool, list[str]]:
    overall_ok = True
    messages: list[str] = []
    for url in urls:
        try:
            result = await _navigate_probe(page, url, timeout_ms)
            messages.append(
                _build_smoke_line(
                    ok=bool(result["ok"]),
                    kind="home",
                    target=url,
                    final_url=str(result["final_url"] or ""),
                    status=result["status"],
                    title=str(result["title"] or ""),
                    reason=str(result["reason"] or ""),
                )
            )
            overall_ok = overall_ok and bool(result["ok"])
        except Exception as exc:
            messages.append(f"[fail] [home] {url} -> exception={exc}")
            overall_ok = False
    return overall_ok, messages


async def _run_article_api_probe(context, complex_id: str, timeout_ms: int) -> tuple[bool, str, str, int | None]:
    cid = str(complex_id or "").strip()
    if not cid:
        return False, "[fail] [article-api] missing complex id", "", None

    target_url = build_article_api_url("complexes", cid, "매매", "APT", page=1)
    final_url = target_url
    status = None
    article_count = None
    sample_article_id = ""
    reason = ""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "referer": f"https://new.land.naver.com/complexes/{cid}",
    }

    if hasattr(context, "new_page"):
        page = None
        captured = {}
        captured_event = asyncio.Event()

        def _handle_request(request):
            try:
                url = str(getattr(request, "url", "") or "")
                if f"/api/articles/complex/{cid}" not in url or captured_event.is_set():
                    return
                captured["url"] = url
                captured["headers"] = dict(getattr(request, "headers", {}) or {})
                captured_event.set()
            except Exception:
                return None

        try:
            page = await _new_smoke_page(context)
            page.on("request", _handle_request)
            await page.goto(
                f"https://new.land.naver.com/complexes/{cid}",
                wait_until="domcontentloaded",
                timeout=max(1000, int(timeout_ms)),
            )
            try:
                await asyncio.wait_for(captured_event.wait(), timeout=max(0.5, float(timeout_ms) / 1000.0))
            except Exception:
                pass
            captured_url = str(captured.get("url", "") or "")
            captured_headers = dict(captured.get("headers", {}) or {})
            auth_header = str(captured_headers.get("authorization", "") or captured_headers.get("Authorization", "") or "")
            if captured_url:
                target_url = captured_url
                final_url = captured_url
            if auth_header:
                headers["authorization"] = auth_header
            if captured_headers.get("referer"):
                headers["referer"] = str(captured_headers.get("referer") or "")
        except Exception as exc:
            reason = _append_reason(reason, f"article_api_auth_capture:{type(exc).__name__}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

    try:
        response = await context.request.get(
            target_url,
            headers=headers,
            timeout=max(1000, int(timeout_ms)),
        )
        raw_status = getattr(response, "status", None)
        status = int(raw_status) if raw_status is not None else None
        if status is not None and status >= 400:
            reason = _append_reason(reason, f"article_api_http_{status}")
        payload = await response.json()
        article_list = payload.get("articleList") or payload.get("articles") or []
        if not isinstance(article_list, list):
            reason = _append_reason(reason, "article_list_not_list")
        else:
            article_count = len(article_list)
            for article in article_list:
                if not isinstance(article, dict):
                    continue
                aid = str(article.get("articleNo") or article.get("atclNo") or "").strip()
                if aid:
                    sample_article_id = aid
                    break
            if article_count <= 0:
                reason = _append_reason(reason, "articles_empty")
    except Exception as exc:
        reason = _append_reason(reason, f"article_api_exception:{type(exc).__name__}:{exc}")

    ok = bool(status is None or status < 400) and article_count is not None and int(article_count) > 0
    extra = (
        f"api_articles={status if status is not None else '-'} "
        f"article_count={article_count if article_count is not None else '-'} "
        f"sample_article={sample_article_id or '-'}"
    )
    return ok, _build_smoke_line(
        ok=ok,
        kind="article-api",
        target=target_url,
        final_url=final_url,
        status=status,
        title="",
        reason=reason,
        extra=extra,
    ), sample_article_id, int(article_count) if article_count is not None else None


async def _capture_complex_articles(page, complex_id: str, timeout_ms: int) -> dict:
    cid = str(complex_id or "").strip()
    expected = f"/api/articles/complex/{cid}"
    state = {
        "seen": False,
        "status": None,
        "article_count": None,
        "sample_article_id": "",
        "json_error": "",
    }
    matched_event = asyncio.Event()
    pending_tasks: set[asyncio.Task] = set()

    async def _consume(response):
        try:
            url = str(getattr(response, "url", "") or "")
            if expected not in url:
                return
            state["seen"] = True
            raw_status = getattr(response, "status", None)
            state["status"] = int(raw_status) if raw_status is not None else None
            try:
                payload = await response.json()
                article_list = payload.get("articleList") or payload.get("articles") or []
                if isinstance(article_list, list):
                    state["article_count"] = len(article_list)
                    for article in article_list:
                        if not isinstance(article, dict):
                            continue
                        aid = str(article.get("articleNo") or article.get("atclNo") or "").strip()
                        if aid:
                            state["sample_article_id"] = aid
                            break
                else:
                    state["json_error"] = "article_list_not_list"
            except Exception as exc:
                state["json_error"] = f"{type(exc).__name__}:{exc}"
            finally:
                matched_event.set()
        except Exception as exc:
            state["json_error"] = f"{type(exc).__name__}:{exc}"
            matched_event.set()

    def _handle(response):
        try:
            url = str(getattr(response, "url", "") or "")
            if expected not in url:
                return
            task = asyncio.create_task(_consume(response))
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)
        except Exception:
            return None

    can_listen = bool(cid) and hasattr(page, "on") and hasattr(page, "remove_listener")
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
        if pending_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*list(pending_tasks), return_exceptions=True),
                    timeout=0.5,
                )
            except Exception:
                pass
        return state
    finally:
        if can_listen:
            try:
                page.remove_listener("response", _handle)
            except Exception:
                pass


async def _run_complex_probe_detail(page, complex_id: str, timeout_ms: int) -> tuple[bool, str, str, int | None]:
    cid = str(complex_id or "").strip()
    if not cid:
        return False, "[fail] [complex] missing complex id", "", None

    target_url = f"https://new.land.naver.com/complexes/{cid}"
    capture_task = asyncio.create_task(_capture_complex_articles(page, cid, timeout_ms))
    await asyncio.sleep(0)
    result = await _navigate_probe(page, target_url, timeout_ms)
    article_capture = await capture_task
    articles_seen = bool(article_capture.get("seen", False))
    articles_status = article_capture.get("status")
    article_count = article_capture.get("article_count")
    sample_article_id = str(article_capture.get("sample_article_id", "") or "")
    reason = str(result["reason"] or "")
    if not articles_seen:
        reason = _append_reason(reason, "articles_capture_missing")
    elif articles_status is not None and int(articles_status) >= 400:
        reason = _append_reason(reason, f"articles_http_{int(articles_status)}")
    json_error = str(article_capture.get("json_error", "") or "")
    if json_error:
        reason = _append_reason(reason, f"articles_json_error:{json_error}")
    if article_count is None and articles_seen:
        reason = _append_reason(reason, "articles_count_missing")
    elif article_count is not None and int(article_count) <= 0:
        reason = _append_reason(reason, "articles_empty")
    ok = (
        bool(result["ok"])
        and articles_seen
        and (articles_status is None or int(articles_status) < 400)
        and article_count is not None
        and int(article_count) > 0
    )
    extra = (
        f"api_articles={articles_status if articles_status is not None else '-'} "
        f"article_count={article_count if article_count is not None else '-'} "
        f"sample_article={sample_article_id or '-'}"
    )
    return ok, _build_smoke_line(
        ok=ok,
        kind="complex",
        target=target_url,
        final_url=str(result["final_url"] or ""),
        status=result["status"],
        title=str(result["title"] or ""),
        reason=reason,
        extra=extra,
    ), sample_article_id, int(article_count) if article_count is not None else None


async def _run_complex_probe(page, complex_id: str, timeout_ms: int) -> tuple[bool, str]:
    ok, line, _sample_article_id, _article_count = await _run_complex_probe_detail(page, complex_id, timeout_ms)
    return ok, line


async def _run_detail_probe(page, article_id: str, timeout_ms: int) -> tuple[bool, str]:
    aid = str(article_id or "").strip()
    if not aid:
        return False, "[fail] [detail] missing article id"

    target_url = f"https://fin.land.naver.com/articles/{aid}"
    expected_agent = f"/front-api/v1/article/agent?articleNumber={aid}"
    capture_task = asyncio.create_task(
        _capture_response_status(page, lambda url: expected_agent in str(url or ""), timeout_ms)
    )
    result = await _navigate_probe(page, target_url, timeout_ms)
    reason = str(result["reason"] or "")
    final_url = str(result["final_url"] or "")
    lower_final_url = final_url.lower()
    agent_seen, agent_status = await capture_task
    if not agent_seen:
        reason = _append_reason(reason, "agent_capture_missing")
        if "/map" in lower_final_url:
            reason = _append_reason(reason, "generic_map_only")
    elif agent_status is not None and int(agent_status) >= 400:
        reason = _append_reason(reason, f"agent_http_{int(agent_status)}")
    ok = bool(result["ok"]) and agent_seen and (agent_status is None or int(agent_status) < 400)
    return ok, _build_smoke_line(
        ok=ok,
        kind="detail",
        target=target_url,
        final_url=final_url,
        status=result["status"],
        title=str(result["title"] or ""),
        reason=reason,
        extra=f"agent_api={agent_status if agent_status is not None else '-'}",
    )


async def _run_detail_field_probe(page, article_id: str, timeout_ms: int) -> tuple[bool, str]:
    aid = str(article_id or "").strip()
    if not aid:
        return False, "[fail] [detail-fields] missing article id"

    try:
        if hasattr(page, "set_default_timeout"):
            page.set_default_timeout(max(1000, int(timeout_ms or 12000)))
        detail = await fetch_mobile_article_detail(page, aid)
        title = await page.title()
    except Exception as exc:
        return False, (
            f"[fail] [detail-fields] https://fin.land.naver.com/articles/{aid} -> "
            f"{getattr(page, 'url', '') or '-'} status=- reason=detail_exception:{type(exc).__name__}: {exc}"
        )

    presence = _detail_field_presence(detail if isinstance(detail, dict) else {})
    parse_state = str(presence["parse_state"] or "")
    core_field_count = int(presence["core_field_count"] or 0)
    ok = parse_state in {"partial", "success"} and core_field_count > 0
    reason = "" if ok else f"parse_state={parse_state},core_field_count={core_field_count}"
    extra = (
        f"parse_state={parse_state} "
        f"source={presence['source']} "
        f"core_field_count={core_field_count} "
        f"missing_field_count={presence['missing_field_count']} "
        f"network_response_count={presence['network_response_count']} "
        f"hydration_hit={presence['hydration_hit']}"
    )
    return ok, _build_smoke_line(
        ok=ok,
        kind="detail-fields",
        target=f"https://fin.land.naver.com/articles/{aid}",
        final_url=str(getattr(page, "url", "") or ""),
        status=None,
        title=str(title or ""),
        reason=reason,
        extra=extra,
    )


async def _run_geo_marker_probe(page, complex_id: str, timeout_ms: int) -> tuple[bool, str]:
    cid = str(complex_id or "").strip()
    if not cid:
        return False, "[fail] [geo-marker] missing complex id"
    target_url = f"https://new.land.naver.com/complexes/{cid}?ms=37.5608,126.9888,15&a=APT"
    capture_task = asyncio.create_task(
        _capture_response_status(
            page,
            lambda url: "complexes/single-markers" in str(url or "") or "houses/single-markers" in str(url or ""),
            timeout_ms,
        )
    )
    result = await _navigate_probe(page, target_url, timeout_ms)
    clicked = False
    for selector in [
        "text=상세매물검색",
        "text=매물",
        'button[aria-label*="매물"]',
        '[role="button"][aria-label*="매물"]',
        'button:has-text("매물")',
    ]:
        try:
            await page.locator(selector).first.click(timeout=1000)
            clicked = True
            await page.wait_for_timeout(500)
            break
        except Exception:
            continue
    marker_seen, marker_status = await capture_task
    reason = str(result["reason"] or "")
    if not clicked:
        reason = _append_reason(reason, "marker_switch_click_missing")
    if not marker_seen:
        reason = _append_reason(reason, "marker_api_capture_missing")
    elif marker_status is not None and int(marker_status) >= 400:
        reason = _append_reason(reason, f"marker_api_http_{int(marker_status)}")
    ok = bool(result["ok"]) and clicked and marker_seen and (marker_status is None or int(marker_status) < 400)
    return ok, _build_smoke_line(
        ok=ok,
        kind="geo-marker",
        target=target_url,
        final_url=str(result["final_url"] or ""),
        status=result["status"],
        title=str(result["title"] or ""),
        reason=reason,
        extra=f"marker_api={marker_status if marker_status is not None else '-'} clicked={1 if clicked else 0}",
    )


def _run_article_lookup_probe(article_id: str) -> tuple[bool, str]:
    aid = str(article_id or "").strip()
    if not aid:
        return False, "[fail] [article-lookup] missing article id"
    try:
        from src.core.parser import NaverURLParser

        resolved = NaverURLParser.resolve_article_complex(aid)
    except Exception as exc:
        return False, f"[fail] [article-lookup] {aid} -> exception={exc}"
    cid = str(resolved.get("complex_id", "") or "") if isinstance(resolved, dict) else ""
    asset_type = str(resolved.get("asset_type", "") or "") if isinstance(resolved, dict) else ""
    source = str(resolved.get("source", "") or "") if isinstance(resolved, dict) else ""
    ok = bool(cid)
    return ok, (
        f"{'[ok]' if ok else '[fail]'} [article-lookup] {aid} -> "
        f"complex_id={cid or '-'} asset_type={asset_type or '-'} source={source or '-'}"
    )
