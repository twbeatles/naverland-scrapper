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
        self.assertAlmostEqual(float(item["위도"]), 37.56)
        self.assertAlmostEqual(float(item["경도"]), 126.98)


if __name__ == "__main__":
    unittest.main()
