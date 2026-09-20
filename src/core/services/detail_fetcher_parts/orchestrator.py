from __future__ import annotations

from src.core.services.detail_fetcher_parts.artifacts import (
    _collect_detail_artifacts,
    _collect_inline_artifacts,
)
from src.core.services.detail_fetcher_parts.detail_parse import (
    _build_detail_meta,
    _detail_candidate_score,
    _detail_core_field_score,
    _merge_detail_artifacts,
    _parse_detail_fields,
)
from src.core.services.detail_fetcher_parts.field_merge import (
    _backfill_fields_from_artifacts,
    _merge_detail_field_maps,
)
from src.core.services.detail_fetcher_parts.front_api import (
    _supplement_front_api_artifacts,
    parse_front_api_agent_payload,
)
from src.core.services.detail_fetcher_parts.page_primitives import _is_not_found_body


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
