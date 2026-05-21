import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webhtml.analysis.calculator import build_report_view


class GlobalInterpretationTest(unittest.TestCase):
    def test_usd_cnh_positive_change_means_renminbi_weaker(self):
        view = build_report_view(
            {
                "date": "2026-05-21",
                "globals": [
                    {
                        "category": "汇率",
                        "indicator": "美元/离岸CNH",
                        "code": "CNH=X",
                        "price": 6.81,
                        "value_or_change": 0.11,
                        "interpretation": "人民币升值，利好外资流入",
                    }
                ],
            }
        )

        item = view["globals_groups"][0]["items"][0]
        self.assertEqual(item["interpretation"], "美元兑离岸人民币上行，人民币走弱")


if __name__ == "__main__":
    unittest.main()
