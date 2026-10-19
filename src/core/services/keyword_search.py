"""Keyword search against Naver Land (``/api/autocomplete`` + ``/api/search``).

Live contract verified 2026-10 with a real browser session:

- ``GET /api/autocomplete?keyword=...`` -> JSON array of display strings with
  ``<strong class='text_input'>`` highlight markup (no IDs).
- ``GET /api/search?keyword=...&page=N`` -> ``{"complexes": [...], "regions":
  [...], "isShown": bool, "isMoreData": bool, ...}``. ``complexes``/``regions``
  keys may be absent when nothing matches.
- Direct (cookie-less) HTTP is rate-limited (429); these endpoints must be
  called from a browser session, see :class:`KeywordBrowserSession`.
"""

from __future__ import annotations

import html as _html
import json
import re
from collections.abc import Callable
from typing import Any

from src.core.services.site_contract import (
    build_autocomplete_url,
    build_search_url,
)

_HIGHLIGHT_RE = re.compile(r"<[^>]+>")
_SEARCH_PAGE_DELAY_SEC = 1.2


def strip_autocomplete_highlight(text: str) -> str:
    """Remove ``<strong class='text_input'>`` markup from a suggestion."""
    cleaned = _HIGHLIGHT_RE.sub("", str(text or ""))
    return _html.unescape(cleaned).strip()


def parse_autocomplete_payload(payload: Any) -> list[str]:
    """Parse ``/api/autocomplete`` body into plain suggestion strings."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return []
    if not isinstance(payload, list):
        return []
    suggestions = []
    for item in payload:
        text = strip_autocomplete_highlight(item)
        if text and text not in suggestions:
            suggestions.append(text)
    return suggestions


def _complex_asset_type(item: dict) -> str:
    deep_link = str(item.get("deepLink", "") or "")
    if "/houses/" in deep_link:
        return "VL"
    code = str(item.get("realEstateTypeCode", "") or "").strip().upper()
    if code == "VL":
        return "VL"
    return "APT"


def parse_search_complexes(payload: Any) -> list[dict]:
    """Parse ``/api/search`` body into normalized complex candidates."""
    if not isinstance(payload, dict):
        return []
    results = []
    for key in ("complexes", "houses"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("complexNo", item.get("houseNo", "")) or "").strip()
            if not cid:
                continue
            results.append(
                {
                    "complex_id": cid,
                    "name": str(item.get("complexName", item.get("houseName", "")) or "").strip(),
                    "address": str(item.get("cortarAddress", "") or "").strip(),
                    "asset_type": _complex_asset_type(item),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "deep_link": str(item.get("deepLink", "") or ""),
                }
            )
    return results


def parse_search_regions(payload: Any) -> list[dict]:
    """Parse ``/api/search`` body into normalized region candidates."""
    if not isinstance(payload, dict):
        return []
    regions = payload.get("regions")
    if not isinstance(regions, list):
        return []
    results = []
    for item in regions:
        if not isinstance(item, dict):
            continue
        cortar_no = str(item.get("cortarNo", "") or "").strip()
        if not cortar_no:
            continue
        raw_lat = item.get("centerLat")
        raw_lon = item.get("centerLon")
        try:
            lat = float(raw_lat) if raw_lat is not None else None
            lon = float(raw_lon) if raw_lon is not None else None
        except (TypeError, ValueError):
            lat, lon = None, None
        results.append(
            {
                "cortar_no": cortar_no,
                "name": str(item.get("cortarName", "") or "").strip(),
                "latitude": lat,
                "longitude": lon,
                "deep_link": str(item.get("deepLink", "") or ""),
            }
        )
    return results


def parse_search_has_more(payload: Any) -> bool:
    return bool(isinstance(payload, dict) and payload.get("isMoreData"))


PageFetch = Callable[[str], tuple[int, str]]
"""Fetch callable: full URL -> (status_code, body_text)."""

_ADDRESS_VARIANT_CAP = 4
_REGION_TAIL_SUFFIXES = ("동", "읍", "면", "리", "구", "군", "시", "도", "로", "길")
_TRAILING_BUNJI_RE = re.compile(r"^(.*\S)\s+\d+(?:-\d+)?(?:번지)?$")
_URL_LIKE_RE = re.compile(r"https?://|land\.naver\.com|fin\.land", re.IGNORECASE)


def _is_region_tail(text: str) -> bool:
    """True when a query tail looks like a legal-dong / district name."""
    token = str(text or "").strip()
    if len(token) < 2 or any(ch.isdigit() for ch in token):
        return False
    return token.endswith(_REGION_TAIL_SUFFIXES)


def address_query_variants(keyword: str, *, max_variants: int = _ADDRESS_VARIANT_CAP) -> list[str]:
    """Build fallback queries so a full real address still resolves.

    ``/api/search`` matches short names (``반포동``, ``분당구``) reliably but
    often returns nothing for a full address (``서울특별시 서초구 반포동``,
    ``경기도 성남시 분당구 정자동 123``). Variants are tried in order, most
    specific first; callers stop at the first variant with any result.
    URLs are returned untouched (map links are resolved elsewhere).
    """
    raw = re.sub(r"\s+", " ", str(keyword or "").strip())
    if not raw:
        return []
    if _URL_LIKE_RE.search(raw):
        return [raw]
    variants = [raw]
    stripped = _TRAILING_BUNJI_RE.sub(r"\1", raw).strip()
    if stripped and stripped != raw and len(stripped) >= 2:
        variants.append(stripped)
    for base in list(variants):
        tokens = base.split(" ")
        for tail_len in (2, 1):
            if len(tokens) > tail_len:
                tail = " ".join(tokens[-tail_len:])
                if _is_region_tail(tail) and tail not in variants:
                    variants.append(tail)
    cap = max(1, int(max_variants or 1))
    return variants[:cap]


class KeywordSearchError(Exception):
    """Transport-level keyword search failure (rate limit, HTTP error)."""

    def __init__(self, keyword: str, status: int | None, detail: str = ""):
        self.keyword = str(keyword or "")
        self.status = status
        message = f"keyword search failed ({self.keyword}, status={status})"
        if detail:
            message += f": {detail}"
        super().__init__(message)


def is_rate_limit_error(exc: BaseException) -> bool:
    """Detect rate-limit failures worth a cooldown (HTTP 429 et al.)."""
    status = getattr(exc, "status", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def fetch_suggestions(keyword: str, page_fetch: PageFetch) -> list[str]:
    """Fetch autocomplete suggestions (empty keyword -> []; errors raise)."""
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    status, body = page_fetch(build_autocomplete_url(keyword))
    if status != 200:
        raise KeywordSearchError(keyword, status)
    return parse_autocomplete_payload(body)


def fetch_search_page(keyword: str, page_fetch: PageFetch, *, page: int = 1) -> dict:
    """Fetch one ``/api/search`` page (transport errors raise)."""
    keyword = str(keyword or "").strip()
    if not keyword:
        return {"complexes": [], "regions": [], "is_more_data": False}
    status, body = page_fetch(build_search_url(keyword, page=page))
    if status != 200:
        raise KeywordSearchError(keyword, status)
    try:
        payload = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise KeywordSearchError(keyword, status, "invalid response") from exc
    return {
        "complexes": parse_search_complexes(payload),
        "regions": parse_search_regions(payload),
        "is_more_data": parse_search_has_more(payload),
    }


def _is_empty_search_result(result: dict) -> bool:
    return not (result.get("complexes") or result.get("regions"))


def fetch_search_page_with_fallback(
    keyword: str,
    page_fetch: PageFetch,
    *,
    page: int = 1,
    max_variants: int = _ADDRESS_VARIANT_CAP,
) -> dict:
    """Fetch one ``/api/search`` page, falling back through address variants.

    The raw keyword is tried first; when it yields no complexes and no
    regions, shorter variants from :func:`address_query_variants` are tried
    until one hits (or the list is exhausted). Transport errors raise
    immediately (rate limits must not burn through variants). The winning
    query is reported as ``effective_query`` so follow-up pages keep it.
    """
    variants = address_query_variants(keyword, max_variants=max_variants) or [str(keyword or "").strip()]
    last_error: KeywordSearchError | None = None
    empty: dict = {"complexes": [], "regions": [], "is_more_data": False}
    for variant in variants:
        try:
            result = fetch_search_page(variant, page_fetch, page=page)
        except KeywordSearchError as exc:
            last_error = exc
            if is_rate_limit_error(exc):
                raise
            continue
        if _is_empty_search_result(result):
            empty = result
            continue
        result["effective_query"] = variant
        return result
    if last_error is not None:
        raise last_error
    empty["effective_query"] = variants[0]
    return empty


class KeywordBrowserSession:
    """Short-lived browser session for keyword endpoints (rate-limit safe).

    The autocomplete/search APIs answer 429 to cookie-less HTTP but 200 from a
    real browser session (verified live). Usage::

        with KeywordBrowserSession() as session:
            names = fetch_suggestions("래미안", session.fetch)
            page1 = fetch_search_page("래미안", session.fetch, page=1)
    """

    def __init__(self, *, executable_path: str | None = None):
        self._executable_path = executable_path
        self._playwright = None
        self._browser = None
        self._page = None

    def __enter__(self) -> KeywordBrowserSession:
        from playwright.sync_api import sync_playwright

        from src.utils.helpers import ChromeParamHelper

        executable_path = self._executable_path or ChromeParamHelper.get_chrome_executable_path()
        self._playwright = sync_playwright().start()
        if executable_path:
            self._browser = self._playwright.chromium.launch(
                executable_path=executable_path, headless=True
            )
        else:
            self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page(
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
        )
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        self._page.goto("https://new.land.naver.com/", wait_until="domcontentloaded", timeout=25000)
        try:
            self._page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        finally:
            try:
                if self._playwright is not None:
                    self._playwright.stop()
            finally:
                self._browser = None
                self._page = None
                self._playwright = None

    def fetch(self, url: str) -> tuple[int, str]:
        """GET a same-site URL inside the session; returns (status, text)."""
        if self._page is None:
            raise RuntimeError("KeywordBrowserSession is not open")
        result = self._page.evaluate(
            """(url) => {
                return fetch(url, {headers: {accept: 'application/json'}})
                    .then(async (r) => ({status: r.status, body: await r.text()}))
                    .catch((e) => ({status: 0, body: ''}));
            }""",
            url,
        )
        try:
            status = int(result.get("status", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        return status, str(result.get("body", "") or "")
