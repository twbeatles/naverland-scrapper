from __future__ import annotations

from src.core.services.detail_fetcher_parts.field_merge import (
    _fields_from_named_tree,
    _merge_detail_field_maps,
)
from src.core.services.detail_fetcher_parts.text_extract import _build_detail_corpus


def build_front_api_agent_url(article_no: str) -> str:
    from src.core.services.site_contract import build_front_api_agent_url as _build

    return _build(article_no)


def build_front_api_basic_info_url(article_no: str) -> str:
    from src.core.services.site_contract import build_front_api_basic_info_url as _build

    return _build(article_no)


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
    """Best-effort cookie/auth warm before front-api (new.land + auth/si)."""
    request_context = _request_context_from_page(detail_page)
    if request_context is None:
        return False
    warmed = False
    # Prefer new.land (stable host) so browser context has land cookies.
    try:
        if detail_page is not None and hasattr(detail_page, "goto"):
            current = str(getattr(detail_page, "url", "") or "")
            if "new.land.naver.com" not in current and "fin.land.naver.com" not in current:
                await detail_page.goto(
                    "https://new.land.naver.com/",
                    wait_until="domcontentloaded",
                    timeout=max(1000, int(timeout_ms)),
                )
                warmed = True
    except Exception:
        pass
    try:
        status, payload = await _fetch_front_api_json(
            request_context,
            "https://fin.land.naver.com/front-api/v1/auth/si",
            referer="https://fin.land.naver.com/",
            timeout_ms=timeout_ms,
        )
        if status is not None and int(status) < 400 and payload is not None:
            warmed = True
    except Exception:
        pass
    return warmed


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

    # One warm per page object to reduce repeated auth traffic.
    if request_context is not None and not getattr(detail_page, "_front_api_session_warmed", False):
        try:
            await _warm_front_api_session(detail_page, timeout_ms=min(6000, timeout_ms))
            try:
                setattr(detail_page, "_front_api_session_warmed", True)
            except Exception:
                pass
            artifacts["front_api_session_warmed"] = True
        except Exception:
            artifacts["front_api_session_warmed"] = False

    for url in (
        build_front_api_agent_url(article_no),
        build_front_api_basic_info_url(article_no),
    ):
        if url in existing_urls:
            continue
        status, payload = await _fetch_front_api_json(
            request_context,
            url,
            referer=referer,
            timeout_ms=timeout_ms,
        )
        if status is not None and int(status) == 429:
            artifacts["front_api_rate_limited"] = True
            break
        if payload is None:
            continue
        if status is not None and int(status) >= 400:
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
