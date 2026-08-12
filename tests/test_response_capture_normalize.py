import unittest

from src.core.services.response_capture import normalize_article_payload


class TestNormalizeArticlePayload(unittest.TestCase):
    def test_maps_list_meta_fields(self):
        article = {
            "articleNo": "2630745167",
            "tradeTypeCode": "A1",
            "dealOrWarrantPrc": "12억",
            "area1": 84.5,
            "floorInfo": "10/20",
            "direction": "남향",
            "articleConfirmYmd": "20260801",
            "buildingName": "101동",
            "areaName": "84A",
            "sameAddrCnt": 3,
            "cpName": "네이버",
            "latitude": 37.56,
            "longitude": 126.98,
            "articleFeatureDesc": "로얄층",
            "realtorName": "약수하나공인중개사사무소",
            "realtorId": "r-123",
            "sameAddrMaxPrc": "20억",
            "sameAddrMinPrc": "18억",
            "verificationTypeCode": "DOC",
            "detailAddress": "33동 1201호",
            "isDirectTrade": False,
        }
        item = normalize_article_payload(
            article,
            complex_name="남산타운",
            complex_id="3833",
            requested_trade_type="매매",
            asset_type="APT",
        )
        self.assertEqual(item["매물ID"], "2630745167")
        self.assertEqual(item["확인일"], "20260801")
        self.assertEqual(item["동"], "101동")
        self.assertEqual(item["타입명"], "84A")
        self.assertEqual(item["동일주소건수"], 3)
        self.assertEqual(item["정보제공"], "네이버")
        self.assertEqual(item["부동산상호"], "약수하나공인중개사사무소")
        self.assertEqual(item["중개ID"], "r-123")
        self.assertEqual(item["동일주소최고가"], "20억")
        self.assertEqual(item["동일주소최저가"], "18억")
        self.assertEqual(item["확인유형"], "DOC")
        self.assertEqual(item["상세주소"], "33동 1201호")
        self.assertEqual(item["직거래"], "N")
        self.assertAlmostEqual(float(item["위도"]), 37.56)
        self.assertAlmostEqual(float(item["경도"]), 126.98)


if __name__ == "__main__":
    unittest.main()
