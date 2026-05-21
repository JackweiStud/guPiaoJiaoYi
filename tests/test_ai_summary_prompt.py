import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webhtml.analysis.ai_summary import build_prompt_from_view


class AiSummaryPromptTest(unittest.TestCase):
    def test_prompt_uses_structured_market_signals(self):
        prompt = build_prompt_from_view(
            {
                "indexes": [{"name": "上证指数", "change_pct_str": "-1.00%"}],
                "up_down": {"up": 800, "down": 4200, "label": "普跌", "activityPct": "84.0%"},
                "sectors": [{"etf_name": "医药ETF"}, {"etf_name": "芯片ETF"}],
                "market_signals": [
                    {
                        "signal": "china_tech_transmission_blocked",
                        "impact": "negative",
                        "strength": "medium",
                        "confidence": "high",
                        "summary": "美股科技强势，但港股科技下跌且人民币走弱，外部科技行情对中国资产传导受阻",
                        "evidence": ["纳斯达克100 +1.66%", "恒生科技 -1.61%", "USD/CNH +0.11%"],
                    }
                ],
            }
        )

        self.assertIn("不得推翻结构化信号", prompt)
        self.assertIn("china_tech_transmission_blocked", prompt)
        self.assertIn("外部科技行情对中国资产传导受阻", prompt)
        self.assertIn("纳斯达克100 +1.66%", prompt)


if __name__ == "__main__":
    unittest.main()
