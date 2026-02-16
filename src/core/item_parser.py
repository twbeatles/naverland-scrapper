import re
from src.utils.helpers import AreaConverter, PriceConverter, PricePerPyeongCalculator, DateTimeHelper
from src.utils.logger import get_logger

logger = get_logger("ItemParser")

class ItemParser:
    """BeautifulSoup 기반 매물 아이템 파서 (v14.0)"""
    ITEM_SELECTORS = (
        ".item_article", ".item_inner", ".article_item", "[class*='ArticleItem']",
        ".complex_item", "li[data-article-id]", ".list_item",
    )
    TYPE_SELECTORS = (".type", ".trade_type", "[class*='type']", ".item_type", ".article_type")
    PRICE_SELECTORS = (
        ".item_price strong", ".price_line", ".article_price", "[class*='price']",
        ".selling_price", ".trade_price", "strong[class*='Price']", ".price",
    )
    AREA_SELECTORS = (".item_area", ".info_area", ".article_area", "[class*='area']")
    FLOOR_SELECTORS = (
        ".item_floor", ".info_floor", ".floor", "[class*='floor']", ".article_floor",
        ".item_info .floor", "span.floor", ".info_article_floor", ".cell_floor",
        ".data_floor", "td.floor", ".item_cell.floor", "[class*='Floor']",
    )
    DIRECTION_SELECTORS = (
        ".item_direction", ".direction", "[class*='direction']",
        ".info_direction", ".cell_direction", "[class*='Direction']",
    )
    FEATURE_SELECTORS = (
        ".item_desc", ".feature", ".info_sub", "[class*='desc']", ".article_desc",
        ".item_feature", ".description", ".info_article_feature", ".cell_feature",
        ".data_feature", ".item_info_desc", ".tag_list", ".item_tag",
        "[class*='tag']", ".item_detail", ".detail_info", ".sub_info",
    )
    AD_KEYWORDS = (
        "부동산뱅크", "직방", "다방", "피터팬", "네이버부동산", "KB부동산",
        "부동산114", "호갱노노", "매물번호", "중개사무소", "공인중개사",
        "제공", "출처", "문의", "연락", "전화", "상담", "클릭", "바로가기",
        "더보기", "자세히", "확인하세요", "드립니다", "해드립니다",
    )
    MEANINGFUL_KEYWORDS = (
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
        "펜트하우스", "복도식", "계단식", "엘리베이터", "경비실", "관리비저렴",
    )
    PRICE_TEXT_RE = re.compile(r'(\d+억\s*\d*,?\d*만?|\d+,?\d*만)')
    MONTHLY_RE = re.compile(r'\d+[억만]?\s*/\s*\d+')
    SQM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:㎡|m²)')
    PYEONG_RE = re.compile(r'(\d+(?:\.\d+)?)\s*평')
    SUPPLY_RE = re.compile(r'(\d+(?:\.\d+)?)[㎡m²]?\s*/\s*(\d+(?:\.\d+)?)')
    FLOOR_LEVEL_RE = re.compile(r'(고층|중층|저층)')
    FLOOR_RE = re.compile(r'(\d+)\s*층')
    FLOOR_TOTAL_RE = re.compile(r'(\d+)\s*/\s*(\d+)\s*층')
    DIRECTION_RE = re.compile(r'(동향|서향|남향|북향|남동향|남서향|북동향|북서향|동남향|동북향|서남향|서북향)')
    ROOM_RE = re.compile(r'(\d)\s*룸|방\s*(\d)|(\d)\s*베드')
    BATH_RE = re.compile(r'(\d)\s*욕|화장실\s*(\d)|(\d)\s*배스')
    ARTICLE_ID_RE = re.compile(r'articleId=(\d+)')

    @staticmethod
    def _first_text(item, selectors, separator="", strip=True):
        for sel in selectors:
            elem = item.select_one(sel)
            if elem:
                text = elem.get_text(separator=separator, strip=strip)
                if text:
                    return text
        return ""
    
    @staticmethod
    def find_items(soup):
        """soup에서 매물 아이템 요소들을 찾아 반환"""
        # 우선순위 선택자 시도
        for sel in ItemParser.ITEM_SELECTORS:
            found = soup.select(sel)
            if found:
                logger.debug(f"선택자 '{sel}': {len(found)}개 발견")
                return found
        
        # 실패 시 대체 방식
        logger.debug("표준 선택자 실패, 대체 방식 시도...")
        return soup.find_all(['div', 'li'], class_=lambda x: x and ('item' in x.lower() or 'article' in x.lower()))

    @staticmethod
    def parse_element(item, name, cid, ttype):
        """개별 아이템 요소 파싱"""
        full_text = item.get_text(separator=" ", strip=True)
        detected_type = ttype
        
        # 거래유형 감지
        type_text = ItemParser._first_text(item, ItemParser.TYPE_SELECTORS, strip=True)
        if "매매" in type_text:
            detected_type = "매매"
        elif "전세" in type_text:
            detected_type = "전세"
        elif "월세" in type_text:
            detected_type = "월세"
        
        # 가격 추출
        price_text = ItemParser._first_text(item, ItemParser.PRICE_SELECTORS, strip=True)
        if price_text and not ("억" in price_text or "만" in price_text or price_text.replace(",", "").replace("/", "").isdigit()):
            price_text = ""
        
        if not price_text:
            price_match = ItemParser.PRICE_TEXT_RE.search(full_text)
            if price_match:
                price_text = price_match.group(1)
        
        # 유형 재확인
        short_text = full_text[:50]
        if ItemParser.MONTHLY_RE.search(price_text):
            detected_type = "월세"
        elif "전세" in short_text:
            detected_type = "전세"
        elif "매매" in short_text:
            detected_type = "매매"
        
        # 면적 추출
        area_text, sqm, pyeong = ItemParser._first_text(item, ItemParser.AREA_SELECTORS, strip=True), 0, 0
        if not area_text:
            area_text = full_text
        
        sqm_match = ItemParser.SQM_RE.search(area_text)
        if sqm_match:
            sqm = float(sqm_match.group(1))
            pyeong = AreaConverter.sqm_to_pyeong(sqm)
        else:
            pyeong_match = ItemParser.PYEONG_RE.search(area_text)
            if pyeong_match:
                pyeong = float(pyeong_match.group(1))
                sqm = round(pyeong / 0.3025, 2)
        
        supply_match = ItemParser.SUPPLY_RE.search(area_text)
        if supply_match:
            sqm = float(supply_match.group(2))
            pyeong = AreaConverter.sqm_to_pyeong(sqm)
        
        # 층/방향 추출
        floor_text = ItemParser._first_text(item, ItemParser.FLOOR_SELECTORS, strip=True)
        
        if not floor_text:
            level_match = ItemParser.FLOOR_LEVEL_RE.search(full_text)
            floor_match = ItemParser.FLOOR_RE.search(full_text)
            floor_total_match = ItemParser.FLOOR_TOTAL_RE.search(full_text)
            
            if floor_total_match:
                floor_text = f"{floor_total_match.group(1)}/{floor_total_match.group(2)}층"
            elif floor_match:
                floor_text = f"{floor_match.group(1)}층"
            elif level_match:
                floor_text = level_match.group(1)
        
        direction = ItemParser._first_text(item, ItemParser.DIRECTION_SELECTORS, strip=True)
        
        if not direction:
            dir_match = ItemParser.DIRECTION_RE.search(full_text)
            if dir_match:
                direction = dir_match.group(1)
        
        if floor_text and direction:
            floor_text = f"{floor_text} {direction}"
        elif direction and not floor_text:
            floor_text = direction
        
        # 특징 추출
        feature_text = ""
        for sel in ItemParser.FEATURE_SELECTORS:
            elem = item.select_one(sel)
            if not elem:
                continue
            text = elem.get_text(separator=" ", strip=True)
            if not text or len(text) <= 2:
                continue

            is_ad_only = any(ad in text for ad in ItemParser.AD_KEYWORDS) and \
                         not any(kw in text for kw in ItemParser.MEANINGFUL_KEYWORDS)
            if is_ad_only:
                continue

            cleaned = text
            for ad in ItemParser.AD_KEYWORDS:
                cleaned = cleaned.replace(ad, "").strip()
            if cleaned and len(cleaned) > 2:
                feature_text = cleaned[:100]
                break
        
        if not feature_text or len(feature_text) < 3:
            found_features = []
            for kw in ItemParser.MEANINGFUL_KEYWORDS:
                if kw in full_text:
                    found_features.append(kw)
                    if len(found_features) >= 6:
                        break
            if found_features:
                feature_text = ", ".join(found_features)
        
        if not feature_text:
            room_info = []
            room_match = ItemParser.ROOM_RE.search(full_text)
            bath_match = ItemParser.BATH_RE.search(full_text)
            if room_match:
                num = room_match.group(1) or room_match.group(2) or room_match.group(3)
                room_info.append(f"방{num}개")
            if bath_match:
                num = bath_match.group(1) or bath_match.group(2) or bath_match.group(3)
                room_info.append(f"화장실{num}개")
            if room_info:
                feature_text = ", ".join(room_info)
        
        # 매물 ID
        article_id = ""
        link = item.select_one("a[href*='articleId']")
        if link:
            href = link.get('href', '')
            id_match = ItemParser.ARTICLE_ID_RE.search(href)
            if id_match:
                article_id = id_match.group(1)
        else:
            article_id = item.get('data-article-id', '') or item.get('data-id', '')
        
        # 가격 파싱 (매매가, 보증금, 월세)
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
        
        main_price = PriceConverter.to_int(매매가) if detected_type == "매매" else PriceConverter.to_int(보증금)
        price_per_pyeong = PricePerPyeongCalculator.calculate(main_price, pyeong) if pyeong > 0 else 0
        
        return {
            "단지명": name, "단지ID": cid, "거래유형": detected_type,
            "매매가": 매매가, "보증금": 보증금, "월세": 월세,
            "면적(㎡)": sqm, "면적(평)": pyeong, 
            "평당가": price_per_pyeong,
            "평당가_표시": PricePerPyeongCalculator.format(price_per_pyeong),
            "층/방향": floor_text,
            "타입/특징": feature_text, "매물ID": article_id,
            "수집시각": DateTimeHelper.now_string()
        }
