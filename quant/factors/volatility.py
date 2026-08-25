"""真实波幅 (ATR) 与唐奇安通道 (Donchian Channel) 因子计算模块

用于动态风险调整、波动率过滤与通道突破策略。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, Optional


def calc_true_range(
    df: pd.DataFrame,
    high_col: str = "HighValue",
    low_col: str = "LowValue",
    close_col: str = "CloseValue"
) -> pd.Series:
    """
    计算真实波幅 (True Range, TR):
        TR = max(High - Low, |High - PrevClose|, |Low - PrevClose|)
    """
    high = df[high_col].astype(float)
    low = df[low_col].astype(float)
    close = df[close_col].astype(float)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr


def calc_atr(
    df: pd.DataFrame,
    period: int = 14,
    smoothing: str = "rma",  # "rma" (Wilder) 或 "sma"
    high_col: str = "HighValue",
    low_col: str = "LowValue",
    close_col: str = "CloseValue"
) -> pd.Series:
    """
    计算 ATR (Average True Range).
    """
    tr = calc_true_range(df, high_col=high_col, low_col=low_col, close_col=close_col)
    
    if smoothing == "rma":
        # Wilder's Smoothing (EMA with alpha = 1 / period)
        atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    else:
        atr = tr.rolling(window=period, min_periods=period).mean()

    return atr


def calc_donchian_channels(
    df: pd.DataFrame,
    period: int = 20,
    high_col: str = "HighValue",
    low_col: str = "LowValue"
) -> pd.DataFrame:
    """
    计算唐奇安通道 (Donchian Channels):
        Upper = 过去 N 日最高价 (不含当日)
        Lower = 过去 N 日最低价 (不含当日)
        Mid = (Upper + Lower) / 2
    """
    high = df[high_col].astype(float)
    low = df[low_col].astype(float)

    # shift(1) 避免未来数据窥探 (Look-ahead bias)
    upper = high.shift(1).rolling(window=period, min_periods=period).max()
    lower = low.shift(1).rolling(window=period, min_periods=period).min()
    mid = (upper + lower) / 2.0

    return pd.DataFrame({
        "donchian_upper": upper,
        "donchian_lower": lower,
        "donchian_mid": mid
    }, index=df.index)


def calc_risk_adjusted_momentum(
    df: pd.DataFrame,
    return_window: int = 20,
    atr_window: int = 20,
    close_col: str = "CloseValue"
) -> pd.Series:
    """
    计算风险调整后的动量收益率指标 (Sharpe-like Momentum):
        Risk_Adj_Mom = (Close_t / Close_{t-N} - 1) / (ATR_N / Close_t)
    """
    close = df[close_col].astype(float)
    ret = close.pct_change(return_window)
    atr = calc_atr(df, period=atr_window, close_col=close_col)
    atr_pct = atr / close

    risk_adj_mom = ret / atr_pct.replace(0, np.nan)
    return risk_adj_mom.fillna(0.0)
