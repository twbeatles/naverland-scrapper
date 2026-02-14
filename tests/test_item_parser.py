import sys
import os
import unittest
from bs4 import BeautifulSoup

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.item_parser import ItemParser

class TestItemParser(unittest.TestCase):
    def test_parse_simple_item(self):
        html = """
        <div class="item_inner">
            <div class="item_type">아파트</div>
            <div class="item_price"><strong>매매 10억</strong></div>
            <div class="item_area">공급/전용 110/84㎡</div>
            <div class="item_floor">10/20층</div>
            <div class="item_direction">남향</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        item = soup.select_one(".item_inner")
        
        data = ItemParser.parse_element(item, "Sample Complex", "12345", "매매")

        self.assertEqual(data["단지명"], "Sample Complex")
        self.assertEqual(data["단지ID"], "12345")
        self.assertEqual(data["거래유형"], "매매")
        self.assertEqual(data["매매가"], "10억")
        self.assertEqual(data["면적(㎡)"], 84.0)
        self.assertIn("10/20층", data["층/방향"])
        self.assertIn("남향", data["층/방향"])

    def test_find_items(self):
        html = """
        <div class="article_list">
            <div class="item_article">Item 1</div>
            <div class="item_article">Item 2</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        items = ItemParser.find_items(soup)
        self.assertEqual(len(items), 2)

if __name__ == '__main__':
    unittest.main()
