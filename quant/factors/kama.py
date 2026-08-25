"""KAMA (考夫曼自适应移动平均线) 因子计算模块

数学原理:
    1. 计算价格效率比 (Efficiency Ratio, ER):
       Change = |Price_t - Price_{t-n}|
       Volatility = sum_{i=1}^n |Price_i - Price_{i-1}|
       ER = Change / Volatility  (取值范围 0 ~ 1)
       * 单边趋势市 ER -> 1 (高效率，少噪声)
       * 箱体震荡市 ER -> 0 (低效率，充满随机噪声)

    2. 计算平滑常数 (Smoothing Constant, SC):
       Fast_SC = 2 / (fast_period + 1)   (默认 fast=2)
       Slow_SC = 2 / (slow_period + 1)   (默认 slow=30)
       SC = (ER * (Fast_SC - Slow_SC) + Slow_SC) ^ 2

    3. 递推计算 KAMA:
       KAMA_t = KAMA_{t-1} + SC * (Price_t - KAMA_{t-1})
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, Union


def calc_efficiency_ratio(
    prices: pd.Series,
    period: int = 10
) -> pd.Series:
    """
    计算效率比 (Efficiency Ratio, ER).
    """
    change = (prices - prices.shift(period)).abs()
    volatility = (prices - prices.shift(1)).abs().rolling(window=period, min_periods=period).sum()
    
    # 避免除以零
    er = change / volatility.replace(0, np.nan)
    return er.fillna(0.0).clip(lower=0.0, upper=1.0)


def calc_kama(
    prices: Union[pd.Series, pd.DataFrame],
    er_period: int = 10,
    fast_period: int = 2,
    slow_period: int = 30,
    price_col: str = "CloseValue"
) -> pd.Series:
    """
    计算 KAMA 自适应均线时间序列.

    参数:
        prices: 价格 Series 或包含 price_col 的 DataFrame
        er_period: 效率比回看周期 (默认 10)
        fast_period: 快速平滑周期 (默认 2)
        slow_period: 慢速平滑周期 (默认 30)
        price_col: 若传入 DataFrame，指定收盘价列名

    返回:
        pd.Series: KAMA 均线序列
    """
    if isinstance(prices, pd.DataFrame):
        if price_col not in prices.columns:
            raise ValueError(f"DataFrame 缺少 '{price_col}' 列")
        p = prices[price_col].astype(float)
    else:
        p = prices.astype(float)

    n = len(p)
    if n == 0:
        return pd.Series(dtype=np.float64)

    fast_sc = 2.0 / (fast_period + 1.0)
    slow_sc = 2.0 / (slow_period + 1.0)

    er = calc_efficiency_ratio(p, period=er_period).to_numpy()
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    price_arr = p.to_numpy()
    kama = np.full(n, np.nan, dtype=np.float64)

    # 初始值设为第一个有效窗口后的均值或当期价格
    start_idx = er_period
    if start_idx < n:
        kama[start_idx] = price_arr[start_idx]
        for i in range(start_idx + 1, n):
            if np.isnan(kama[i - 1]):
                kama[i - 1] = price_arr[i - 1]
            kama[i] = kama[i - 1] + sc[i] * (price_arr[i] - kama[i - 1])

    return pd.Series(kama, index=p.index, name="KAMA")


def calc_kama_signals(
    df: pd.DataFrame,
    er_period: int = 10,
    fast_period: int = 2,
    slow_period: int = 30,
    filter_bandwidth: float = 0.005,
    price_col: str = "CloseValue"
) -> pd.DataFrame:
    """
    基于 KAMA 的趋势与自适应突破信号生成.
    
    参数:
        df: 行情数据 DataFrame
        filter_bandwidth: 过滤带宽度 (例如 0.005 表示突破 KAMA 0.5% 确认)
    
    返回:
        包含 kama, kama_diff, kama_trend, kama_er 的 DataFrame
    """
    p = df[price_col].astype(float)
    kama = calc_kama(p, er_period=er_period, fast_period=fast_period, slow_period=slow_period)
    er = calc_efficiency_ratio(p, period=er_period)

    # KAMA 自身的斜率变化 (二阶导数/拐头)
    kama_diff = kama.diff()
    
    # 价格相对 KAMA 的偏离度
    price_vs_kama = (p - kama) / kama

    # 状态判定: 1=看多, -1=看空, 0=震荡
    kama_trend = pd.Series(0, index=df.index, dtype=int)
    kama_trend[(price_vs_kama > filter_bandwidth) & (kama_diff > 0)] = 1
    kama_trend[(price_vs_kama < -filter_bandwidth) & (kama_diff < 0)] = -1

    return pd.DataFrame({
        "kama": kama,
        "kama_diff": kama_diff,
        "kama_er": er,
        "price_vs_kama": price_vs_kama,
        "kama_trend": kama_trend
    }, index=df.index)
