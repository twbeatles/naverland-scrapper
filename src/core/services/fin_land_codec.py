"""Decoders for Naver Land map links (live 2026-10-22).

- fin.land ``map?layer=`` is the layer stack JSON compressed with lz-string
  ``compressToEncodedURIComponent``, e.g. ``[{"id":"complex_detail",
  "params":{"complexId":111515},"searchParams":{"tab":"article"}}]``.
- Coordinates are base62 (``0-9a-zA-Z``) of ``round(value * 1e7) + 2e9``:
  fin uses ``center=<lon>-<lat>&zoom=N``; new.land now writes
  ``ms=<lat>,<lon>,<zoom>`` in the same form (plain decimals still accepted).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

_LZ_URI_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$"
_LZ_URI_INDEX = {ch: idx for idx, ch in enumerate(_LZ_URI_ALPHABET)}
_LZ_MAX_OUTPUT = 20000

BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE62_INDEX = {ch: idx for idx, ch in enumerate(BASE62_CHARS)}
_BASE62_RE = re.compile(r"^[0-9a-zA-Z]+$")
_COORD_OFFSET = 2_000_000_000
_COORD_SCALE = 1e7


def lz_decompress_from_uri(encoded: str) -> str | None:
    """Port of lz-string ``decompressFromEncodedURIComponent``.

    Returns ``None`` for malformed input instead of raising.
    """
    if encoded is None:
        return None
    text = str(encoded).replace(" ", "+")
    if not text:
        return ""
    try:
        values = [_LZ_URI_INDEX[ch] for ch in text]
    except KeyError:
        return None
    length = len(values)
    reset_value = 32
    state = {"val": values[0], "pos": reset_value, "index": 1}

    def read_bits(count: int) -> int:
        bits = 0
        power = 1
        maxpower = 1 << count
        while power != maxpower:
            resb = state["val"] & state["pos"]
            state["pos"] >>= 1
            if state["pos"] == 0:
                state["pos"] = reset_value
                idx = state["index"]
                state["val"] = values[idx] if idx < length else 0
                state["index"] = idx + 1
            if resb > 0:
                bits |= power
            power <<= 1
        return bits

    dictionary: dict[int, str] = {0: "", 1: "", 2: ""}
    enlarge_in = 4
    dict_size = 4
    num_bits = 3
    first = read_bits(2)
    if first == 0:
        entry = chr(read_bits(8))
    elif first == 1:
        entry = chr(read_bits(16))
    else:
        return ""
    dictionary[3] = entry
    w = entry
    result = [entry]
    total = len(entry)
    while True:
        if state["index"] > length:
            return None
        code = read_bits(num_bits)
        if code == 0:
            dictionary[dict_size] = chr(read_bits(8))
            code = dict_size
            dict_size += 1
            enlarge_in -= 1
        elif code == 1:
            dictionary[dict_size] = chr(read_bits(16))
            code = dict_size
            dict_size += 1
            enlarge_in -= 1
        elif code == 2:
            return "".join(result)
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1
        if code in dictionary:
            entry = dictionary[code]
        elif code == dict_size:
            entry = w + w[0]
        else:
            return None
        result.append(entry)
        total += len(entry)
        if total > _LZ_MAX_OUTPUT:
            return None
        dictionary[dict_size] = w + entry[0]
        dict_size += 1
        enlarge_in -= 1
        w = entry
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1


def decode_base62_coord(token: str) -> float | None:
    raw = str(token or "").strip()
    if not raw or not _BASE62_RE.match(raw):
        return None
    value = 0
    for ch in raw:
        value = value * 62 + _BASE62_INDEX[ch]
    return (value - _COORD_OFFSET) / _COORD_SCALE


def encode_base62_coord(value: float) -> str:
    number = int(round(float(value) * _COORD_SCALE)) + _COORD_OFFSET
    if number <= 0:
        return "0"
    chars = []
    while number > 0:
        number, rem = divmod(number, 62)
        chars.append(BASE62_CHARS[rem])
    return "".join(reversed(chars))


def _coord_token(token: str) -> float | None:
    """Plain decimal or base62 coordinate."""
    raw = str(token or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return decode_base62_coord(raw)


def decode_layer_stack(layer_param: str) -> list[dict]:
    text = lz_decompress_from_uri(unquote(str(layer_param or "")))
    if not text:
        return []
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [layer for layer in payload if isinstance(layer, dict)]


def _in_korea(lat: float, lon: float) -> bool:
    return 33.0 <= lat <= 39.5 and 124.0 <= lon <= 132.1


def parse_map_center(url_or_text: str) -> tuple[float, float, int] | None:
    """(lat, lon, zoom) from new.land ``ms=`` or fin ``center=``/``zoom=``."""
    raw = str(url_or_text or "")
    match = re.search(r"[?&]ms=([0-9A-Za-z.\-]+),([0-9A-Za-z.\-]+),(\d+(?:\.\d+)?)", raw)
    lat = lon = None
    zoom: float | None = None
    if match:
        lat = _coord_token(match.group(1))
        lon = _coord_token(match.group(2))
        zoom = float(match.group(3))
    else:
        center = re.search(r"[?&]center=([0-9A-Za-z]+)-([0-9A-Za-z]+)", raw)
        if center:
            lon = decode_base62_coord(center.group(1))
            lat = decode_base62_coord(center.group(2))
            zoom_match = re.search(r"[?&]zoom=(\d+(?:\.\d+)?)", raw)
            zoom = float(zoom_match.group(1)) if zoom_match else 15.0
    if lat is None or lon is None or zoom is None:
        return None
    if not _in_korea(lat, lon):
        return None
    return (lat, lon, max(12, min(18, int(zoom))))


def parse_fin_map_link(url: str) -> dict[str, Any]:
    """Extract complex/article IDs from a fin ``map?layer=`` link.

    The top-most matching layer wins (the stack is ordered bottom -> top).
    """
    result: dict[str, Any] = {"complex_id": "", "article_id": "", "asset_type": "", "layers": []}
    try:
        query = parse_qs(urlparse(str(url or "")).query)
    except ValueError:
        return result
    layers = decode_layer_stack((query.get("layer") or [""])[0])
    result["layers"] = layers
    for layer in reversed(layers):
        layer_id = str(layer.get("id", "") or "")
        raw_params = layer.get("params")
        raw_search = layer.get("searchParams")
        params: dict = raw_params if isinstance(raw_params, dict) else {}
        search: dict = raw_search if isinstance(raw_search, dict) else {}
        if layer_id == "article_detail" and not result["article_id"]:
            result["article_id"] = str(params.get("articleId", "") or "").strip()
        if layer_id == "complex_detail" and not result["complex_id"]:
            result["complex_id"] = str(params.get("complexId", "") or "").strip()
            is_villa = str(search.get("isVilla", "") or "").lower() == "true"
            result["asset_type"] = "VL" if is_villa else "APT"
    return result
