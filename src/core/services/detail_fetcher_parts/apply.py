from __future__ import annotations

from src.core.services.gap_analysis import enrich_gap_fields


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
