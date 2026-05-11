from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

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

DEFAULT_SMOKE_COMPLEX_ID = "3833"
DEFAULT_SMOKE_ARTICLE_ID = "2625154515"


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
    complex_id: str = DEFAULT_SMOKE_COMPLEX_ID,
    article_id: str = DEFAULT_SMOKE_ARTICLE_ID,
    include_article_lookup: bool = True,
    include_geo_marker: bool = True,
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
) -> tuple[bool, list[str]]:
    probe_urls = list(urls or default_live_smoke_urls())
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
                    "requested_article_id": str(article_id or DEFAULT_SMOKE_ARTICLE_ID),
                    "messages": messages,
                },
                fp,
                ensure_ascii=False,
                indent=2,
            )
    return ok, messages
