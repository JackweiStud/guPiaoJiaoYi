import os
import sys
import unittest

import pandas as pd


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webhtml.data_handler import fetcher


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAkWithSpotFallback:
    def stock_market_activity_legu(self):
        return None

    def stock_zh_a_spot_em(self):
        return pd.DataFrame({"涨跌幅": [1.2, -0.5, 0.0, 2.1, -3.0, None]})


class FakeAkAllFail:
    def stock_market_activity_legu(self):
        return None

    def stock_zh_a_spot_em(self):
        return pd.DataFrame()


class BuildUpDownTest(unittest.TestCase):
    def test_falls_back_to_eastmoney_push2_when_legu_fails(self):
        original_ak = fetcher.ak
        original_get = fetcher.requests.get

        def fake_get(_url, params=None, **_kwargs):
            return FakeResponse(
                {
                    "data": {
                        "diff": [
                            {"f104": 2, "f105": 3, "f106": 0},
                            {"f104": 1, "f105": 1, "f106": 0},
                        ]
                    }
                }
            )

        fetcher.ak = FakeAkAllFail()
        fetcher.requests.get = fake_get
        try:
            result, fallback = fetcher.buildUpDown({"up": 0, "down": 0, "activityPct": "0%"})
        finally:
            fetcher.ak = original_ak
            fetcher.requests.get = original_get

        self.assertFalse(fallback)
        self.assertEqual(result["up"], 3)
        self.assertEqual(result["down"], 4)
        self.assertEqual(result["activityPct"], "42.9%")

    def test_eastmoney_push2_tolerates_partial_page_failure(self):
        original_ak = fetcher.ak
        original_get = fetcher.requests.get

        def fake_get(_url, params=None, **_kwargs):
            if "ulist.np" in _url:
                raise RuntimeError("index breadth failed")
            page = int(params["pn"])
            if page == 1:
                return FakeResponse({"data": {"total": 4, "diff": [{"f3": 1.2}, {"f3": -0.5}]}})
            raise RuntimeError("page failed")

        fetcher.ak = FakeAkAllFail()
        fetcher.requests.get = fake_get
        try:
            result, fallback = fetcher.buildUpDown({"up": 0, "down": 0, "activityPct": "0%"})
        finally:
            fetcher.ak = original_ak
            fetcher.requests.get = original_get

        self.assertFalse(fallback)
        self.assertEqual(result["up"], 1)
        self.assertEqual(result["down"], 1)
        self.assertEqual(result["activityPct"], "50.0%")

    def test_falls_back_to_a_share_spot_when_push2_fails(self):
        original_ak = fetcher.ak
        original_get = fetcher.requests.get

        def fake_get(*_args, **_kwargs):
            raise RuntimeError("network failed")

        fetcher.requests.get = fake_get
        fetcher.ak = FakeAkWithSpotFallback()
        try:
            result, fallback = fetcher.buildUpDown({"up": 0, "down": 0, "activityPct": "0%"})
        finally:
            fetcher.ak = original_ak
            fetcher.requests.get = original_get

        self.assertFalse(fallback)
        self.assertEqual(result["up"], 2)
        self.assertEqual(result["down"], 2)
        self.assertEqual(result["activityPct"], "50.0%")

    def test_returns_unavailable_marker_when_all_sources_fail(self):
        original_ak = fetcher.ak
        original_get = fetcher.requests.get

        def fake_get(*_args, **_kwargs):
            raise RuntimeError("network failed")

        fetcher.requests.get = fake_get
        fetcher.ak = FakeAkAllFail()
        try:
            result, fallback = fetcher.buildUpDown({"up": 0, "down": 0, "activityPct": "0%"})
        finally:
            fetcher.ak = original_ak
            fetcher.requests.get = original_get

        self.assertTrue(fallback)
        self.assertIsNone(result["up"])
        self.assertIsNone(result["down"])
        self.assertEqual(result["activityPct"], "-")


if __name__ == "__main__":
    unittest.main()
