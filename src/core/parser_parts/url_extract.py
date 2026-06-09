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


class NaverURLExtractMixin:

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
        runtime_cls = runtime_contract(cls)
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

        url = runtime_cls._URL_RE.search(raw)
        token = url.group(0) if url else raw
        for entry in runtime_cls._PARSE_PATTERNS:
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
        runtime_cls = runtime_contract(cls)
        raw_text = str(text or "")
        results = []
        seen = set()

        urls = runtime_cls._URL_RE.findall(raw_text)
        for url in urls:
            parsed = cls.parse_url_info(url)
            cid = str(parsed.get("complex_id", "") or "").strip()
            asset_type = runtime_cls._normalize_asset_type(parsed.get("asset_type", "APT"))
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
        runtime_cls = runtime_contract(cls)
        if not line:
            return None
        raw_line = str(line).strip()
        if not raw_line:
            return None

        lower = raw_line.lower()
        if "articleid" in lower and "complexno" not in lower:
            return None

        q_match = runtime_cls._COMPLEX_QUERY_RE.search(raw_line)
        if q_match:
            return q_match.group(1)

        context_match = runtime_cls._CONTEXT_ID_LINE_RE.search(raw_line)
        if context_match:
            return context_match.group(1)

        standalone_match = runtime_cls._STANDALONE_ID_LINE_RE.match(raw_line)
        if standalone_match:
            return standalone_match.group(1)

        return None

    @staticmethod
    def _normalize_asset_type(asset_type) -> str:
        token = str(asset_type or "APT").strip().upper()
        return token if token in {"APT", "VL"} else "APT"
