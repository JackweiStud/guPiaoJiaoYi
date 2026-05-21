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
        self.assertEqual(item["interpretation"], "美元兑离岸人民币上行，人民币走弱，对外资流入和A股估值偏负面")

    def test_nasdaq_up_and_hstech_down_is_transmission_blocked(self):
        view = build_report_view(
            {
                "date": "2026-05-21",
                "globals": [
                    {
                        "category": "香港",
                        "indicator": "恒生科技指数",
                        "code": "HSTECH.HK",
                        "price": 4795.23,
                        "value_or_change": -1.61,
                        "interpretation": "与A股科技板块形成共振",
                    },
                    {
                        "category": "美股",
                        "indicator": "纳斯达克100",
                        "code": "^NDX",
                        "price": 29297.70,
                        "value_or_change": 1.66,
                        "interpretation": "利好A股科技股开盘",
                    },
                ],
            }
        )

        hstech = view["globals_groups"][0]["items"][0]
        ndx = view["globals_groups"][1]["items"][0]
        self.assertIn("传导受阻", hstech["interpretation"])
        self.assertIn("不能简单外推为A股科技共振", ndx["interpretation"])
        self.assertEqual(view["market_signals"][0]["signal"], "china_tech_transmission_blocked")

    def test_us10y_rising_pressures_growth_valuation(self):
        view = build_report_view(
            {
                "date": "2026-05-21",
                "risks": [
                    {
                        "category": "全球风险锚",
                        "name": "10年期美债收益率",
                        "code": "US10Y",
                        "price": 4.55,
                        "value_or_change": 0.08,
                        "interpretation": "对高估值成长股构成潜在压力",
                    }
                ],
            }
        )

        risk = view["risks"][0]
        self.assertEqual(risk["interpretation"], "10年期美债收益率上行，全球估值锚抬升，对高估值成长股和A股科技偏压制")

    def test_global_long_yields_have_country_specific_interpretations(self):
        view = build_report_view(
            {
                "date": "2026-05-21",
                "risks": [
                    {
                        "category": "全球风险锚",
                        "name": "30年期美债收益率",
                        "code": "US30Y",
                        "price": 5.12,
                        "value_or_change": 0.4,
                        "interpretation": "",
                    },
                    {
                        "category": "全球风险锚",
                        "name": "英国10年期国债收益率",
                        "code": "UK10Y",
                        "price": 4.96,
                        "value_or_change": -0.3,
                        "interpretation": "",
                    },
                    {
                        "category": "全球风险锚",
                        "name": "日本10年期国债收益率",
                        "code": "JP10Y",
                        "price": 2.77,
                        "value_or_change": 0.2,
                        "interpretation": "",
                    },
                ],
            }
        )

        risks = {item["code"]: item for item in view["risks"]}
        self.assertEqual(risks["US30Y"]["interpretation"], "30年期美债收益率上行，长端期限溢价抬升，对全球久期资产和成长股估值偏压制")
        self.assertEqual(risks["UK10Y"]["interpretation"], "英国10年期国债收益率下行，英镑资产长端利率压力缓解，对欧洲风险资产边际正面")
        self.assertEqual(risks["JP10Y"]["interpretation"], "日本10年期国债收益率上行，日债利率正常化压力升温，全球套息交易和高估值资产承压")

    def test_us10y_negative_change_is_not_labeled_with_up_arrow(self):
        view = build_report_view(
            {
                "date": "2026-05-21",
                "risks": [
                    {
                        "category": "全球风险锚",
                        "name": "10年期美债收益率",
                        "code": "US10Y",
                        "price": 4.45,
                        "value_or_change": -2.04,
                        "interpretation": "",
                    }
                ],
            }
        )

        risk = view["risks"][0]
        self.assertEqual(risk["value_or_change_str"], "-2.04%")
        self.assertEqual(risk["interpretation"], "10年期美债收益率下行，成长股估值压力缓解，对A股科技偏正面")


if __name__ == "__main__":
    unittest.main()
