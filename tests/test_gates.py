"""门槛纯函数与防未来数据测试。"""

import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gate_backtest.backtest import (
    apply_signal_lag,
    build_at_least_n_position,
    build_combo_position,
    build_scaled_position,
    build_target_position,
    run_listed_backtest_fractional,
)
from gate_backtest.credit_mapping import (
    compute_baa_threshold_from_oas,
    compute_baa_threshold_v2,
    compute_rate_absolute_threshold,
)
from gate_backtest.data import align_asof
from gate_backtest.gates import credit_gate, oil_gate, rate_absolute_gate, rate_gate


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


class RateAbsoluteGateTest(unittest.TestCase):
    def test_threshold(self):
        idx = pd.bdate_range("2020-01-01", periods=3)
        s = pd.Series([3.0, 3.35, 4.0], index=idx)
        g = rate_absolute_gate(s, threshold=3.35)
        self.assertEqual(g.tolist(), [True, True, False])


class CreditMappingV2Test(unittest.TestCase):
    def test_v2_uses_full_oas_then_2007_baa(self):
        oas_idx = pd.bdate_range("2023-11-01", periods=50)
        oas = pd.Series(np.linspace(2.0, 5.0, 50), index=oas_idx)
        baa_idx = pd.bdate_range("2007-01-02", periods=200)
        baa = pd.Series(np.linspace(1.0, 4.0, 200), index=baa_idx)
        m = compute_baa_threshold_v2(oas, baa, baa_sample_start="2007-01-01", oas_target=3.6)
        self.assertGreater(m["q"], 0)
        self.assertLess(m["q"], 1)
        self.assertTrue(np.isfinite(m["tau"]))
        self.assertEqual(m["n_oas"], 50.0)

    def test_rate_abs_median(self):
        idx = pd.bdate_range("2007-01-02", periods=101)
        s = pd.Series(np.linspace(1.0, 5.0, 101), index=idx)
        m = compute_rate_absolute_threshold(s, sample_start="2007-01-01", percentile=0.5)
        self.assertAlmostEqual(m["tau_rate"], 3.0, places=6)


class ScaledPositionTest(unittest.TestCase):
    def test_scale_map_and_lag(self):
        idx = pd.bdate_range("2020-01-01", periods=10)
        # 三门：前半全开，后半只开 1 门
        g1 = pd.Series([True] * 10, index=idx)
        g2 = pd.Series([True] * 5 + [False] * 5, index=idx)
        g3 = pd.Series([True] * 5 + [False] * 5, index=idx)
        pos, _, _ = build_scaled_position([g1, g2, g3], idx, lag=1)
        # 滞后 1 日：第 0 日为 0；第 1 日起对应前一日的 3 门 → 1.0
        self.assertEqual(pos.iloc[0], 0.0)
        self.assertAlmostEqual(float(pos.iloc[1]), 1.0)
        # 第 6 日对应第 5 日（仍 3 门开完？ idx[5] 是后半第一天：只 g1 开 → 1 门 → 0.33）
        # 对齐后 count：日 0-4 = 3，日 5-9 = 1；滞后后日 1-5 = 1.0，日 6-9 = 0.33
        self.assertAlmostEqual(float(pos.iloc[5]), 1.0)
        self.assertAlmostEqual(float(pos.iloc[6]), 0.33)

    def test_at_least_two(self):
        idx = pd.bdate_range("2020-01-01", periods=6)
        g1 = pd.Series([True, True, True, False, False, True], index=idx)
        g2 = pd.Series([True, True, False, False, True, True], index=idx)
        g3 = pd.Series([True, False, False, False, False, False], index=idx)
        pos, _, _ = build_at_least_n_position([g1, g2, g3], idx, n_min=2, lag=1)
        # native counts: 3,2,1,0,1,2 → lagged: 0,3,2,1,0,1 → >=2: F,T,T,F,F,F
        self.assertEqual(pos.tolist(), [0.0, 1.0, 1.0, 0.0, 0.0, 0.0])


class BootstrapCITest(unittest.TestCase):
    def test_recentered_ci_contains_point(self):
        """重定心后 90% CI 应包含全样本点估计（修复未校正百分位偏置）。"""
        from gate_backtest.bootstrap import mdd_diff_block_bootstrap

        rng = np.random.default_rng(0)
        idx = pd.bdate_range("2010-01-01", periods=800)
        # 构造两条相关收益：策略略低波动
        shock = rng.normal(0.0005, 0.02, size=len(idx))
        rs = pd.Series(shock * 0.7, index=idx)
        rb = pd.Series(shock, index=idx)
        point, lo, hi, diffs = mdd_diff_block_bootstrap(
            rs, rb, block=20, n_boot=400, seed=1, ci=0.90
        )
        self.assertLessEqual(lo, point)
        self.assertLessEqual(point, hi)
        # 原始 bootstrap 均值相对点估计的偏置被重定心吸收：CI 半宽与原始百分位半宽同阶
        raw_lo, raw_hi = np.quantile(diffs, [0.05, 0.95])
        self.assertAlmostEqual(hi - lo, raw_hi - raw_lo, places=12)


class FractionalFeeTest(unittest.TestCase):
    def test_fee_on_delta_not_full_notional(self):
        idx = pd.bdate_range("2020-01-01", periods=5)
        ohlcv = pd.DataFrame(
            {"Open": [100.0] * 5, "Close": [100.0] * 5, "High": 100.0, "Low": 100.0, "Volume": 1},
            index=idx,
        )
        cash = pd.Series([0.0] * 5, index=idx)  # 零利率，便于核对
        # 日0: 0→0.5；日2: 0.5→1.0
        pos = pd.Series([0.5, 0.5, 1.0, 1.0, 1.0], index=idx)
        pf = run_listed_backtest_fractional(ohlcv, pos, cash, initial_capital=100_000.0, commission=0.001)
        # 第一次买入名义 50000，费 50 → 现金约 49950，股票 50000；收盘总权益 99950
        self.assertAlmostEqual(pf["total"].iloc[0], 99950.0, places=4)
        # 第二次再买约一半：总权益仍约 99950，目标全仓，Δ≈49975，费≈50 → 权益再降约 50
        self.assertLess(pf["total"].iloc[2], pf["total"].iloc[1])
        self.assertGreater(pf["total"].iloc[2], 99800.0)


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

    def test_scaled_position_invariant_to_future_changes(self):
        idx = pd.bdate_range("2020-01-01", periods=40)
        oil = pd.Series([100.0] * 40, index=idx)
        rate = pd.Series([3.0] * 40, index=idx)
        credit = pd.Series([1.5] * 40, index=idx)
        gates0 = [oil_gate(oil, 105, 5), rate_absolute_gate(rate, 3.35), credit_gate(credit, 3.32)]
        pos0, _, _ = build_scaled_position(gates0, idx)
        t = idx[20]
        oil2 = oil.copy()
        oil2.iloc[21:] = 200.0
        rate2 = rate.copy()
        rate2.iloc[21:] = 10.0
        credit2 = credit.copy()
        credit2.iloc[21:] = 9.0
        gates1 = [
            oil_gate(oil2, 105, 5),
            rate_absolute_gate(rate2, 3.35),
            credit_gate(credit2, 3.32),
        ]
        pos1, _, _ = build_scaled_position(gates1, idx)
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
