import re
from typing import Any, ClassVar, Protocol, cast


class NaverParserRuntimeContract(Protocol):
    _PARSE_PATTERNS: ClassVar[tuple[dict[str, Any], ...]]
    _URL_RE: ClassVar[re.Pattern[str]]
    _STANDALONE_ID_LINE_RE: ClassVar[re.Pattern[str]]
    _CONTEXT_ID_LINE_RE: ClassVar[re.Pattern[str]]
    _COMPLEX_QUERY_RE: ClassVar[re.Pattern[str]]
    _ARTICLE_COMPLEX_PATTERNS: ClassVar[tuple[tuple[str, re.Pattern[str]], ...]]
    _ARTICLE_TYPE_CODE_RE: ClassVar[re.Pattern[str]]
    _ARTICLE_TYPE_NAME_RE: ClassVar[re.Pattern[str]]
    _name_cache: ClassVar[dict[str, str]]
    _name_lookup_cooldown_until: ClassVar[float]
    _NAME_LOOKUP_COOLDOWN_SECONDS: ClassVar[float]

    @staticmethod
    def _normalize_asset_type(asset_type) -> str: ...

    @staticmethod
    def _is_cancelled(cancel_checker) -> bool: ...


def runtime_contract(cls) -> type[NaverParserRuntimeContract]:
    return cast(type[NaverParserRuntimeContract], cls)
