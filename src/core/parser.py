import json
import re
import time
import urllib.request
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError

from src.utils.logger import get_logger
from src.utils.retry_handler import RetryCancelledError


class NaverURLParser:
    """네이버 부동산 URL에서 단지 정보를 추출한다."""

    PATTERNS = [
        r"new\.land\.naver\.com/complexes/(\d+)",
        r"new\.land\.naver\.com/houses/(\d+)",
        r"land\.naver\.com/complex/(\d+)",
        r"complexNo=(\d+)",
        r"complexNo=(\d+).*articleId=\d+",
        r"/api/.*complex[=/](\d+)",
        r"/api/.*houses?[=/](\d+)",
        r"m\.land\.naver\.com.*complex[=/](\d+)",
        r"m\.land\.naver\.com.*houses?[=/](\d+)",
    ]
    _PARSE_PATTERNS = (
        {
            "pattern": re.compile(r"new\.land\.naver\.com/complexes/(\d+)", re.IGNORECASE),
            "family": "new",
            "entity_type": "complex",
            "asset_type": "APT",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(
                r"new\.land\.naver\.com/houses/(\d+)(?:\?[^\s#]*articleId=(\d+)[^\s#]*)?",
                re.IGNORECASE,
            ),
            "family": "new",
            "entity_type": "complex",
            "asset_type": "VL",
            "complex_group": 1,
            "article_group": 2,
        },
        {
            "pattern": re.compile(r"land\.naver\.com/complex/(\d+)", re.IGNORECASE),
            "family": "legacy",
            "entity_type": "complex",
            "asset_type": "APT",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(r"complexNo=(\d+)(?:.*?articleId=(\d+))?", re.IGNORECASE),
            "family": "legacy",
            "entity_type": "complex",
            "asset_type": "APT",
            "complex_group": 1,
            "article_group": 2,
        },
        {
            "pattern": re.compile(r"/api/.*complex[=/](\d+)", re.IGNORECASE),
            "family": "api",
            "entity_type": "complex",
            "asset_type": "APT",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(r"/api/.*houses?[=/](\d+)", re.IGNORECASE),
            "family": "api",
            "entity_type": "complex",
            "asset_type": "VL",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(r"m\.land\.naver\.com/article/(?:info|view)/(\d+)", re.IGNORECASE),
            "family": "m",
            "entity_type": "article",
            "article_group": 1,
        },
        {
            "pattern": re.compile(r"m\.land\.naver\.com.*complex[=/](\d+)", re.IGNORECASE),
            "family": "m",
            "entity_type": "complex",
            "asset_type": "APT",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(r"m\.land\.naver\.com.*houses?[=/](\d+)", re.IGNORECASE),
            "family": "m",
            "entity_type": "complex",
            "asset_type": "VL",
            "complex_group": 1,
        },
        {
            "pattern": re.compile(r"fin\.land\.naver\.com/articles/(\d+)", re.IGNORECASE),
            "family": "fin",
            "entity_type": "article",
            "article_group": 1,
        },
    )
    _URL_RE = re.compile(r"https?://[^\s<>\"']+")
    _STANDALONE_ID_LINE_RE = re.compile(r"^\s*(\d+)\s*$")
    _CONTEXT_ID_LINE_RE = re.compile(
        r"(?:단지\s*(?:id|번호)?|complex\s*id|complexno)\s*[:=]?\s*(\d+)",
        re.IGNORECASE,
    )
    _COMPLEX_QUERY_RE = re.compile(r"complexNo=(\d+)", re.IGNORECASE)

    _name_cache: dict[str, str] = {}
    _name_lookup_cooldown_until: float = 0.0
    _NAME_LOOKUP_COOLDOWN_SECONDS = 300.0

    @classmethod
    def extract_complex_id(cls, url):
        """URL에서 단지 ID를 추출한다."""
        parsed = cls.parse_url_info(url)
        complex_id = str(parsed.get("complex_id", "") or "").strip()
        return complex_id or None

    @classmethod
    def extract_article_id(cls, url):
        """URL에서 매물 ID를 추출한다."""
        parsed = cls.parse_url_info(url)
        article_id = str(parsed.get("article_id", "") or "").strip()
        return article_id or None

    @classmethod
    def parse_url_info(cls, url_or_text):
        """URL 문자열을 구조화해 반환한다."""
        raw = str(url_or_text or "").strip()
        if not raw:
            return {
                "url": "",
                "family": "",
                "entity_type": "",
                "asset_type": "",
                "complex_id": "",
                "article_id": "",
            }

        url = cls._URL_RE.search(raw)
        token = url.group(0) if url else raw
        for entry in cls._PARSE_PATTERNS:
            match = entry["pattern"].search(token)
            if not match:
                continue
            complex_group = entry.get("complex_group")
            article_group = entry.get("article_group")
            complex_id = match.group(complex_group) if complex_group else ""
            article_id = match.group(article_group) if article_group and match.lastindex and match.lastindex >= article_group else ""
            if not article_id:
                article_match = re.search(r"articleId=(\d+)", token, re.IGNORECASE)
                if article_match:
                    article_id = article_match.group(1)
            entity_type = str(entry.get("entity_type", "") or "")
            if article_id and entity_type != "article":
                entity_type = "article"
            return {
                "url": token,
                "family": str(entry.get("family", "") or ""),
                "entity_type": entity_type,
                "asset_type": str(entry.get("asset_type", "") or ""),
                "complex_id": str(complex_id or ""),
                "article_id": str(article_id or ""),
            }

        return {
            "url": token,
            "family": "",
            "entity_type": "",
            "asset_type": "",
            "complex_id": "",
            "article_id": "",
        }

    @classmethod
    def extract_from_text(cls, text):
        """텍스트에서 모든 단지 URL/ID를 추출한다."""
        results = []
        seen = set()

        urls = cls._URL_RE.findall(text)
        for url in urls:
            cid = cls.extract_complex_id(url)
            if cid and cid not in seen:
                results.append(("URL에서 추출", cid))
                seen.add(cid)

        for line in text.splitlines():
            cid = cls._extract_id_from_line(line)
            if cid and cid not in seen:
                results.append(("ID 직접 입력", cid))
                seen.add(cid)

        return results

    @classmethod
    def _extract_id_from_line(cls, line):
        if not line:
            return None
        raw_line = str(line).strip()
        if not raw_line:
            return None

        lower = raw_line.lower()
        if "articleid" in lower and "complexno" not in lower:
            return None

        q_match = cls._COMPLEX_QUERY_RE.search(raw_line)
        if q_match:
            return q_match.group(1)

        context_match = cls._CONTEXT_ID_LINE_RE.search(raw_line)
        if context_match:
            return context_match.group(1)

        standalone_match = cls._STANDALONE_ID_LINE_RE.match(raw_line)
        if standalone_match:
            return standalone_match.group(1)

        return None

    @classmethod
    def _fetch_name_impl(cls, complex_id):
        """네이버 API를 호출해 단지명을 조회한다."""
        url = f"https://new.land.naver.com/api/complexes/{complex_id}?sameAddressGroup=false"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("complexDetail", {}).get("complexName", f"단지_{complex_id}")

    @classmethod
    def _fallback_name(cls, complex_id):
        return f"단지_{complex_id}"

    @staticmethod
    def _is_cancelled(cancel_checker) -> bool:
        if not callable(cancel_checker):
            return False
        try:
            return bool(cancel_checker())
        except Exception:
            return False

    @classmethod
    def _activate_name_lookup_cooldown(cls):
        cls._name_lookup_cooldown_until = max(
            float(cls._name_lookup_cooldown_until or 0.0),
            time.monotonic() + float(cls._NAME_LOOKUP_COOLDOWN_SECONDS),
        )

    @classmethod
    def _consume_http_error_body(cls, error: HTTPError) -> str:
        try:
            return error.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    @classmethod
    def _reset_runtime_state_for_tests(cls):
        cls._name_cache.clear()
        cls._name_lookup_cooldown_until = 0.0

    @classmethod
    def fetch_complex_name(cls, complex_id, cancel_checker=None):
        """단지 ID로 단지명을 조회한다."""
        cid = str(complex_id or "").strip()
        fallback_name = cls._fallback_name(cid)
        if not cid:
            return fallback_name
        if cls._is_cancelled(cancel_checker):
            raise RetryCancelledError("lookup cancelled before attempt")

        cached = cls._name_cache.get(cid, "")
        if cached:
            return cached

        if time.monotonic() < float(cls._name_lookup_cooldown_until or 0.0):
            return fallback_name

        logger = get_logger("NaverURLParser")
        try:
            name = str(cls._fetch_name_impl(cid) or "").strip() or fallback_name
            if name and not name.startswith("단지_"):
                cls._name_cache[cid] = name
            return name
        except RetryCancelledError:
            raise
        except Exception as e:
            if cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("lookup cancelled after exception") from e
            if isinstance(e, HTTPError):
                response_body = cls._consume_http_error_body(e)
                status = int(getattr(e, "code", 0) or 0)
                if status == 429 or "TOO_MANY_REQUESTS" in response_body:
                    cls._activate_name_lookup_cooldown()
                    logger.warning(f"단지명 조회 rate limit ({cid}): status={status}")
                else:
                    logger.debug(f"단지명 조회 HTTP 실패 ({cid}): status={status}, body={response_body[:160]}")
            else:
                logger.debug(f"단지명 조회 실패 ({cid}): {e}")
            return fallback_name
