"""门槛纯函数与防未来数据测试。"""

import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gate_backtest.backtest import apply_signal_lag, build_combo_position, build_target_position
from gate_backtest.credit_mapping import compute_baa_threshold_from_oas
from gate_backtest.data import align_asof
from gate_backtest.gates import credit_gate, oil_gate, rate_gate


class OilGateTest(unittest.TestCase):
    def test_requires_five_consecutive_days_below(self):
        idx = pd.bdate_range("2020-01-01", periods=10)
        brent = pd.Series([110, 100, 100, 100, 100, 100, 106, 100, 100, 100], index=idx)
        g = oil_gate(brent, threshold=105, streak_days=5)
        # 第 2–6 日低于 105，第 6 日 streak=5 才开
        self.assertFalse(bool(g.iloc[4]))  # 4 天连续仍不足
        self.assertTrue(bool(g.iloc[5]))
        self.assertFalse(bool(g.iloc[6]))  # 106 打断


class RateGateTest(unittest.TestCase):
    def test_open_when_below_ma(self):
        idx = pd.bdate_range("2020-01-01", periods=30)
        # 前 20 日稳定 4.0，之后降到 3.5 → 应低于 MA
        vals = [4.0] * 20 + [3.5] * 10
        g = rate_gate(pd.Series(vals, index=idx), ma_window=20, band=0.0)
        self.assertTrue(bool(g.iloc[19]))  # 恰满窗口且 s == MA → ≤ 放行
        self.assertTrue(bool(g.iloc[20]))  # 降至 3.5 < MA


class CreditGateTest(unittest.TestCase):
    def test_threshold(self):
        idx = pd.bdate_range("2020-01-01", periods=3)
        s = pd.Series([1.5, 1.8, 2.0], index=idx)
        g = credit_gate(s, threshold=1.8)
        self.assertEqual(g.tolist(), [True, True, False])


class CreditMappingTest(unittest.TestCase):
    def test_mapping_uses_overlap_only(self):
        idx = pd.bdate_range("2023-11-01", periods=100)
        oas = pd.Series(np.linspace(2.5, 4.5, 100), index=idx)
        baa = pd.Series(np.linspace(1.0, 2.0, 100), index=idx)
        m = compute_baa_threshold_from_oas(oas, baa, overlap_start="2023-11-01", oas_target=3.6)
        self.assertGreater(m["q"], 0)
        self.assertLess(m["q"], 1)
        self.assertTrue(np.isfinite(m["tau"]))


class AlignAsOfTest(unittest.TestCase):
    def test_no_interpolation_only_last_known(self):
        native = pd.Series([10.0, 20.0], index=pd.to_datetime(["2020-01-01", "2020-01-03"]))
        target = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"])
        aligned, carry, streak = align_asof(native, target)
        self.assertEqual(list(aligned.values), [10.0, 10.0, 20.0, 20.0])
        self.assertEqual(carry, 2)  # 01-02, 01-04
        self.assertEqual(streak, 1)

    def test_does_not_invent_before_first_print(self):
        native = pd.Series([5.0], index=pd.to_datetime(["2020-01-03"]))
        target = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
        aligned, carry, _ = align_asof(native, target)
        self.assertTrue(np.isnan(aligned.iloc[0]))
        self.assertTrue(np.isnan(aligned.iloc[1]))
        self.assertEqual(aligned.iloc[2], 5.0)
        self.assertEqual(carry, 0)


class NoLookaheadTest(unittest.TestCase):
    """专门防未来数据：改动 t 日之后的数据，t 日信号不得变。"""

    def test_oil_gate_invariant_to_future_changes(self):
        idx = pd.bdate_range("2020-01-01", periods=12)
        base = pd.Series([100.0] * 12, index=idx)
        t = idx[6]
        g0 = oil_gate(base, threshold=105, streak_days=5)
        sig0 = build_target_position(g0, idx)[0]

        # 改动 t 之后的油价
        altered = base.copy()
        altered.iloc[7:] = 200.0
        g1 = oil_gate(altered, threshold=105, streak_days=5)
        sig1 = build_target_position(g1, idx)[0]

        # t 日及之前的仓位信号应完全一致
        self.assertTrue((sig0.loc[:t] == sig1.loc[:t]).all())

    def test_combo_position_invariant_to_future_changes(self):
        idx = pd.bdate_range("2020-01-01", periods=40)
        oil = pd.Series([100.0] * 40, index=idx)
        rate = pd.Series([4.0] * 30 + [3.0] * 10, index=idx)
        credit = pd.Series([1.5] * 40, index=idx)
        g_oil = oil_gate(oil, 105, 5)
        g_rate = rate_gate(rate, 20, 0.0)
        g_credit = credit_gate(credit, 1.8)
        pos0, _, _ = build_combo_position([g_oil, g_rate, g_credit], idx)

        t = idx[25]
        oil2 = oil.copy()
        oil2.iloc[26:] = 200.0
        rate2 = rate.copy()
        rate2.iloc[26:] = 10.0
        credit2 = credit.copy()
        credit2.iloc[26:] = 5.0
        pos1, _, _ = build_combo_position(
            [oil_gate(oil2, 105, 5), rate_gate(rate2, 20, 0.0), credit_gate(credit2, 1.8)],
            idx,
        )
        self.assertTrue((pos0.loc[:t] == pos1.loc[:t]).all())

    def test_signal_lag_at_least_one_day(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        g = pd.Series([False, True, True, False, True], index=idx)
        lagged = apply_signal_lag(g, lag=1)
        self.assertFalse(bool(lagged.iloc[0]))
        self.assertFalse(bool(lagged.iloc[1]))  # 原日1的 True 到日2才生效
        self.assertTrue(bool(lagged.iloc[2]))


if __name__ == "__main__":
    unittest.main()
