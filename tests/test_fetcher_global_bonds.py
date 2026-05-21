import os
import sys
import unittest

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webhtml.config import market_watch_list as watch
from webhtml.data_handler import fetcher


class FakeYFinance:
    def download(self, **_kwargs):
        return pd.DataFrame(
            {"Close": [5.00, 5.10]},
            index=pd.to_datetime(["2026-05-20", "2026-05-21"]),
        )


class GlobalBondRiskTest(unittest.TestCase):
    def test_watch_list_contains_added_global_bond_yields(self):
        codes = [item["code"] for item in watch.RISKS]
        self.assertIn("US30Y", codes)
        self.assertIn("UK10Y", codes)
        self.assertIn("JP10Y", codes)

    def test_build_risks_fetches_us30y_and_uk_japan_yields(self):
        original_yf = fetcher.yf
        original_te = fetcher._fetch_tradingeconomics_bond_yield

        def fake_te(code):
            if code == "UK10Y":
                return (-0.3, 4.96)
            if code == "JP10Y":
                return (0.2, 2.77)
            return None

        fetcher.yf = FakeYFinance()
        fetcher._fetch_tradingeconomics_bond_yield = fake_te
        try:
            result, fallback = fetcher.buildRisks(
                [
                    {"category": "全球风险锚", "name": "30年期美债收益率", "code": "US30Y"},
                    {"category": "全球风险锚", "name": "英国10年期国债收益率", "code": "UK10Y"},
                    {"category": "全球风险锚", "name": "日本10年期国债收益率", "code": "JP10Y"},
                ],
                [
                    {"code": "US30Y", "value_or_change": 0, "interpretation": ""},
                    {"code": "UK10Y", "value_or_change": 0, "interpretation": ""},
                    {"code": "JP10Y", "value_or_change": 0, "interpretation": ""},
                ],
            )
        finally:
            fetcher.yf = original_yf
            fetcher._fetch_tradingeconomics_bond_yield = original_te

        by_code = {item["code"]: item for item in result}
        self.assertFalse(fallback)
        self.assertAlmostEqual(by_code["US30Y"]["price"], 5.10)
        self.assertAlmostEqual(by_code["US30Y"]["value_or_change"], 2.0)
        self.assertAlmostEqual(by_code["UK10Y"]["price"], 4.96)
        self.assertAlmostEqual(by_code["UK10Y"]["value_or_change"], -0.3)
        self.assertAlmostEqual(by_code["JP10Y"]["price"], 2.77)
        self.assertAlmostEqual(by_code["JP10Y"]["value_or_change"], 0.2)


if __name__ == "__main__":
    unittest.main()
