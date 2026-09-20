from __future__ import annotations

import asyncio


def _is_not_found_body(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return True
    return (
        "요청하신 페이지를 찾을 수 없어요" in body
        or "주소가 변경되거나 삭제되어 요청하신 페이지를 찾을 수 없습니다" in body
    )


def _is_meaningful_body(text: str) -> bool:
    body = str(text or "").strip()
    if len(body) < 80:
        return False
    if _is_not_found_body(body):
        return False
    return True


async def _goto_detail_url(detail_page, url: str, *, navigation_timeout_ms: int | None = None):
    goto_kwargs: dict[str, object] = {"wait_until": "domcontentloaded"}
    if navigation_timeout_ms is not None:
        goto_kwargs["timeout"] = max(1000, int(navigation_timeout_ms))
    await detail_page.goto(url, **goto_kwargs)
    try:
        await detail_page.wait_for_load_state("networkidle", timeout=2000)
    except Exception:
        pass


def _spawn_response_task(pending_tasks: set[asyncio.Task], coro) -> None:
    task = asyncio.create_task(coro)
    pending_tasks.add(task)
    task.add_done_callback(lambda done: pending_tasks.discard(done))


async def _drain_pending_tasks(pending_tasks: set[asyncio.Task], timeout_ms: int = 1500) -> None:
    if not pending_tasks:
        return
    try:
        await asyncio.wait_for(
            asyncio.gather(*list(pending_tasks), return_exceptions=True),
            timeout=max(0.1, float(timeout_ms) / 1000.0),
        )
    except Exception:
        for task in list(pending_tasks):
            if not task.done():
                task.cancel()
        if pending_tasks:
            await asyncio.gather(*list(pending_tasks), return_exceptions=True)


async def _read_body_text(detail_page, attempts: int = 5, wait_ms: int = 300) -> str:
    body_text = ""
    for idx in range(max(1, int(attempts or 1))):
        try:
            body_text = await detail_page.inner_text("body")
        except Exception:
            body_text = ""
        if _is_meaningful_body(body_text):
            return body_text
        if idx + 1 < max(1, int(attempts or 1)):
            try:
                await detail_page.wait_for_timeout(wait_ms)
            except Exception:
                pass
    return body_text
