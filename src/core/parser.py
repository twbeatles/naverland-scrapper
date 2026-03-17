import json
import re
import urllib.request
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError

from src.utils.logger import get_logger
from src.utils.retry_handler import RetryCancelledError, RetryHandler


class NaverURLParser:
    """네이버 부동산 URL에서 단지 정보를 추출한다."""

    PATTERNS = [
        r"new\.land\.naver\.com/complexes/(\d+)",
        r"land\.naver\.com/complex/(\d+)",
        r"complexNo=(\d+)",
        r"complexNo=(\d+).*articleId=\d+",
        r"/api/.*complex[=/](\d+)",
        r"m\.land\.naver\.com.*complex[=/](\d+)",
    ]
    _URL_RE = re.compile(r"https?://[^\s<>\"']+")
    _STANDALONE_ID_LINE_RE = re.compile(r"^\s*(\d+)\s*$")
    _CONTEXT_ID_LINE_RE = re.compile(
        r"(?:단지\s*(?:id|번호)?|complex\s*id|complexno)\s*[:=]?\s*(\d+)",
        re.IGNORECASE,
    )
    _COMPLEX_QUERY_RE = re.compile(r"complexNo=(\d+)", re.IGNORECASE)

    _retry_handler = RetryHandler(max_retries=2, base_delay=1.0)

    @classmethod
    def extract_complex_id(cls, url):
        """URL에서 단지 ID를 추출한다."""
        for pattern in cls.PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

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
    def fetch_complex_name(cls, complex_id, cancel_checker=None):
        """단지 ID로 단지명을 조회한다."""
        try:
            return cls._retry_handler.execute_with_retry(
                cls._fetch_name_impl,
                complex_id,
                cancel_checker=cancel_checker,
            )
        except RetryCancelledError:
            raise
        except Exception as e:
            get_logger("NaverURLParser").debug(f"단지명 조회 실패 ({complex_id}): {e}")
            return f"단지_{complex_id}"
