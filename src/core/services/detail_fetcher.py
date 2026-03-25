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


async def _goto_detail_url(detail_page, url: str):
    await detail_page.goto(url, wait_until="domcontentloaded")
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
    if isinstance(value, str):
        matches = re.findall(r"(0\d{1,2}-\d{3,4}-\d{4})", value)
        return matches[0] if matches else ""
    if isinstance(value, (list, tuple)):
        for item in value:
            phone = _first_phone_from_value(item)
            if phone:
                return phone
    return ""


def _backfill_fields_from_artifacts(fields: dict, artifacts: dict | None) -> dict:
    artifacts = dict(artifacts or {})
    source_tree = {
        "hydration_state": artifacts.get("hydration_state", {}),
        "responses": artifacts.get("responses", []),
    }
    office = _find_named_value(source_tree, {"brokerName", "officeName", "realtorName"})
    if office and not str(fields.get("부동산상호", "") or "").strip():
        fields["부동산상호"] = str(office).strip()

    agent_name = _find_named_value(
        source_tree,
        {"agentName", "brokerRepresentativeName", "representativeName"},
    )
    if agent_name and not str(fields.get("중개사이름", "") or "").strip():
        fields["중개사이름"] = str(agent_name).strip()

    if not str(fields.get("전화1", "") or "").strip():
        phone_value = _find_named_value(source_tree, {"phone", "phones", "telNo", "telephone", "mobileNo"})
        phone = _first_phone_from_value(phone_value)
        if phone:
            fields["전화1"] = phone

    if int(fields.get("기전세금(원)", 0) or 0) <= 0:
        prev_jeonse_value = _find_named_value(
            source_tree,
            {"prevJeonse", "prevJeonsePrice", "previousJeonse"},
        )
        prev_jeonse = parse_kr_money_to_won(str(prev_jeonse_value or ""))
        if prev_jeonse:
            fields["기전세금(원)"] = prev_jeonse

    return fields


async def _collect_detail_artifacts(detail_page, url: str) -> dict:
    responses: list[dict] = []
    pending_tasks: set[asyncio.Task] = set()

    async def _consume(response):
        response_url = str(getattr(response, "url", "") or "")
        if not response_url:
            return
        lower_url = response_url.lower()
        if not any(token in lower_url for token in ("land.naver.com", "/api/", "article", "realtor")):
            return
        try:
            payload = await response.json()
        except Exception:
            return
        responses.append({"url": response_url, "payload": payload})

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
        await _goto_detail_url(detail_page, url)
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
        office = grab(r"brokerName\s+([^\n]+)") or grab(r"officeName\s+([^\n]+)")
    if not agent_name:
        agent_name = grab(r"agentName\s+([^\n]+)") or grab(r"brokerRepresentativeName\s+([^\n]+)")

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


async def fetch_mobile_article_detail(detail_page, article_no: str) -> dict:
    if not article_no:
        return {}

    body_text = ""
    corpus_text = ""
    selected_source = ""
    selected_artifacts: dict = {}
    for source, url in (
        ("fin_article", f"https://fin.land.naver.com/articles/{article_no}"),
        ("m_info", f"https://m.land.naver.com/article/info/{article_no}"),
        ("m_view", f"https://m.land.naver.com/article/view/{article_no}"),
    ):
        artifacts = await _collect_detail_artifacts(detail_page, url)
        candidate_body = str(artifacts.get("body_text", "") or "")
        candidate_corpus = str(artifacts.get("corpus_text", "") or "")
        if _is_not_found_body(candidate_body) and not candidate_corpus:
            continue
        body_text = candidate_body
        corpus_text = candidate_corpus
        selected_source = source
        selected_artifacts = artifacts
        if _is_meaningful_body(candidate_body) or len(candidate_corpus) >= 120:
            break

    try:
        await detail_page.locator("text=실거래가").first.click()
        await detail_page.wait_for_timeout(250)
        await detail_page.locator("text=전세").first.click()
        inline_artifacts = await _collect_inline_artifacts(detail_page)
        refreshed_body = str(inline_artifacts.get("body_text", "") or "")
        refreshed_corpus = str(inline_artifacts.get("corpus_text", "") or "")
        if refreshed_body:
            body_text = refreshed_body
        if refreshed_corpus:
            corpus_text = refreshed_corpus
            selected_artifacts = {
                "body_text": body_text,
                "html_text": inline_artifacts.get("html_text", ""),
                "hydration_state": inline_artifacts.get("hydration_state", {}),
                "responses": list(selected_artifacts.get("responses", []) or []),
                "corpus_text": refreshed_corpus,
            }
    except Exception:
        pass

    fields = _parse_detail_fields(body_text, fallback_text=corpus_text)
    fields = _backfill_fields_from_artifacts(fields, selected_artifacts)
    fields["_detail_meta"] = _build_detail_meta(selected_source, body_text, fields, selected_artifacts)
    return fields


def apply_mobile_detail(item: dict, detail: dict | None) -> dict:
    if not isinstance(item, dict):
        return {}
    if isinstance(detail, dict):
        applied = {key: value for key, value in detail.items() if key != "_detail_meta"}
        item.update(applied)
    return enrich_gap_fields(item)
