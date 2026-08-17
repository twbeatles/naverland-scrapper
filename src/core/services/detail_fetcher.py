from __future__ import annotations

import asyncio
import re

from src.core.services.gap_analysis import enrich_gap_fields


def parse_kr_money_to_won(text: str) -> int | None:
    if not text:
        return None
    src = str(text).strip().replace(" ", "").replace(",", "")
    has_won = "원" in src
    src = src.replace("원", "")
    total = 0
    man = 0

    match = re.search(r"(\d+(?:\.\d+)?)억", src)
    if match:
        try:
            total += int(float(match.group(1)) * 100_000_000)
        except (TypeError, ValueError):
            pass
        tail = src.split("억", 1)[1]
        man_match = re.search(r"(\d+)만", tail) or re.search(r"^(\d+)$", tail) or re.search(r"(\d+)천", tail)
        if man_match:
            try:
                man = int(man_match.group(1))
                if "천" in man_match.group(0):
                    man *= 1000
            except (TypeError, ValueError):
                man = 0
    elif re.fullmatch(r"\d+", src):
        return int(src) if has_won else int(src) * 10_000
    else:
        man_match = re.search(r"(\d+)만", src) or re.search(r"(\d+)천만?", src)
        if man_match:
            man = int(man_match.group(1))
            if "천" in man_match.group(0):
                man *= 1000

    return total + man * 10_000


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


async def _read_hydration_state(detail_page) -> dict:
    script = """
    () => {
      const pick = (value) => {
        if (!value || typeof value === "function") {
          return null;
        }
        try {
          return JSON.parse(JSON.stringify(value));
        } catch (error) {
          return null;
        }
      };
      const keys = [
        "__NEXT_DATA__",
        "__NUXT__",
        "__INITIAL_STATE__",
        "__PRELOADED_STATE__",
        "__APOLLO_STATE__",
        "__STATE__",
        "__REDUX_STATE__",
      ];
      const payload = {};
      for (const key of keys) {
        const value = pick(window[key]);
        if (value) {
          payload[key] = value;
        }
      }
      return payload;
    }
    """
    try:
        payload = await detail_page.evaluate(script)
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _flatten_text_fragments(value, sink: list[str], *, limit: int = 4000) -> None:
    if len(sink) >= limit or value is None:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            sink.append(text)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if len(sink) >= limit:
                break
            if isinstance(key, str) and key.strip():
                sink.append(key.strip())
            _flatten_text_fragments(item, sink, limit=limit)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if len(sink) >= limit:
                break
            _flatten_text_fragments(item, sink, limit=limit)
        return


def _build_detail_corpus(body_text: str, html_text: str, hydration_state: dict, responses: list[dict]) -> str:
    chunks: list[str] = []
    if body_text:
        chunks.append(str(body_text))
    if html_text:
        chunks.append(re.sub(r"<[^>]+>", " ", str(html_text)))
    _flatten_text_fragments(hydration_state, chunks)
    _flatten_text_fragments(responses, chunks)
    seen = set()
    ordered = []
    for chunk in chunks:
        token = str(chunk or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return "\n".join(ordered)


def _find_named_value(value, wanted_keys: set[str]):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key or "").strip()
            if normalized in wanted_keys:
                return item
            nested = _find_named_value(item, wanted_keys)
            if nested not in (None, "", [], {}):
                return nested
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            nested = _find_named_value(item, wanted_keys)
            if nested not in (None, "", [], {}):
                return nested
    return None


def _first_phone_from_value(value) -> str:
    if isinstance(value, dict):
        for item in value.values():
            phone = _first_phone_from_value(item)
            if phone:
                return phone
    if isinstance(value, str):
        matches = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", value)
        return matches[0] if matches else ""
    if isinstance(value, (list, tuple)):
        for item in value:
            phone = _first_phone_from_value(item)
            if phone:
                return phone
    return ""


def _phone_list_from_value(value) -> list[str]:
    ordered: list[str] = []

    def _append(phone: str) -> None:
        token = str(phone or "").strip()
        if token and token not in ordered:
            ordered.append(token)

    if isinstance(value, dict):
        for item in value.values():
            for phone in _phone_list_from_value(item):
                _append(phone)
        return ordered
    if isinstance(value, str):
        for match in re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", value):
            _append(match)
        return ordered
    if isinstance(value, (list, tuple)):
        for item in value:
            for phone in _phone_list_from_value(item):
                _append(phone)
    return ordered


_OFFICE_KEYS = {
    "brokerageName",
    "officeName",
    "realtorName",
    "realtorOfficeName",
    "agencyName",
    "cpName",
    "brokerageFirmName",
}
_AGENT_NAME_KEYS = {
    "brokerName",
    "agentName",
    "brokerRepresentativeName",
    "representativeName",
    "realtorRepresentativeName",
    "agentRepresentativeName",
}
_PHONE_KEYS = {
    "phone",
    "phones",
    "telNo",
    "telephone",
    "mobileNo",
    "mobilePhone",
    "cellPhone",
    "brokeragePhone",
    "agentPhone",
    "tel",
    "mobile",
}
_PREV_JEONSE_KEYS = {
    "prevJeonse",
    "prevJeonsePrice",
    "previousJeonse",
    "previousJeonsePrice",
    "warrantPrice",
}


def _merge_detail_field_maps(base: dict, extra: dict | None) -> dict:
    merged = dict(base or {})
    for key, value in dict(extra or {}).items():
        if key.startswith("_"):
            continue
        if value in (None, "", [], {}):
            continue
        current = merged.get(key)
        if current in (None, "", 0, 0.0):
            merged[key] = value
    return merged


def _fields_from_named_tree(source_tree) -> dict:
    fields = {
        "부동산상호": "",
        "중개사이름": "",
        "전화1": "",
        "전화2": "",
        "전세_기간(년)": 0,
        "전세_기간내_최고(원)": 0,
        "전세_기간내_최저(원)": 0,
        "기전세금(원)": 0,
    }
    office = _find_named_value(source_tree, _OFFICE_KEYS)
    if office not in (None, "", [], {}):
        fields["부동산상호"] = str(office).strip()

    agent_name = _find_named_value(source_tree, _AGENT_NAME_KEYS)
    if agent_name not in (None, "", [], {}):
        # Avoid treating office-like blobs as a person name when nested "name" matches first.
        token = str(agent_name).strip()
        if token and token != fields["부동산상호"] and not re.search(r"\d{2,}", token):
            fields["중개사이름"] = token

    phone_value = _find_named_value(source_tree, _PHONE_KEYS)
    phones = _phone_list_from_value(phone_value)
    if not phones:
        phones = _phone_list_from_value(source_tree)
    if phones:
        fields["전화1"] = phones[0]
        if len(phones) >= 2:
            fields["전화2"] = phones[1]

    prev_jeonse_value = _find_named_value(source_tree, _PREV_JEONSE_KEYS)
    prev_jeonse = parse_kr_money_to_won(str(prev_jeonse_value or ""))
    if prev_jeonse:
        fields["기전세금(원)"] = prev_jeonse
    return fields


def _backfill_fields_from_artifacts(fields: dict, artifacts: dict | None) -> dict:
    artifacts = dict(artifacts or {})
    source_tree = {
        "hydration_state": artifacts.get("hydration_state", {}),
        "responses": artifacts.get("responses", []),
    }
    extracted = _fields_from_named_tree(source_tree)
    return _merge_detail_field_maps(fields, extracted)


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


def _parse_detail_fields(body_text: str, *, fallback_text: str = "") -> dict:
    search_space = str(body_text or "")
    combined_text = search_space
    if fallback_text:
        combined_text = f"{combined_text}\n{fallback_text}" if combined_text else str(fallback_text)

    def grab(regex: str, flags: int = 0) -> str:
        for source in (search_space, combined_text):
            if not source:
                continue
            match = re.search(regex, source, flags)
            if match:
                return match.group(1).strip()
        return ""

    prev_jeonse_text = grab(r"기전세금\s*([\d,억\s만]+)") or grab(r"prevJeonse\s*([\d,억\s만]+)")
    prev_jeonse = parse_kr_money_to_won(prev_jeonse_text) if prev_jeonse_text else 0

    lines = [line.strip() for line in combined_text.splitlines() if line.strip()]
    agent_name = ""
    office = ""
    candidate_idx = -1

    for idx, line in enumerate(lines):
        if re.fullmatch(r"[가-힣]{2,4}", line) and line not in ("이미지", "상세보기", "중개사", "중개소"):
            context = "\n".join(lines[max(0, idx - 3): idx + 2])
            if ("중개사" in context) or ("프로필" in context) or ("중개소" in context):
                agent_name = line
                candidate_idx = idx
                break

    office_pattern = re.compile(r"(공인중개사|부동산)")
    if candidate_idx >= 0:
        for line in lines[candidate_idx + 1: candidate_idx + 6]:
            if office_pattern.search(line) and ("상세보기" not in line) and ("전화" not in line):
                office = line
                break
    if not office:
        office_match = re.search(r"중개소\s+([^\n]+)", combined_text)
        if office_match:
            office = office_match.group(1).strip()
    if not office:
        office = (
            grab(r"brokerageName\s+([^\n]+)")
            or grab(r"officeName\s+([^\n]+)")
            or grab(r"realtorName\s+([^\n]+)")
        )
    if not agent_name:
        agent_name = (
            grab(r"brokerName\s+([^\n]+)")
            or grab(r"agentName\s+([^\n]+)")
            or grab(r"brokerRepresentativeName\s+([^\n]+)")
        )

    max_match = re.search(r"(\d+)\s*년\s*내\s*최고\s*([\d,억\s만]+)", combined_text)
    min_match = re.search(r"(\d+)\s*년\s*내\s*최저\s*([\d,억\s만]+)", combined_text)
    period_years = int(max_match.group(1)) if max_match else (int(min_match.group(1)) if min_match else 0)
    jeonse_max = parse_kr_money_to_won(max_match.group(2)) if max_match else 0
    jeonse_min = parse_kr_money_to_won(min_match.group(2)) if min_match else 0
    phones = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", combined_text)
    if not phones:
        phone_text = grab(r"phones?\s+([^\n]+)") or grab(r"phone\s+([^\n]+)")
        phones = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", phone_text)

    return {
        "부동산상호": office,
        "중개사이름": agent_name,
        "전화1": phones[0] if len(phones) >= 1 else "",
        "전화2": phones[1] if len(phones) >= 2 else "",
        "전세_기간(년)": period_years,
        "전세_기간내_최고(원)": jeonse_max or 0,
        "전세_기간내_최저(원)": jeonse_min or 0,
        "기전세금(원)": prev_jeonse or 0,
    }


def _detail_core_field_score(fields: dict) -> int:
    return sum(
        1
        for flag in (
            bool(str(fields.get("부동산상호", "") or "").strip()),
            bool(str(fields.get("중개사이름", "") or "").strip()),
            bool(str(fields.get("전화1", "") or "").strip() or str(fields.get("전화2", "") or "").strip()),
            int(fields.get("기전세금(원)", 0) or 0) > 0,
        )
        if flag
    )


def _detail_candidate_score(fields: dict, meta: dict) -> int:
    core_score = _detail_core_field_score(fields)
    parse_state = str(meta.get("detail_parse_state", "") or "")
    state_bonus = {"failed": 0, "partial": 100, "success": 200}.get(parse_state, 0)
    response_bonus = min(20, int(meta.get("network_response_count", 0) or 0) * 2)
    hydration_bonus = 5 if int(meta.get("hydration_hit", 0) or 0) > 0 else 0
    return state_bonus + core_score * 25 + response_bonus + hydration_bonus


def _merge_detail_artifacts(primary: dict | None, secondary: dict | None) -> dict:
    base = dict(primary or {})
    extra = dict(secondary or {})
    responses = list(base.get("responses", []) or [])
    for item in list(extra.get("responses", []) or []):
        if item not in responses:
            responses.append(item)
    return {
        "body_text": str(extra.get("body_text", "") or base.get("body_text", "") or ""),
        "html_text": str(extra.get("html_text", "") or base.get("html_text", "") or ""),
        "hydration_state": extra.get("hydration_state", {}) or base.get("hydration_state", {}) or {},
        "responses": responses,
        "corpus_text": str(extra.get("corpus_text", "") or base.get("corpus_text", "") or ""),
    }


def _build_detail_meta(source: str, body_text: str, fields: dict, artifacts: dict | None = None) -> dict:
    artifacts = dict(artifacts or {})
    responses = list(artifacts.get("responses", []) or [])
    hydration_state = dict(artifacts.get("hydration_state", {}) or {})
    populated = [
        bool(str(fields.get("부동산상호", "") or "").strip()),
        bool(str(fields.get("중개사이름", "") or "").strip()),
        bool(str(fields.get("전화1", "") or "").strip()),
        bool(str(fields.get("전화2", "") or "").strip()),
        int(fields.get("기전세금(원)", 0) or 0) > 0,
        int(fields.get("전세_기간(년)", 0) or 0) > 0,
        int(fields.get("전세_기간내_최고(원)", 0) or 0) > 0,
        int(fields.get("전세_기간내_최저(원)", 0) or 0) > 0,
    ]
    found_count = sum(1 for flag in populated if flag)
    if found_count >= 3:
        parse_state = "success"
    elif found_count > 0:
        parse_state = "partial"
    else:
        parse_state = "failed"
    return {
        "detail_source": str(source or ""),
        "detail_parse_state": parse_state,
        "missing_field_count": len(populated) - found_count,
        "body_length": len(str(body_text or "").strip()),
        "network_response_count": len(responses),
        "hydration_blob_count": len(hydration_state),
        "hydration_hit": 1 if hydration_state else 0,
    }


async def fetch_mobile_article_detail(
    detail_page,
    article_no: str,
    *,
    navigation_timeout_ms: int | None = None,
    front_api_enabled: bool = True,
    prefer_front_api_only: bool = False,
) -> dict:
    if not article_no:
        return {}

    from src.core.services.site_contract import HOST_FIN, HOST_M, is_fin_html_dead_url

    best_source = ""
    best_artifacts: dict = {}
    best_fields: dict = {}
    best_meta: dict = {}
    best_body_text = ""
    best_score = -1
    use_front_api = bool(front_api_enabled)
    fin_html_dead = False

    # Skip HTML navigation when callers already know fin is dead / want API-only path.
    if prefer_front_api_only and use_front_api:
        cold_artifacts = await _supplement_front_api_artifacts(
            detail_page,
            article_no,
            {"responses": [], "body_text": "", "html_text": "", "hydration_state": {}},
            navigation_timeout_ms=navigation_timeout_ms,
        )
        cold_fields: dict = {}
        for response_item in list(cold_artifacts.get("responses", []) or []):
            if not isinstance(response_item, dict):
                continue
            payload = response_item.get("payload")
            if isinstance(payload, dict):
                cold_fields = _merge_detail_field_maps(cold_fields, parse_front_api_agent_payload(payload))
        cold_fields = _backfill_fields_from_artifacts(cold_fields, cold_artifacts)
        cold_meta = _build_detail_meta("front_api", "", cold_fields, cold_artifacts)
        if bool(cold_artifacts.get("front_api_rate_limited")):
            cold_meta["front_api_rate_limited"] = True
        cold_meta["detail_host_unreachable"] = True
        cold_meta["prefer_front_api_only"] = True
        cold_fields["_detail_meta"] = cold_meta
        return cold_fields

    # Prefer front-api-only first when HTML is known-dead; try fin once then skip m.* redirects.
    url_candidates: list[tuple[str, str]] = [
        ("fin_article", f"{HOST_FIN}/articles/{article_no}"),
        ("m_info", f"{HOST_M}/article/info/{article_no}"),
    ]
    for source, url in url_candidates:
        if fin_html_dead and source.startswith("m_"):
            # m.land redirects into the same fin 404 chain — skip extra navigations.
            continue
        artifacts = await _collect_detail_artifacts(
            detail_page,
            url,
            navigation_timeout_ms=navigation_timeout_ms,
        )
        candidate_body = str(artifacts.get("body_text", "") or "")
        try:
            final_url = str(getattr(detail_page, "url", "") or url)
        except Exception:
            final_url = url
        if is_fin_html_dead_url(final_url, candidate_body) or _is_not_found_body(candidate_body):
            fin_html_dead = True
            artifacts["detail_host_unreachable"] = True
        # DOM may be 404/map-only; still pull front-api with browser cookies.
        if use_front_api:
            artifacts = await _supplement_front_api_artifacts(
                detail_page,
                article_no,
                artifacts,
                navigation_timeout_ms=navigation_timeout_ms,
            )
        candidate_corpus = str(artifacts.get("corpus_text", "") or "")
        has_network = bool(artifacts.get("responses"))
        if _is_not_found_body(candidate_body) and not candidate_corpus and not has_network:
            if fin_html_dead:
                break
            continue
        merged_artifacts = dict(artifacts)

        if not fin_html_dead:
            try:
                await detail_page.locator("text=실거래가").first.click()
                await detail_page.wait_for_timeout(250)
                await detail_page.locator("text=전세").first.click()
                inline_artifacts = await _collect_inline_artifacts(detail_page)
                merged_artifacts = _merge_detail_artifacts(artifacts, inline_artifacts)
            except Exception:
                pass

        body_text = str(merged_artifacts.get("body_text", "") or candidate_body or "")
        corpus_text = str(merged_artifacts.get("corpus_text", "") or candidate_corpus or "")
        fields = _parse_detail_fields(body_text, fallback_text=corpus_text)
        fields = _backfill_fields_from_artifacts(fields, merged_artifacts)
        # Prefer structured front-api payloads when present.
        for response_item in list(merged_artifacts.get("responses", []) or []):
            if not isinstance(response_item, dict):
                continue
            payload = response_item.get("payload")
            if isinstance(payload, dict):
                fields = _merge_detail_field_maps(fields, parse_front_api_agent_payload(payload))
        meta = _build_detail_meta(source, body_text, fields, merged_artifacts)
        if bool(merged_artifacts.get("front_api_rate_limited")):
            meta["front_api_rate_limited"] = True
        if bool(merged_artifacts.get("detail_host_unreachable")):
            meta["detail_host_unreachable"] = True
        score = _detail_candidate_score(fields, meta)

        if score > best_score:
            best_source = source
            best_artifacts = merged_artifacts
            best_fields = fields
            best_meta = meta
            best_body_text = body_text
            best_score = score

        if _detail_core_field_score(fields) > 0 and str(meta.get("detail_parse_state", "")) in {"partial", "success"}:
            break
        if fin_html_dead:
            break

    # Last resort: front-api only without successful page body (cold request may 429).
    if use_front_api and _detail_core_field_score(best_fields) <= 0:
        cold_artifacts = await _supplement_front_api_artifacts(
            detail_page,
            article_no,
            {"responses": [], "body_text": "", "html_text": "", "hydration_state": {}},
            navigation_timeout_ms=navigation_timeout_ms,
        )
        cold_fields = {}
        for response_item in list(cold_artifacts.get("responses", []) or []):
            if not isinstance(response_item, dict):
                continue
            payload = response_item.get("payload")
            if isinstance(payload, dict):
                cold_fields = _merge_detail_field_maps(cold_fields, parse_front_api_agent_payload(payload))
        cold_fields = _backfill_fields_from_artifacts(cold_fields, cold_artifacts)
        cold_meta = _build_detail_meta("front_api", "", cold_fields, cold_artifacts)
        if bool(cold_artifacts.get("front_api_rate_limited")):
            cold_meta["front_api_rate_limited"] = True
        if fin_html_dead:
            cold_meta["detail_host_unreachable"] = True
        cold_score = _detail_candidate_score(cold_fields, cold_meta)
        if cold_score > best_score:
            best_source = "front_api"
            best_artifacts = cold_artifacts
            best_fields = cold_fields
            best_meta = cold_meta
            best_body_text = ""
            best_score = cold_score

    final_fields = dict(best_fields)
    final_meta = dict(best_meta) if best_meta else _build_detail_meta(best_source, best_body_text, final_fields, best_artifacts)
    if fin_html_dead:
        final_meta["detail_host_unreachable"] = True
    final_fields["_detail_meta"] = final_meta
    return final_fields


def apply_mobile_detail(item: dict, detail: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    if isinstance(detail, dict):
        meta = dict(detail.get("_detail_meta", {}) or {})
        applied = {key: value for key, value in detail.items() if key != "_detail_meta"}
        # Snapshot list-level broker before merge so empty detail cannot erase credit.
        had_list_broker = bool(str(item.get("부동산상호", "") or "").strip())
        # Do not wipe list-level fields (e.g. realtorName → 부동산상호) with empty detail values.
        for key, value in applied.items():
            if isinstance(value, str) and not value.strip():
                existing = item.get(key)
                if existing not in (None, ""):
                    continue
            if value in (0, 0.0) and key in {
                "기전세금(원)",
                "전세_기간(년)",
                "전세_기간내_최고(원)",
                "전세_기간내_최저(원)",
                "갭금액(원)",
                "갭비율",
            }:
                existing_num = item.get(key)
                try:
                    if existing_num not in (None, "", 0, 0.0) and float(existing_num) != 0:
                        continue
                except (TypeError, ValueError):
                    pass
            item[key] = value
        if meta:
            source = str(meta.get("detail_source", "") or "")
            parse_state = str(meta.get("detail_parse_state", "") or "")
            # List already had broker name and detail failed → list-partial (not full failure).
            if parse_state == "failed" and had_list_broker:
                parse_state = "partial"
                source = source or "list_meta"
            missing_count = int(meta.get("missing_field_count", 0) or 0)
            item["detail_source"] = source
            item["detail_parse_state"] = parse_state
            item["missing_field_count"] = missing_count
            item["detail_network_response_count"] = int(meta.get("network_response_count", 0) or 0)
            item["detail_hydration_hit"] = int(meta.get("hydration_hit", 0) or 0)
            if meta.get("detail_host_unreachable"):
                item["detail_host_unreachable"] = True
            item["상세소스"] = source
            item["상세수집상태"] = parse_state
            item["상세누락필드수"] = missing_count
    return enrich_gap_fields(item)
