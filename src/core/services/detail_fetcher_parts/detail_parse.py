from __future__ import annotations

import re
from src.core.services.detail_fetcher_parts.money import parse_kr_money_to_won


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
