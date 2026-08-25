"""下一代量化引擎自动化单元测试套件 (NextGen Quant Test Suite)"""

import unittest
import numpy as np
import pandas as pd

from quant.factors.rsrs import calc_rsrs, calc_rsrs_series
from quant.factors.kama import calc_kama, calc_efficiency_ratio
from quant.factors.volatility import calc_atr, calc_donchian_channels, calc_risk_adjusted_momentum
from quant.risk.trailing_stop import ATRTrailingStop, calc_volatility_position_size
from quant.regime.macro_regime import MacroRegimeClassifier
from quant.rotation.universe import DEFAULT_ETF_UNIVERSE, load_universe_data
from quant.rotation.scorer import score_universe_cross_section, compute_etf_single_date_factors
from quant.rotation.engine import select_top_etfs
from quant.backtest.single_asset import calculate_metrics, run_nextgen_single_backtest
from quant.backtest.portfolio import run_portfolio_rotation_backtest


class TestQuantEngine(unittest.TestCase):

    def setUp(self):
        # 构造 100 天模拟日线数据
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        np.random.seed(42)
        close_prices = 1.0 + np.cumsum(np.random.randn(100) * 0.01)
        high_prices = close_prices + np.abs(np.random.randn(100) * 0.008)
        low_prices = close_prices - np.abs(np.random.randn(100) * 0.008)
        volumes = np.random.randint(100000, 500000, size=100)

        self.sample_df = pd.DataFrame({
            "DateTime": dates,
            "OpenValue": close_prices - 0.002,
            "CloseValue": close_prices,
            "HighValue": high_prices,
            "LowValue": low_prices,
            "Volume": volumes,
            "ChangeRate": [0.0] * 100
        }).set_index("DateTime")

    def test_rsrs_calculation(self):
        """测试 RSRS 因子计算"""
        rsrs_df = calc_rsrs_series(self.sample_df, n_window=16, m_window=50)
        self.assertEqual(len(rsrs_df), 100)
        self.assertIn("rsrs_score", rsrs_df.columns)
        self.assertIn("rsrs_slope", rsrs_df.columns)

        res = calc_rsrs(self.sample_df, n_window=16, m_window=50)
        self.assertIn("score", res)
        self.assertIn("signal", res)
        self.assertIn(res["signal"], ["BUY", "SELL", "HOLD"])

    def test_kama_calculation(self):
        """测试 KAMA 自适应均线与效率比"""
        er = calc_efficiency_ratio(self.sample_df["CloseValue"], period=10)
        self.assertEqual(len(er), 100)
        self.assertTrue((er >= 0.0).all() and (er <= 1.0).all())

        kama = calc_kama(self.sample_df["CloseValue"], er_period=10, fast_period=2, slow_period=30)
        self.assertEqual(len(kama), 100)
        # 预热期后 KAMA 不应全为 NaN
        self.assertFalse(pd.isna(kama.iloc[-1]))

    def test_volatility_factors(self):
        """测试 ATR 与唐奇安通道"""
        atr = calc_atr(self.sample_df, period=14)
        self.assertEqual(len(atr), 100)
        self.assertTrue((atr.dropna() > 0).all())

        donchian = calc_donchian_channels(self.sample_df, period=20)
        self.assertIn("donchian_upper", donchian.columns)
        self.assertIn("donchian_lower", donchian.columns)

    def test_trailing_stop(self):
        """测试 ATR 动态移动追踪止损逻辑"""
        stop_mgr = ATRTrailingStop(atr_multiplier=2.5, min_profit_protect_pct=0.05)
        init_stop = stop_mgr.enter_position(entry_price=1.00, current_atr=0.02)
        self.assertAlmostEqual(init_stop, 1.00 - 2.5 * 0.02)

        # 价格上涨到 1.10，止损价应上移并锁定保本
        is_stopped, new_stop, _ = stop_mgr.update(current_high=1.10, current_close=1.08, current_atr=0.02)
        self.assertFalse(is_stopped)
        self.assertGreater(new_stop, init_stop)

        # 价格跌破止损线
        is_stopped, _, reason = stop_mgr.update(current_high=1.08, current_close=new_stop - 0.05, current_atr=0.02)
        self.assertTrue(is_stopped)
        self.assertEqual(reason, "trailing_stop_triggered")

    def test_macro_regime(self):
        """测试宏观状态机判定"""
        classifier = MacroRegimeClassifier()
        # 1. 强进攻状态测试
        bull_regime = classifier.evaluate_regime(cnh_change_pct=-0.1, up_down_ratio=2.0, broad_index_above_ma60=True)
        self.assertEqual(bull_regime["regime"], "STRONG_OFFENSIVE")
        self.assertEqual(bull_regime["max_position_cap"], 1.00)

        # 2. 避险状态测试
        bear_regime = classifier.evaluate_regime(cnh_change_pct=0.5, up_down_ratio=0.3, broad_index_above_ma60=False)
        self.assertEqual(bear_regime["regime"], "BEAR_LIQUIDITY_SHOCK")
        self.assertLessEqual(bear_regime["max_position_cap"], 0.20)

    def test_rotation_cross_section(self):
        """测试多资产截面打分与 Top 决策"""
        fake_universe = {
            "588180": self.sample_df,
            "159843": self.sample_df * 1.05,
            "511090": self.sample_df * 0.95
        }
        scored = score_universe_cross_section(fake_universe)
        self.assertFalse(scored.empty)
        self.assertIn("score", scored.columns)
        self.assertIn("rank", scored.columns)

        decision = select_top_etfs(scored, top_n=2)
        self.assertIn("regime", decision)
        self.assertIn("weights", decision)

    def test_single_asset_backtest(self):
        """测试单标的 NextGen 回测计算"""
        port, metrics = run_nextgen_single_backtest(self.sample_df)
        self.assertIn("total_return", metrics)
        self.assertIn("sharpe_ratio", metrics)
        self.assertIn("max_drawdown", metrics)


if __name__ == "__main__":
    unittest.main()
