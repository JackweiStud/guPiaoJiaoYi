"""门槛纯函数：只消费已发布真实序列，不插值。"""

from __future__ import annotations

import pandas as pd


def oil_gate(
    brent: pd.Series,
    threshold: float = 105.0,
    streak_days: int = 5,
) -> pd.Series:
    """
    门 1：Brent 连续 streak_days 个已发布交易日低于 threshold 时放行。
    在 brent 原生日历上计算；输入应为真实发布值（含 NaN 的点先丢掉）。
    """
    s = brent.dropna().astype(float).sort_index()
    below = s < threshold
    # 连续 True 计数
    groups = (~below).cumsum()
    streak = below.groupby(groups).cumsum()
    open_gate = streak >= streak_days
    return open_gate.astype(bool)


def rate_gate(
    dgs30: pd.Series,
    ma_window: int = 20,
    band: float = 0.0,
) -> pd.Series:
    """
    门 2：DGS30 ≤ MA20 * (1 + band) 时放行。
    band=0 为基准；±0.1 用于稳健性。MA 只在真实发布点上滚动。
    """
    s = dgs30.dropna().astype(float).sort_index()
    ma = s.rolling(window=ma_window, min_periods=ma_window).mean()
    thresh = ma * (1.0 + band)
    open_gate = s <= thresh
    # MA 未满窗口的前段为 False（信息不足，不放行）
    open_gate = open_gate.fillna(False)
    return open_gate.astype(bool)


def credit_gate(baa10y: pd.Series, threshold: float) -> pd.Series:
    """门 3：BAA10Y ≤ threshold 时放行。"""
    s = baa10y.dropna().astype(float).sort_index()
    return (s <= threshold).astype(bool)


def rate_absolute_gate(dgs30: pd.Series, threshold: float) -> pd.Series:
    """
    门 2（v2 绝对水平）：DGS30 ≤ threshold 时放行。
    threshold 为开测前写死的 τ_rate（如 2007+ 中位数）。
    """
    s = dgs30.dropna().astype(float).sort_index()
    return (s <= threshold).astype(bool)


def oas_gate(oas: pd.Series, threshold: float = 3.6) -> pd.Series:
    """交叉检查：真实 HY OAS ≤ threshold。"""
    s = oas.dropna().astype(float).sort_index()
    return (s <= threshold).astype(bool)


def combine_and_gates(*gates: pd.Series) -> pd.Series:
    """三门同时放行；索引对齐处取交集日期上的逐元素 AND。"""
    if not gates:
        raise ValueError("至少需要一个门")
    out = gates[0].astype(bool)
    for g in gates[1:]:
        aligned = pd.concat([out, g.astype(bool)], axis=1, join="inner")
        out = aligned.all(axis=1)
    return out.astype(bool)


def count_open_gates(*gates: pd.Series) -> pd.Series:
    """
    在共同索引（inner join）上统计开了几道门。
    注意：交易日历路径应先 asof 对齐再计数（见 backtest.build_*）。
    """
    if not gates:
        raise ValueError("至少需要一个门")
    df = pd.concat([g.astype(bool).astype(int) for g in gates], axis=1, join="inner")
    return df.sum(axis=1).astype(int)
