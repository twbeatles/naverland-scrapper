from __future__ import annotations

import re


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
