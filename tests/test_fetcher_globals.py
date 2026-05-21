import math
import os
import sys
import unittest

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webhtml.data_handler import fetcher


class FakeTicker:
    def __init__(self, fast_info):
        self.fast_info = fast_info


class FakeYFinance:
    def __init__(self, data):
        self.data = data
        self.fast_info_by_ticker = {}

    def download(self, **_kwargs):
        return self.data

    def Ticker(self, ticker):
        return FakeTicker(self.fast_info_by_ticker.get(ticker, {}))


class BuildGlobalsTest(unittest.TestCase):
    def test_uses_last_two_valid_closes_when_yfinance_has_nan_gaps(self):
        data = pd.DataFrame(
            {
                ("Close", "^GSPC"): [100.0, 110.0, math.nan],
                ("Close", "BTC-USD"): [200.0, math.nan, 220.0],
            },
            index=pd.to_datetime(["2026-05-19", "2026-05-20", "2026-05-21"]),
        )

        original_yf = fetcher.yf
        fetcher.yf = FakeYFinance(data)
        try:
            result, fallback = fetcher.buildGlobals(
                [
                    {"category": "美股", "indicator": "标普500", "code": "^GSPC"},
                    {"category": "加密货币", "indicator": "比特币(BTC)", "code": "BTC-USD"},
                ],
                [
                    {"code": "^GSPC", "value_or_change": 0, "interpretation": "mock"},
                    {"code": "BTC-USD", "value_or_change": 0, "interpretation": "mock"},
                ],
            )
        finally:
            fetcher.yf = original_yf

        by_code = {item["code"]: item for item in result}
        self.assertFalse(fallback)
        self.assertAlmostEqual(by_code["^GSPC"]["price"], 110.0)
        self.assertAlmostEqual(by_code["^GSPC"]["value_or_change"], 10.0)
        self.assertAlmostEqual(by_code["BTC-USD"]["price"], 220.0)
        self.assertAlmostEqual(by_code["BTC-USD"]["value_or_change"], 10.0)

    def test_uses_fast_info_previous_close_when_only_one_valid_close_exists(self):
        data = pd.DataFrame(
            {"Close": [math.nan, math.nan, 4808.06]},
            index=pd.to_datetime(["2026-05-19", "2026-05-20", "2026-05-21"]),
        )

        original_yf = fetcher.yf
        fake_yf = FakeYFinance(data)
        fake_yf.fast_info_by_ticker["HSTECH.HK"] = {
            "lastPrice": 4808.06,
            "previousClose": 4873.82,
        }
        fetcher.yf = fake_yf
        try:
            result, fallback = fetcher.buildGlobals(
                [{"category": "香港", "indicator": "恒生科技指数", "code": "HSTECH.HK"}],
                [{"code": "HSTECH.HK", "value_or_change": 0, "interpretation": "mock"}],
            )
        finally:
            fetcher.yf = original_yf

        self.assertFalse(fallback)
        self.assertAlmostEqual(result[0]["price"], 4808.06)
        self.assertAlmostEqual(
            result[0]["value_or_change"],
            (4808.06 - 4873.82) / 4873.82 * 100,
        )


if __name__ == "__main__":
    unittest.main()
