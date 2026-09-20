from __future__ import annotations

import asyncio
from src.core.services.detail_fetcher_parts.hydration import _read_hydration_state
from src.core.services.detail_fetcher_parts.page_primitives import (
    _drain_pending_tasks,
    _goto_detail_url,
    _read_body_text,
    _spawn_response_task,
)
from src.core.services.detail_fetcher_parts.text_extract import _build_detail_corpus


async def _collect_detail_artifacts(detail_page, url: str, *, navigation_timeout_ms: int | None = None) -> dict:
    responses: list[dict] = []
    pending_tasks: set[asyncio.Task] = set()

    async def _consume(response):
        response_url = str(getattr(response, "url", "") or "")
        if not response_url:
            return
        lower_url = response_url.lower()
        if not any(
            token in lower_url
            for token in ("land.naver.com", "/api/", "front-api", "article", "realtor", "agent")
        ):
            return
        try:
            payload = await response.json()
        except Exception:
            return
        status = getattr(response, "status", None)
        responses.append({"url": response_url, "payload": payload, "status": status})

    def _handle(response):
        try:
            _spawn_response_task(pending_tasks, _consume(response))
        except Exception:
            return None

    can_listen = hasattr(detail_page, "on") and hasattr(detail_page, "remove_listener")
    if can_listen:
        try:
            detail_page.on("response", _handle)
        except Exception:
            can_listen = False
    try:
        await _goto_detail_url(detail_page, url, navigation_timeout_ms=navigation_timeout_ms)
        body_text = await _read_body_text(detail_page)
        try:
            html_text = await detail_page.content()
        except Exception:
            html_text = ""
        hydration_state = await _read_hydration_state(detail_page)
    finally:
        if can_listen:
            try:
                detail_page.remove_listener("response", _handle)
            except Exception:
                pass
        await _drain_pending_tasks(pending_tasks)

    corpus_text = _build_detail_corpus(body_text, html_text, hydration_state, responses)
    return {
        "body_text": body_text,
        "html_text": html_text,
        "hydration_state": hydration_state,
        "responses": responses,
        "corpus_text": corpus_text,
    }


async def _collect_inline_artifacts(detail_page, body_text: str = "") -> dict:
    if not body_text:
        body_text = await _read_body_text(detail_page, attempts=4, wait_ms=250)
    try:
        html_text = await detail_page.content()
    except Exception:
        html_text = ""
    hydration_state = await _read_hydration_state(detail_page)
    corpus_text = _build_detail_corpus(body_text, html_text, hydration_state, [])
    return {
        "body_text": body_text,
        "html_text": html_text,
        "hydration_state": hydration_state,
        "responses": [],
        "corpus_text": corpus_text,
    }
