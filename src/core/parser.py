import re

from src.core.parser_parts.article_lookup import NaverArticleLookupMixin
from src.core.parser_parts.browser_fallback import ArticleLookupBrowserFallbackSession
from src.core.parser_parts.name_lookup import NaverNameLookupMixin
from src.core.parser_parts.url_extract import NaverURLExtractMixin


class NaverURLParser(
    NaverURLExtractMixin,
    NaverArticleLookupMixin,
    NaverNameLookupMixin,
):
    """??? ??? URL?? ?? ??? ????."""

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
        ("VL", re.compile(r'\\?"(?:bildNo|buildingNo|houseNo|houseId)\\?"\s*:\s*\\?"?(\d+)\\?"?', re.IGNORECASE)),
        ("APT", re.compile(r'\\?"(?:complexNo|complexId|complexNumber|hscpNo|hscpId)\\?"\s*:\s*\\?"?(\d+)\\?"?', re.IGNORECASE)),
        ("VL", re.compile(r"(?:bildNo|buildingNo|houseNo|houseId)\s*[=:]\s*['\"]?(\d+)", re.IGNORECASE)),
        ("APT", re.compile(r"(?:complexNo|complexId|complexNumber|hscpNo|hscpId)\s*[=:]\s*['\"]?(\d+)", re.IGNORECASE)),
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
