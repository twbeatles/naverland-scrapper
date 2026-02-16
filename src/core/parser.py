import re
import json
import urllib.request
from urllib.error import URLError, HTTPError
from socket import timeout as SocketTimeout
from src.utils.logger import get_logger
from src.utils.retry_handler import RetryHandler

class NaverURLParser:
    """네이버 부동산 URL에서 단지 정보 추출 (v7.3)"""
    
    # URL 패턴들
    PATTERNS = [
        # new.land URL 형식: /complexes/123456 (사용자가 가장 많이 복사하는 형태)
        r'new\.land\.naver\.com/complexes/(\d+)',
        # 신규 URL 형식: /complex/123456
        r'land\.naver\.com/complex/(\d+)',
        # 구형 URL: complexNo=123456
        r'complexNo=(\d+)',
        # 매물 상세: articleId와 함께
        r'complexNo=(\d+).*articleId=\d+',
        # 단지 정보 API
        r'/api/.*complex[=/](\d+)',
        # 모바일 URL
        r'm\.land\.naver\.com.*complex[=/](\d+)',
    ]
    _URL_RE = re.compile(r'https?://[^\s<>"\']+')
    _ID_RE = re.compile(r'\b(\d{5,10})\b')
    
    # 재시도 핸들러 (클래스 레벨)
    _retry_handler = RetryHandler(max_retries=2, base_delay=1.0)
    
    @classmethod
    def extract_complex_id(cls, url):
        """URL에서 단지 ID 추출"""
        for pattern in cls.PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @classmethod
    def extract_from_text(cls, text):
        """텍스트에서 모든 단지 URL/ID 추출"""
        results = []
        seen = set()
        # URL에서 추출
        urls = cls._URL_RE.findall(text)
        for url in urls:
            cid = cls.extract_complex_id(url)
            if cid and cid not in seen:
                results.append(("URL에서 추출", cid))
                seen.add(cid)
        
        # 단독 숫자 ID (5자리 이상)
        ids = cls._ID_RE.findall(text)
        for cid in ids:
            if cid not in seen:
                results.append(("ID 직접 입력", cid))
                seen.add(cid)
        
        return results
    
    @classmethod
    def _fetch_name_impl(cls, complex_id):
        """단지명 조회 구현 (내부용)"""
        url = f"https://new.land.naver.com/api/complexes/{complex_id}?sameAddressGroup=false"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('complexDetail', {}).get('complexName', f'단지_{complex_id}')
    
    @classmethod
    def fetch_complex_name(cls, complex_id):
        """단지 ID로 단지명 조회 (네이버 API) - 재시도 지원"""
        try:
            return cls._retry_handler.execute_with_retry(cls._fetch_name_impl, complex_id)
        except Exception as e:
            get_logger('NaverURLParser').debug(f"단지명 조회 실패 ({complex_id}): {e}")
            return f'단지_{complex_id}'

