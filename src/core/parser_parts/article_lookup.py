import json
import re
import time
import urllib.request
from html import unescape
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError

from src.utils.logger import get_logger
from src.utils.retry_handler import RetryCancelledError

logger = get_logger("Parser")
from src.core.parser_parts.contracts import runtime_contract
from src.core.parser_parts.browser_fallback import ArticleLookupBrowserFallbackSession


class NaverArticleLookupMixin:

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
        runtime_cls = runtime_contract(cls)
        corpus = str(text or "")
        for match in runtime_cls._ARTICLE_TYPE_CODE_RE.finditer(corpus):
            detected = cls._normalize_article_asset_type_token(match.group(1))
            if detected:
                return detected
        for match in runtime_cls._ARTICLE_TYPE_NAME_RE.finditer(corpus):
            name = match.group(1)
            if any(token in name for token in ("빌라", "연립", "다세대", "주택")):
                return "VL"
            if any(token in name for token in ("아파트", "APT")):
                return "APT"
        if re.search(r"new\.land\.naver\.com/houses/\d+", corpus, re.IGNORECASE):
            return "VL"
        if any(token in corpus for token in ("빌라", "연립", "다세대")):
            return "VL"
        return runtime_cls._normalize_asset_type(fallback)

    @classmethod
    def _extract_article_complex_info(cls, body_text: str, fallback_asset_type: str = "APT") -> tuple[str, str]:
        runtime_cls = runtime_contract(cls)
        corpus = unescape(str(body_text or "")).replace("\\/", "/")
        detected_asset = cls._detect_article_asset_type(corpus, fallback=fallback_asset_type)
        for pattern_asset, pattern in runtime_cls._ARTICLE_COMPLEX_PATTERNS:
            match = pattern.search(corpus)
            if match:
                cid = str(match.group(1) or "").strip()
                if cid:
                    asset = detected_asset or pattern_asset or fallback_asset_type
                    if pattern_asset == "VL" and detected_asset == "APT":
                        asset = "VL"
                    return cid, runtime_cls._normalize_asset_type(asset)
        return "", runtime_cls._normalize_asset_type(detected_asset or fallback_asset_type)

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
        runtime_cls = runtime_contract(cls)
        for source, url in cls._article_lookup_urls(aid):
            if runtime_cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("article lookup cancelled before attempt")
            try:
                body = cls._fetch_article_lookup_impl(url)
            except RetryCancelledError:
                raise
            except (HTTPError, URLError, SocketTimeout, TimeoutError, OSError) as e:
                logger.debug(f"매물 단지 역조회 실패 ({source}:{aid}): {e}")
                continue
            if runtime_cls._is_cancelled(cancel_checker):
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
        if runtime_cls._is_cancelled(cancel_checker):
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
