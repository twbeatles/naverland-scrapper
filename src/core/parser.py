import json
import re
import time
import urllib.request
from html import unescape
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
    _ARTICLE_COMPLEX_PATTERNS = (
        ("VL", re.compile(r'"(?:bildNo|buildingNo|houseNo|houseId)"\s*:\s*"?(\d+)"?', re.IGNORECASE)),
        ("APT", re.compile(r'"(?:complexNo|complexId|hscpNo|hscpId)"\s*:\s*"?(\d+)"?', re.IGNORECASE)),
        ("VL", re.compile(r"(?:bildNo|buildingNo|houseNo|houseId)\s*[=:]\s*['\"]?(\d+)", re.IGNORECASE)),
        ("APT", re.compile(r"(?:complexNo|complexId|hscpNo|hscpId)\s*[=:]\s*['\"]?(\d+)", re.IGNORECASE)),
        ("VL", re.compile(r"new\.land\.naver\.com/houses/(\d+)", re.IGNORECASE)),
        ("APT", re.compile(r"new\.land\.naver\.com/complexes/(\d+)", re.IGNORECASE)),
    )
    _ARTICLE_TYPE_CODE_RE = re.compile(
        r'"(?:realEstateTypeCode|rletTpCd|estateType|realEstateType)"\s*:\s*"([^"]+)"',
        re.IGNORECASE,
    )
    _ARTICLE_TYPE_NAME_RE = re.compile(
        r'"(?:realEstateTypeName|rletTpNm|estateTypeName)"\s*:\s*"([^"]+)"',
        re.IGNORECASE,
    )

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
        raw_text = str(text or "")
        results = []
        seen = set()

        urls = cls._URL_RE.findall(raw_text)
        for url in urls:
            parsed = cls.parse_url_info(url)
            cid = str(parsed.get("complex_id", "") or "").strip()
            asset_type = cls._normalize_asset_type(parsed.get("asset_type", "APT"))
            dedupe_key = (asset_type, cid)
            if cid and dedupe_key not in seen:
                results.append(
                    {
                        "source": "URL에서 추출",
                        "complex_id": cid,
                        "asset_type": asset_type,
                        "article_id": str(parsed.get("article_id", "") or ""),
                        "url": str(parsed.get("url", url) or url),
                    }
                )
                seen.add(dedupe_key)
            elif not cid:
                article_id = str(parsed.get("article_id", "") or "").strip()
                if article_id and str(parsed.get("entity_type", "") or "") == "article":
                    article_key = ("ARTICLE", article_id)
                    if article_key not in seen:
                        results.append(
                            {
                                "source": "매물 URL에서 추출",
                                "complex_id": "",
                                "asset_type": asset_type,
                                "article_id": article_id,
                                "url": str(parsed.get("url", url) or url),
                                "needs_article_lookup": True,
                            }
                        )
                        seen.add(article_key)

        for line in raw_text.splitlines():
            cid = cls._extract_id_from_line(line)
            dedupe_key = ("APT", str(cid or "").strip())
            if cid and dedupe_key not in seen:
                results.append(
                    {
                        "source": "ID 직접 입력",
                        "complex_id": str(cid),
                        "asset_type": "APT",
                        "article_id": "",
                        "url": "",
                    }
                )
                seen.add(dedupe_key)

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

    @staticmethod
    def _normalize_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token if token in {"APT", "VL"} else "APT"

    @classmethod
    def _name_cache_key(cls, complex_id, asset_type="APT") -> str:
        return f"{cls._normalize_asset_type(asset_type)}:{str(complex_id or '').strip()}"

    @classmethod
    def _article_lookup_urls(cls, article_id) -> tuple[tuple[str, str], ...]:
        aid = str(article_id or "").strip()
        if not aid:
            return ()
        return (
            ("fin_article", f"https://fin.land.naver.com/articles/{aid}"),
            ("m_info", f"https://m.land.naver.com/article/info/{aid}"),
            ("m_view", f"https://m.land.naver.com/article/view/{aid}"),
        )

    @classmethod
    def _fetch_article_lookup_impl(cls, url: str) -> str:
        req = urllib.request.Request(str(url or ""))
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        req.add_header("Accept", "text/html,application/json;q=0.9,*/*;q=0.8")
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8", errors="ignore")

    @classmethod
    def _normalize_article_asset_type_token(cls, token: str) -> str:
        value = str(token or "").strip().upper()
        if value in {"APT", "ABYG", "JGC"}:
            return "APT"
        if value in {"VL", "DDDGG", "JWJT", "SGJT", "HOJT", "JT", "OR"}:
            return "VL"
        return ""

    @classmethod
    def _detect_article_asset_type(cls, text: str, fallback: str = "APT") -> str:
        corpus = str(text or "")
        for match in cls._ARTICLE_TYPE_CODE_RE.finditer(corpus):
            detected = cls._normalize_article_asset_type_token(match.group(1))
            if detected:
                return detected
        for match in cls._ARTICLE_TYPE_NAME_RE.finditer(corpus):
            name = match.group(1)
            if any(token in name for token in ("빌라", "연립", "다세대", "주택")):
                return "VL"
            if any(token in name for token in ("아파트", "APT")):
                return "APT"
        if re.search(r"new\.land\.naver\.com/houses/\d+", corpus, re.IGNORECASE):
            return "VL"
        if any(token in corpus for token in ("빌라", "연립", "다세대")):
            return "VL"
        return cls._normalize_asset_type(fallback)

    @classmethod
    def _extract_article_complex_info(cls, body_text: str, fallback_asset_type: str = "APT") -> tuple[str, str]:
        corpus = unescape(str(body_text or "")).replace("\\/", "/")
        detected_asset = cls._detect_article_asset_type(corpus, fallback=fallback_asset_type)
        for pattern_asset, pattern in cls._ARTICLE_COMPLEX_PATTERNS:
            match = pattern.search(corpus)
            if match:
                cid = str(match.group(1) or "").strip()
                if cid:
                    asset = detected_asset or pattern_asset or fallback_asset_type
                    if pattern_asset == "VL" and detected_asset == "APT":
                        asset = "VL"
                    return cid, cls._normalize_asset_type(asset)
        return "", cls._normalize_asset_type(detected_asset or fallback_asset_type)

    @classmethod
    def resolve_article_complex(
        cls,
        article_id,
        *,
        cancel_checker=None,
        fallback_asset_type="APT",
        browser_fallback=None,
    ) -> dict:
        """Resolve an article-only URL/id to a complex id and asset type."""
        aid = str(article_id or "").strip()
        if not aid:
            return {}
        logger = get_logger("NaverURLParser")
        for source, url in cls._article_lookup_urls(aid):
            if cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("article lookup cancelled before attempt")
            try:
                body = cls._fetch_article_lookup_impl(url)
            except RetryCancelledError:
                raise
            except (HTTPError, URLError, SocketTimeout, TimeoutError, OSError) as e:
                logger.debug(f"매물 단지 역조회 실패 ({source}:{aid}): {e}")
                continue
            if cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("article lookup cancelled after response")
            cid, asset_type = cls._extract_article_complex_info(body, fallback_asset_type=fallback_asset_type)
            if cid:
                return {
                    "source": source,
                    "complex_id": cid,
                    "asset_type": asset_type,
                    "article_id": aid,
                    "url": url,
                }
        if cls._is_cancelled(cancel_checker):
            raise RetryCancelledError("article lookup cancelled before browser fallback")
        if browser_fallback is not None:
            try:
                if hasattr(browser_fallback, "resolve"):
                    fallback = browser_fallback.resolve(
                        aid,
                        cancel_checker=cancel_checker,
                        fallback_asset_type=fallback_asset_type,
                    )
                elif callable(browser_fallback):
                    fallback = browser_fallback(
                        aid,
                        cancel_checker=cancel_checker,
                        fallback_asset_type=fallback_asset_type,
                    )
                else:
                    fallback = {}
            except RetryCancelledError:
                raise
            except Exception as e:
                logger.debug(f"매물 단지 injected browser fallback 실패 ({aid}): {e}")
                fallback = {}
        else:
            fallback = cls._resolve_article_complex_browser_fallback(
                aid,
                cancel_checker=cancel_checker,
                fallback_asset_type=fallback_asset_type,
            )
        if isinstance(fallback, dict) and fallback:
            return fallback
        return {}

    @classmethod
    def create_article_browser_fallback(cls):
        return ArticleLookupBrowserFallbackSession(cls)

    @classmethod
    def _resolve_article_complex_browser_fallback(
        cls,
        article_id,
        *,
        cancel_checker=None,
        fallback_asset_type="APT",
    ) -> dict:
        session = cls.create_article_browser_fallback()
        try:
            return session.resolve(
                article_id,
                cancel_checker=cancel_checker,
                fallback_asset_type=fallback_asset_type,
            )
        except RetryCancelledError:
            raise
        except Exception as e:
            get_logger("NaverURLParser").debug(f"매물 단지 browser fallback 전체 실패 ({article_id}): {e}")
            return {}
        finally:
            session.close()

    @classmethod
    def _fetch_name_impl(cls, complex_id, asset_type="APT"):
        """네이버 API를 호출해 단지명을 조회한다."""
        asset_token = cls._normalize_asset_type(asset_type)
        entity_path = "houses" if asset_token == "VL" else "complexes"
        url = f"https://new.land.naver.com/api/{entity_path}/{complex_id}?sameAddressGroup=false"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            detail = data.get("complexDetail", {}) if isinstance(data, dict) else {}
            name_candidates = (
                detail.get("complexName"),
                detail.get("name"),
                data.get("complexName") if isinstance(data, dict) else "",
                data.get("name") if isinstance(data, dict) else "",
            )
            for candidate in name_candidates:
                token = str(candidate or "").strip()
                if token:
                    return token
            return f"단지_{complex_id}"

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
    def fetch_complex_name(cls, complex_id, asset_type="APT", cancel_checker=None):
        """단지 ID로 단지명을 조회한다."""
        cid = str(complex_id or "").strip()
        asset_token = cls._normalize_asset_type(asset_type)
        fallback_name = cls._fallback_name(cid)
        if not cid:
            return fallback_name
        if cls._is_cancelled(cancel_checker):
            raise RetryCancelledError("lookup cancelled before attempt")

        cache_key = cls._name_cache_key(cid, asset_token)
        cached = cls._name_cache.get(cache_key, "")
        if cached:
            return cached

        if time.monotonic() < float(cls._name_lookup_cooldown_until or 0.0):
            return fallback_name

        logger = get_logger("NaverURLParser")
        try:
            name = str(cls._fetch_name_impl(cid, asset_type=asset_token) or "").strip() or fallback_name
            if name and not name.startswith("단지_"):
                cls._name_cache[cache_key] = name
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
                    logger.warning(f"단지명 조회 rate limit ({asset_token}:{cid}): status={status}")
                else:
                    logger.debug(
                        f"단지명 조회 HTTP 실패 ({asset_token}:{cid}): status={status}, body={response_body[:160]}"
                    )
            else:
                logger.debug(f"단지명 조회 실패 ({asset_token}:{cid}): {e}")
            return fallback_name


class ArticleLookupBrowserFallbackSession:
    """Reusable Playwright browser fallback for article-only URL resolution."""

    def __init__(self, parser_cls=NaverURLParser):
        self._parser_cls = parser_cls
        self._playwright = None
        self._browser = None
        self._page = None
        self._logger = get_logger("NaverURLParser")

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self._logger.debug(f"매물 단지 browser fallback 사용 불가: {e}")
            return None
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        return self._page

    def resolve(self, article_id, *, cancel_checker=None, fallback_asset_type="APT"):
        aid = str(article_id or "").strip()
        if not aid:
            return {}
        page = self._ensure_page()
        if page is None:
            return {}
        for source, url in self._parser_cls._article_lookup_urls(aid):
            if self._parser_cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("article lookup cancelled during browser fallback")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=8000)
                try:
                    page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    pass
                body = ""
                try:
                    body = page.inner_text("body", timeout=1000)
                except Exception:
                    pass
                try:
                    content = page.content()
                except Exception:
                    content = ""
                cid, asset_type = self._parser_cls._extract_article_complex_info(
                    f"{body}\n{content}",
                    fallback_asset_type=fallback_asset_type,
                )
                if cid:
                    return {
                        "source": f"{source}:browser_fallback",
                        "complex_id": cid,
                        "asset_type": asset_type,
                        "article_id": aid,
                        "url": url,
                    }
            except RetryCancelledError:
                raise
            except Exception as e:
                self._logger.debug(f"매물 단지 browser fallback 실패 ({source}:{aid}): {e}")
                continue
        return {}

    def close(self):
        try:
            if self._page is not None:
                self._page.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._playwright = None
