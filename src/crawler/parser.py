import re
from typing import Dict, Any, List, Optional
try:
    from bs4 import BeautifulSoup, Tag
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from src.utils.converters import PriceConverter, AreaConverter
from src.utils.helpers import DateTimeHelper
from src.utils.logger import get_logger

class NaverURLParser:
    """네이버 부동산 URL에서 단지 정보 추출 (v13.1)"""
    
    PATTERNS = [
        # 신규 URL 형식: /complex/123456
        r'land\.naver\.com/complex/(\d+)',
        # 구형/모바일 URL: complexNo=123456
        r'complexNo=(\d+)',
    ]
    
    @classmethod
    def extract_complex_id(cls, url: str) -> Optional[str]:
        """URL에서 단지 ID 추출"""
        for pattern in cls.PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
        
    @classmethod
    def extract_from_text(cls, text: str) -> List[str]:
        """텍스트에서 모든 단지 URL/ID 추출"""
        ids = set()
        # 1. URL 패턴 검색
        for pattern in cls.PATTERNS:
            matches = re.findall(pattern, text)
            ids.update(matches)
            
        # 2. 순수 숫자 ID 검색 (6자리 이상)
        # 주의: 전화번호 등과 혼동될 수 있으므로 URL이 없는 경우에만 보완적으로 사용하거나
        # 명확한 컨텍스트가 있을 때 사용해야 함. 여기서는 보수적으로 URL 패턴만 사용.
        
        return list(ids)

class PageParser:
    """페이지 파싱 로직 분리"""
    
    @staticmethod
    def parse_item(item: Any, name: str, cid: str, ttype: str) -> Optional[Dict[str, Any]]:
        """매물 항목 파싱"""
        if not BS4_AVAILABLE: return None
        if not isinstance(item, Tag): return None
        
        full_text = item.get_text(separator=" ", strip=True)
        detected_type = ttype
        
        # 1. 거래유형 감지
        for sel in [".type", ".trade_type", "[class*='type']", ".item_type", ".article_type"]:
            elem = item.select_one(sel)
            if elem:
                type_text = elem.get_text(strip=True)
                if "매매" in type_text: detected_type = "매매"
                elif "전세" in type_text: detected_type = "전세"
                elif "월세" in type_text: detected_type = "월세"
                break
        
        # 2. 가격 추출
        price_text = ""
        for sel in [".item_price strong", ".price_line", ".article_price", "[class*='price']", ".selling_price", ".trade_price", "strong[class*='Price']", ".price"]:
            elem = item.select_one(sel)
            if elem:
                price_text = elem.get_text(strip=True)
                if price_text and ("억" in price_text or "만" in price_text or price_text.replace(",", "").replace("/", "").isdigit()):
                    break
        
        if not price_text:
            price_match = re.search(r'(\d+억\s*\d*,?\d*만?|\d+,?\d*만)', full_text)
            if price_match: price_text = price_match.group(1)
        
        # 거래유형 보정
        if re.search(r'\d+[억만]?\s*/\s*\d+', price_text): detected_type = "월세"
        elif "전세" in full_text[:50]: detected_type = "전세"
        elif "매매" in full_text[:50]: detected_type = "매매"
        
        # 3. 면적 추출
        area_text, sqm, pyeong = "", 0, 0
        for sel in [".item_area", ".info_area", ".article_area", "[class*='area']"]:
            elem = item.select_one(sel)
            if elem: area_text = elem.get_text(strip=True); break
        if not area_text: area_text = full_text
        
        sqm_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)', area_text)
        if sqm_match:
            sqm = float(sqm_match.group(1))
            pyeong = AreaConverter.sqm_to_pyeong(sqm)
        else:
            pyeong_match = re.search(r'(\d+(?:\.\d+)?)\s*평', area_text)
            if pyeong_match:
                pyeong = float(pyeong_match.group(1))
                sqm = round(pyeong / 0.3025, 2)
        
        supply_match = re.search(r'(\d+(?:\.\d+)?)[㎡m²]?\s*/\s*(\d+(?:\.\d+)?)', area_text)
        if supply_match:
            sqm = float(supply_match.group(2))
            pyeong = AreaConverter.sqm_to_pyeong(sqm)
            
        # 4. 층/방향 추출
        floor_text = ""
        floor_selectors = [
            ".item_floor", ".info_floor", ".floor", "[class*='floor']",
            ".article_floor", ".item_info .floor", "span.floor",
            ".info_article_floor", ".cell_floor", ".data_floor",
            "td.floor", ".item_cell.floor", "[class*='Floor']"
        ]
        for sel in floor_selectors:
            elem = item.select_one(sel)
            if elem:
                floor_text = elem.get_text(strip=True)
                if floor_text: break
        
        if not floor_text:
            level_match = re.search(r'(고층|중층|저층)', full_text)
            floor_match = re.search(r'(\d+)\s*층', full_text)
            floor_total_match = re.search(r'(\d+)\s*/\s*(\d+)\s*층', full_text)
            
            if floor_total_match:
                floor_text = f"{floor_total_match.group(1)}/{floor_total_match.group(2)}층"
            elif floor_match:
                floor_text = f"{floor_match.group(1)}층"
            elif level_match:
                floor_text = level_match.group(1)
                
        direction = ""
        direction_selectors = [
            ".item_direction", ".direction", "[class*='direction']",
            ".info_direction", ".cell_direction", "[class*='Direction']"
        ]
        for sel in direction_selectors:
            elem = item.select_one(sel)
            if elem:
                direction = elem.get_text(strip=True)
                if direction: break
        
        if not direction:
            dir_match = re.search(r'(동향|서향|남향|북향|남동향|남서향|북동향|북서향|동남향|동북향|서남향|서북향)', full_text)
            if dir_match: direction = dir_match.group(1)
            
        if floor_text and direction:
            floor_text = f"{floor_text} {direction}"
        elif direction and not floor_text:
            floor_text = direction
            
        # 5. 특징 추출
        feature_text = PageParser._extract_feature(item, full_text)
        
        # 6. 매물 ID 추출
        article_id = ""
        link = item.select_one("a[href*='articleId']")
        if link:
            href = link.get('href', '')
            id_match = re.search(r'articleId=(\d+)', href)
            if id_match: article_id = id_match.group(1)
        else:
            article_id = item.get('data-article-id', '') or item.get('data-id', '')
            
        # 7. 가격 파싱
        매매가, 보증금, 월세 = "", "", ""
        if detected_type == "매매":
            매매가 = price_text.replace("매매", "").strip()
        elif detected_type == "전세":
            보증금 = price_text.replace("전세", "").strip()
        else:
            price_clean = price_text.replace("월세", "").strip()
            if "/" in price_clean:
                parts = price_clean.split("/")
                보증금 = parts[0].strip()
                월세 = parts[1].strip() if len(parts) > 1 else ""
            else:
                보증금 = price_clean
                
        # 8. 평당가 계산
        main_price = PriceConverter.to_int(매매가) if detected_type == "매매" else PriceConverter.to_int(보증금)
        price_per_pyeong_val = int(main_price / pyeong) if pyeong > 0 else 0
        
        return {
            "단지명": name, "단지ID": cid, "거래유형": detected_type,
            "매매가": 매매가, "보증금": 보증금, "월세": 월세,
            "면적(㎡)": sqm, "면적(평)": pyeong, 
            "평당가": price_per_pyeong_val,
            "평당가_표시": PriceConverter.to_string(price_per_pyeong_val) + "/평" if price_per_pyeong_val > 0 else "-",
            "층/방향": floor_text,
            "타입/특징": feature_text, "매물ID": article_id,
            "수집시각": DateTimeHelper.now_string()
        }

    @staticmethod
    def _extract_feature(item, full_text):
        feature_text = ""
        ad_keywords = [
            "부동산뱅크", "직방", "다방", "피터팬", "네이버부동산", "KB부동산",
            "부동산114", "호갱노노", "매물번호", "중개사무소", "공인중개사",
            "제공", "출처", "문의", "연락", "전화", "상담", "클릭", "바로가기",
            "더보기", "자세히", "확인하세요", "드립니다", "해드립니다"
        ]
        meaningful_keywords = [
            "급매", "급전", "급처분", "네고가능", "협의가능", "가격조정", "실매물",
            "올수리", "풀수리", "리모델링", "인테리어", "풀옵션", "빌트인", "새것", "깨끗",
            "신축", "준신축", "수리완료", "도배완료", "장판교체", "싱크대교체",
            "즉시입주", "입주가능", "공실", "실입주", "바로입주", "협의입주",
            "역세권", "초역세권", "더블역세권", "학군", "학교앞", "공원앞", "공원뷰",
            "한강뷰", "산뷰", "오션뷰", "시티뷰", "조망좋음", "조망권", "남향",
            "베란다확장", "확장형", "복층", "테라스", "정원", "마당", "옥상",
            "주차가능", "주차2대", "분리형", "투룸", "쓰리룸", "방3개", "방2개",
            "화장실2", "욕실2개", "드레스룸", "팬트리", "다용도실",
            "탑층", "로얄층", "고층", "중층", "저층", "1층", "꼭대기",
            "전세안고", "전세끼고", "주인직거래", "세입자있음", "세놓은",
            "펜트하우스", "복도식", "계단식", "엘리베이터", "경비실", "관리비저렴"
        ]
        feature_selectors = [
            ".item_desc", ".feature", ".info_sub", "[class*='desc']",
            ".article_desc", ".item_feature", ".description",
            ".info_article_feature", ".cell_feature", ".data_feature",
            ".item_info_desc", ".tag_list", ".item_tag", "[class*='tag']",
            ".item_detail", ".detail_info", ".sub_info"
        ]
        
        for sel in feature_selectors:
            elem = item.select_one(sel)
            if elem:
                text = elem.get_text(separator=" ", strip=True)
                if text and len(text) > 2:
                    is_ad_only = any(ad in text for ad in ad_keywords) and \
                                 not any(kw in text for kw in meaningful_keywords)
                    if not is_ad_only:
                        cleaned = text
                        for ad in ad_keywords:
                            cleaned = cleaned.replace(ad, "").strip()
                        if cleaned and len(cleaned) > 2:
                            feature_text = cleaned[:100]
                            break
                            
        if not feature_text or len(feature_text) < 3:
            found_features = []
            for kw in meaningful_keywords:
                if kw in full_text:
                    found_features.append(kw)
                    if len(found_features) >= 6:
                        break
            if found_features:
                feature_text = ", ".join(found_features)
                
        if not feature_text:
            room_info = []
            room_match = re.search(r'(\d)\s*룸|방\s*(\d)|(\d)\s*베드', full_text)
            bath_match = re.search(r'(\d)\s*욕|화장실\s*(\d)|(\d)\s*배스', full_text)
            if room_match:
                num = room_match.group(1) or room_match.group(2) or room_match.group(3)
                room_info.append(f"방{num}개")
            if bath_match:
                num = bath_match.group(1) or bath_match.group(2) or bath_match.group(3)
                room_info.append(f"화장실{num}개")
            if room_info:
                feature_text = ", ".join(room_info)
                
        return feature_text
