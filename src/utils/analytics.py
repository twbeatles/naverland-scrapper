from typing import List, Tuple, Dict
from datetime import datetime, timedelta

class MarketAnalyzer:
    """시세 분석 및 예측 (v13.0)"""
    
    @staticmethod
    def calculate_price_change_rate(old_price: int, new_price: int) -> float:
        """가격 변동률 계산 (%)"""
        if old_price <= 0:
            return 0.0
        return round(((new_price - old_price) / old_price) * 100, 2)
    
    @staticmethod
    def calculate_weekly_trend(price_history: List[Tuple[str, int]]) -> dict:
        """주간 가격 트렌드 분석"""
        if len(price_history) < 2:
            return {"trend": "insufficient_data", "change_rate": 0, "avg_price": 0}
        
        # 최근 7일 데이터 필터링
        week_ago = datetime.now() - timedelta(days=7)
        recent_data = [
            (d, p) for d, p in price_history 
            if datetime.strptime(d, "%Y-%m-%d") >= week_ago
        ]
        
        if len(recent_data) < 2:
            return {"trend": "insufficient_data", "change_rate": 0, "avg_price": 0}
        
        prices = [p for _, p in recent_data]
        avg_price = sum(prices) // len(prices)
        change_rate = MarketAnalyzer.calculate_price_change_rate(prices[0], prices[-1])
        
        return {
            "trend": MarketAnalyzer.analyze_trend(prices),
            "change_rate": change_rate,
            "avg_price": avg_price,
            "min_price": min(prices),
            "max_price": max(prices)
        }
    
    @staticmethod
    def calculate_monthly_trend(price_history: List[Tuple[str, int]]) -> dict:
        """월간 가격 트렌드 분석"""
        if len(price_history) < 2:
            return {"trend": "insufficient_data", "change_rate": 0, "avg_price": 0}
        
        # 최근 30일 데이터 필터링
        month_ago = datetime.now() - timedelta(days=30)
        recent_data = [
            (d, p) for d, p in price_history 
            if datetime.strptime(d, "%Y-%m-%d") >= month_ago
        ]
        
        if len(recent_data) < 2:
            return {"trend": "insufficient_data", "change_rate": 0, "avg_price": 0}
        
        prices = [p for _, p in recent_data]
        avg_price = sum(prices) // len(prices)
        change_rate = MarketAnalyzer.calculate_price_change_rate(prices[0], prices[-1])
        
        return {
            "trend": MarketAnalyzer.analyze_trend(prices),
            "change_rate": change_rate,
            "avg_price": avg_price,
            "min_price": min(prices),
            "max_price": max(prices)
        }
    
    @staticmethod
    def analyze_trend(prices: List[int]) -> str:
        """트렌드 분석 (상승/하락/횡보)"""
        if len(prices) < 2:
            return "unknown"
        
        first_half = sum(prices[:len(prices)//2]) / (len(prices)//2)
        second_half = sum(prices[len(prices)//2:]) / (len(prices) - len(prices)//2)
        
        change_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
        
        if change_rate > 3:
            return "상승"
        elif change_rate < -3:
            return "하락"
        else:
            return "횡보"
    
    @staticmethod
    def compare_to_average(current_price: int, avg_price: int) -> dict:
        """평균 시세 대비 현재 가격 비교"""
        if avg_price <= 0:
            return {"status": "unknown", "difference": 0, "percentage": 0}
        
        diff = current_price - avg_price
        percentage = round((diff / avg_price) * 100, 1)
        
        if percentage > 10:
            status = "고가"
        elif percentage > 5:
            status = "약간 고가"
        elif percentage < -10:
            status = "저가"
        elif percentage < -5:
            status = "약간 저가"
        else:
            status = "적정가"
        
        return {
            "status": status,
            "difference": diff,
            "percentage": percentage
        }


class ComplexComparator:
    """단지 간 시세 비교 (v13.0)"""
    
    def __init__(self, db):
        self.db = db
    
    def compare(self, complex_ids: List[str], trade_type: str = "매매") -> dict:
        """여러 단지의 시세 비교 데이터 반환"""
        result = {}
        for cid in complex_ids:
            history = self.db.get_complex_price_history(cid, trade_type)
            if history:
                prices = [row[5] for row in history]  # avg_price
                result[cid] = {
                    "avg_price": sum(prices) // len(prices) if prices else 0,
                    "min_price": min(prices) if prices else 0,
                    "max_price": max(prices) if prices else 0,
                    "data_points": len(history)
                }
        return result
