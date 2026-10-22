from __future__ import annotations

from src.core.services.detail_fetcher_parts.field_merge import (
    _fields_from_named_tree,
    _merge_detail_field_maps,
)
from src.core.services.detail_fetcher_parts.text_extract import _build_detail_corpus


def build_front_api_agent_url(article_no: str) -> str:
    from src.core.services.site_contract import build_front_api_agent_url as _build

    return _build(article_no)


def build_front_api_basic_info_url(article_no: str, *, real_estate_type: str = "A01", trade_type: str = "A1") -> str:
    from src.core.services.site_contract import build_front_api_basic_info_url as _build

    return _build(article_no, real_estate_type=real_estate_type, trade_type=trade_type)


def build_front_api_article_key_url(article_no: str) -> str:
    from src.core.services.site_contract import build_front_api_article_key_url as _build

    return _build(article_no)


def _article_type_codes(payload) -> tuple[str, str]:
    """(realEstateType, tradeType) from an ``/article/key`` payload."""
    result = payload.get("result") if isinstance(payload, dict) else None
    types = result.get("type") if isinstance(result, dict) else None
    if not isinstance(types, dict):
        return "", ""
    return str(types.get("realEstateType", "") or ""), str(types.get("tradeType", "") or "")


def parse_front_api_agent_payload(payload) -> dict:
    """Map fin.land agent/basicInfo JSON into detail field dict."""
    if not isinstance(payload, dict):
        return {}
    # Some APIs wrap under result/data
    candidates = [payload]
    for key in ("result", "data", "body", "articleAgent", "agent"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
        elif isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    candidates.append(item)
    merged: dict = {}
    for tree in candidates:
        extracted = _fields_from_named_tree(tree)
        merged = _merge_detail_field_maps(merged, extracted)
    # basicInfo priceInfo.previousDeposit is the sitting tenant's deposit in won
    # (the text money parser would read bare digits as 만원).
    for tree in candidates:
        price_info = tree.get("priceInfo") if isinstance(tree, dict) else None
        if isinstance(price_info, dict):
            try:
                previous = int(price_info.get("previousDeposit") or 0)
            except (TypeError, ValueError):
                previous = 0
            if previous > 0:
                merged["기전세금(원)"] = previous
                break
    return {k: v for k, v in merged.items() if v not in (None, "", 0, 0.0)}


def _request_context_from_page(detail_page):
    if detail_page is None:
        return None
    for attr in ("request",):
        request = getattr(detail_page, attr, None)
        if request is not None and hasattr(request, "get"):
            return request
    context = getattr(detail_page, "context", None)
    if context is not None:
        request = getattr(context, "request", None)
        if request is not None and hasattr(request, "get"):
            return request
    return None


_PAGE_FETCH_JS = """async ([url, timeoutMs]) => {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, {headers: {accept: 'application/json'}, signal: ctrl.signal});
    return {status: r.status, body: await r.text()};
  } catch (e) {
    return {status: 0, body: ''};
  } finally { clearTimeout(timer); }
}"""


def _page_on_fin_origin(page) -> bool:
    try:
        return str(getattr(page, "url", "") or "").startswith("https://fin.land.naver.com/")
    except Exception:
        return False


async def _fetch_front_api_json_in_page(page, url: str, *, timeout_ms: int = 8000):
    """In-page fetch from a fin.land origin (out-of-browser requests get 429)."""
    import json

    try:
        result = await page.evaluate(_PAGE_FETCH_JS, [url, max(1000, int(timeout_ms or 8000))])
    except Exception:
        return None, None
    if not isinstance(result, dict):
        return None, None
    try:
        status = int(result.get("status", 0) or 0) or None
    except (TypeError, ValueError):
        status = None
    try:
        payload = json.loads(str(result.get("body", "") or ""))
    except (TypeError, ValueError):
        return status, None
    return status, payload


async def _fetch_front_api_json(request_context, url: str, *, referer: str, timeout_ms: int = 8000):
    if request_context is None or not url:
        return None, None
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "referer": referer or "https://fin.land.naver.com/",
    }
    try:
        response = await request_context.get(url, headers=headers, timeout=max(1000, int(timeout_ms or 8000)))
    except TypeError:
        try:
            response = await request_context.get(url, headers=headers)
        except Exception:
            return None, None
    except Exception:
        return None, None
    status = getattr(response, "status", None)
    try:
        payload = await response.json()
    except Exception:
        return status, None
    return status, payload


async def _warm_front_api_session(detail_page, *, timeout_ms: int = 5000) -> bool:
    """Park the page on a fin.land origin so front-api can be fetched in-page.

    Uses the light ``robots.txt`` page instead of the map SPA, which fires
    ~20 side requests per load (2026-10-22).
    """
    if detail_page is None or not hasattr(detail_page, "goto"):
        return False
    if _page_on_fin_origin(detail_page):
        return True
    from src.core.services.site_contract import FIN_API_ORIGIN_PAGE

    try:
        await detail_page.goto(
            FIN_API_ORIGIN_PAGE,
            wait_until="domcontentloaded",
            timeout=max(1000, int(timeout_ms)),
        )
    except Exception:
        return False
    return _page_on_fin_origin(detail_page)


async def _supplement_front_api_artifacts(
    detail_page,
    article_no: str,
    artifacts: dict | None,
    *,
    navigation_timeout_ms: int | None = None,
) -> dict:
    """Explicitly pull fin.land front-api payloads when DOM/detail SPA is empty or 404."""
    artifacts = dict(artifacts or {})
    responses = list(artifacts.get("responses", []) or [])
    existing_urls = {str(item.get("url", "") or "") for item in responses if isinstance(item, dict)}
    request_context = _request_context_from_page(detail_page)
    referer = f"https://fin.land.naver.com/articles/{article_no}"
    timeout_ms = 8000
    if navigation_timeout_ms is not None:
        try:
            timeout_ms = min(15000, max(1500, int(navigation_timeout_ms)))
        except (TypeError, ValueError):
            timeout_ms = 8000

    # A page already on fin.land needs no navigation; others are parked on robots.txt.
    if detail_page is not None and not _page_on_fin_origin(detail_page):
        try:
            artifacts["front_api_session_warmed"] = await _warm_front_api_session(
                detail_page, timeout_ms=min(6000, timeout_ms)
            )
        except Exception:
            artifacts["front_api_session_warmed"] = False

    in_page = _page_on_fin_origin(detail_page)

    async def _get(url: str):
        if in_page:
            return await _fetch_front_api_json_in_page(detail_page, url, timeout_ms=timeout_ms)
        return await _fetch_front_api_json(request_context, url, referer=referer, timeout_ms=timeout_ms)

    # agent (broker/phones) -> key (exact type codes) -> basicInfo only for sales:
    # basicInfo rejects wrong type codes, and previousDeposit matters for 매매 only.
    pending = [build_front_api_agent_url(article_no), build_front_api_article_key_url(article_no)]
    while pending:
        url = pending.pop(0)
        if url in existing_urls:
            continue
        status, payload = await _get(url)
        if status is not None and int(status) == 429:
            artifacts["front_api_rate_limited"] = True
            break
        if payload is None:
            continue
        if status is not None and int(status) >= 400:
            continue
        if "/article/key" in url:
            real_estate_type, trade_code = _article_type_codes(payload)
            if real_estate_type and trade_code == "A1":
                pending.append(
                    build_front_api_basic_info_url(
                        article_no, real_estate_type=real_estate_type, trade_type=trade_code
                    )
                )
            existing_urls.add(url)
            continue
        if isinstance(payload, dict) and payload.get("isSuccess") is False:
            continue
        responses.append({"url": url, "payload": payload, "status": status})
        existing_urls.add(url)

    artifacts["responses"] = responses
    if responses or artifacts.get("hydration_state") or artifacts.get("body_text") or artifacts.get("html_text"):
        artifacts["corpus_text"] = _build_detail_corpus(
            str(artifacts.get("body_text", "") or ""),
            str(artifacts.get("html_text", "") or ""),
            dict(artifacts.get("hydration_state", {}) or {}),
            responses,
        )
    return artifacts
