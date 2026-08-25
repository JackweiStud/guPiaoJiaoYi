"""ATR 动态移动追踪止盈止损与仓位管理模块

核心功能:
    1. ATR 动态移动追踪止损 (Trailing Stop):
       买入后随价格创新高单调上移止损线:
       StopPrice = max(PrevStop, HighestPrice - multiplier * ATR)
       在保全本金的同时锁定大部分浮盈。

    2. 波动率平价仓位估算 (Volatility-Targeted Position Sizing):
       根据各标的 ATR% 波动率反比分配仓位权重。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from quant.factors.volatility import calc_atr


class ATRTrailingStop:
    """
    ATR 移动追踪止损管理器
    """
    def __init__(self, atr_multiplier: float = 2.5, min_profit_protect_pct: float = 0.05):
        """
        :param atr_multiplier: ATR 止损倍数 (默认 2.5)
        :param min_profit_protect_pct: 当浮盈超过该比例 (如 5%) 时，强行将止损线提至成本价以上保本
        """
        self.atr_multiplier = atr_multiplier
        self.min_profit_protect_pct = min_profit_protect_pct
        self.entry_price: Optional[float] = None
        self.highest_price: Optional[float] = None
        self.current_stop_price: Optional[float] = None

    def reset(self):
        self.entry_price = None
        self.highest_price = None
        self.current_stop_price = None

    def enter_position(self, entry_price: float, current_atr: float) -> float:
        """
        建立多头仓位并初始化初始止损位
        """
        self.entry_price = float(entry_price)
        self.highest_price = float(entry_price)
        self.current_stop_price = float(entry_price - self.atr_multiplier * current_atr)
        return self.current_stop_price

    def update(self, current_high: float, current_close: float, current_atr: float) -> Tuple[bool, float, str]:
        """
        更新每日止损价并判定是否触发平仓.
        
        :return: (is_stopped_out: bool, stop_price: float, reason: str)
        """
        if self.entry_price is None or self.current_stop_price is None:
            return False, 0.0, "no_position"

        # 更新持仓以来的最高价
        if current_high > self.highest_price:
            self.highest_price = float(current_high)

        # 动态计算新的候选止损价
        candidate_stop = self.highest_price - self.atr_multiplier * current_atr

        # 保本线提升: 浮盈超过设定比例时，止损位不得低于保本线 (成本价 + 0.3% 手续费缓冲)
        unrealized_peak_gain = (self.highest_price - self.entry_price) / self.entry_price
        if unrealized_peak_gain >= self.min_profit_protect_pct:
            breakeven_stop = self.entry_price * 1.003
            candidate_stop = max(candidate_stop, breakeven_stop)

        # 止损线单调递增 (只能上移，不能下移)
        self.current_stop_price = max(self.current_stop_price, candidate_stop)

        # 判定是否触发平仓 (跌破止损位)
        if current_close < self.current_stop_price:
            return True, self.current_stop_price, "trailing_stop_triggered"

        return False, self.current_stop_price, "holding"


def calc_trailing_stop_series(
    df: pd.DataFrame,
    entry_indices: pd.Series,
    atr_period: int = 14,
    atr_multiplier: float = 2.5,
    high_col: str = "HighValue",
    low_col: str = "LowValue",
    close_col: str = "CloseValue",
) -> pd.DataFrame:
    """
    计算完整的历史持仓止损线轨迹数据框 (用于回测与图表绘制).
    """
    atr = calc_atr(df, period=atr_period, high_col=high_col, low_col=low_col, close_col=close_col)
    
    n = len(df)
    stop_prices = np.full(n, np.nan, dtype=np.float64)
    holding_flags = np.zeros(n, dtype=int)

    manager = ATRTrailingStop(atr_multiplier=atr_multiplier)
    is_in_pos = False

    highs = df[high_col].to_numpy(dtype=np.float64)
    closes = df[close_col].to_numpy(dtype=np.float64)
    atrs = atr.to_numpy(dtype=np.float64)
    entries = entry_indices.to_numpy()

    for i in range(n):
        if not is_in_pos:
            if entries[i] == 1:
                cur_atr = atrs[i] if not np.isnan(atrs[i]) else closes[i] * 0.02
                stop_prices[i] = manager.enter_position(closes[i], cur_atr)
                is_in_pos = True
                holding_flags[i] = 1
        else:
            cur_atr = atrs[i] if not np.isnan(atrs[i]) else closes[i] * 0.02
            is_stopped, stop_p, _ = manager.update(highs[i], closes[i], cur_atr)
            stop_prices[i] = stop_p
            if is_stopped or entries[i] == -1:
                is_in_pos = False
                manager.reset()
                holding_flags[i] = 0
            else:
                holding_flags[i] = 1

    return pd.DataFrame({
        "trailing_stop": pd.Series(stop_prices, index=df.index),
        "in_position": pd.Series(holding_flags, index=df.index)
    })


def calc_volatility_position_size(
    atr_pct_series: Dict[str, float],
    target_portfolio_vol: float = 0.015,
    max_weight_per_asset: float = 0.5
) -> Dict[str, float]:
    """
    根据波动率反比分配仓位 (Risk Parity Weighting).
    
    :param atr_pct_series: 各资产的 ATR% (如 {'588180': 0.025, '159843': 0.012})
    :param target_portfolio_vol: 目标单资产风险预算
    :param max_weight_per_asset: 单标的最大允许仓位上限 (例如 50%)
    :return: 归一化后的仓位权重字典
    """
    if not atr_pct_series:
        return {}

    raw_weights = {}
    for symbol, atr_pct in atr_pct_series.items():
        if atr_pct > 1e-4:
            raw_weights[symbol] = min(max_weight_per_asset, target_portfolio_vol / atr_pct)
        else:
            raw_weights[symbol] = max_weight_per_asset

    total_w = sum(raw_weights.values())
    if total_w > 1.0:
        # 归一化不超过 100%
        return {sym: round(w / total_w, 4) for sym, w in raw_weights.items()}
    return {sym: round(w, 4) for sym, w in raw_weights.items()}
