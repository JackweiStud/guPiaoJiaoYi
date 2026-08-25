"""RSRS (阻力支撑相对强度) 因子计算模块

数学原理:
    每日最高价 High 和最低价 Low 之间进行 OLS 线性回归:
        High_t = alpha + beta * Low_t + epsilon_t
    1. 计算过去 N 日的回归斜率 beta 和决定系数 R^2
    2. 对 beta 在过去 M 日内进行 Z-score 标准化:
        Z(beta) = (beta - mean(beta_M)) / std(beta_M)
    3. 结合拟合优度修正:
        RSRS_Score = Z(beta) * R^2
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any, Optional


def _rolling_ols_slope_and_r2(
    high: np.ndarray,
    low: np.ndarray,
    window: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    使用滑动窗口高效计算 OLS 回归斜率 beta 与拟合优度 R^2.
    y = High, x = Low
    beta = Cov(x, y) / Var(x)
    R^2 = Cov(x, y)^2 / (Var(x) * Var(y))
    """
    n = len(high)
    slopes = np.full(n, np.nan, dtype=np.float64)
    r2_scores = np.full(n, np.nan, dtype=np.float64)

    if n < window:
        return slopes, r2_scores

    # 构建滑动窗口矩阵
    for i in range(window - 1, n):
        y = high[i - window + 1 : i + 1]
        x = low[i - window + 1 : i + 1]

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        x_diff = x - x_mean
        y_diff = y - y_mean

        var_x = np.sum(x_diff ** 2)
        var_y = np.sum(y_diff ** 2)
        cov_xy = np.sum(x_diff * y_diff)

        if var_x > 1e-12:
            beta = cov_xy / var_x
            slopes[i] = beta
            if var_y > 1e-12:
                r2 = (cov_xy ** 2) / (var_x * var_y)
                r2_scores[i] = np.clip(r2, 0.0, 1.0)
            else:
                r2_scores[i] = 0.0
        else:
            slopes[i] = 1.0
            r2_scores[i] = 0.0

    return slopes, r2_scores


def calc_rsrs_series(
    df: pd.DataFrame,
    n_window: int = 18,
    m_window: int = 250,
    high_col: str = "HighValue",
    low_col: str = "LowValue",
) -> pd.DataFrame:
    """
    计算完整的 RSRS 因子时间序列数据框.
    
    参数:
        df: 包含 HighValue 和 LowValue 的行情 DataFrame (以 DateTime 为索引或包含该列)
        n_window: OLS 回归的短期滚动窗口 (推荐 16 ~ 18 日)
        m_window: Z-Score 标准化的长期滚动窗口 (推荐 200 ~ 600 日)
        high_col: 最高价列名
        low_col: 最低价列名

    返回:
        包含以下列的 DataFrame:
        - rsrs_slope: OLS 回归斜率 beta
        - rsrs_r2: 回归决定系数 R^2
        - rsrs_zscore: 标准化后的 Z(beta)
        - rsrs_score: 修正后的 RSRS 分数 = Z(beta) * R^2
        - rsrs_skew_score: 右偏修正分数 = Z(beta) * R^2 * beta
    """
    if high_col not in df.columns or low_col not in df.columns:
        raise ValueError(f"DataFrame 必须包含 '{high_col}' 与 '{low_col}' 列")

    high = df[high_col].to_numpy(dtype=np.float64)
    low = df[low_col].to_numpy(dtype=np.float64)

    slopes, r2_scores = _rolling_ols_slope_and_r2(high, low, window=n_window)

    slope_series = pd.Series(slopes, index=df.index)
    r2_series = pd.Series(r2_scores, index=df.index)

    # 长期滑动窗口标准化
    rolling_mean = slope_series.rolling(window=m_window, min_periods=max(n_window, 30)).mean()
    rolling_std = slope_series.rolling(window=m_window, min_periods=max(n_window, 30)).std()

    # 避免除以零
    zscore = (slope_series - rolling_mean) / rolling_std.replace(0, np.nan)
    rsrs_score = zscore * r2_series
    rsrs_skew_score = rsrs_score * slope_series

    result_df = pd.DataFrame(
        {
            "rsrs_slope": slope_series,
            "rsrs_r2": r2_series,
            "rsrs_zscore": zscore,
            "rsrs_score": rsrs_score,
            "rsrs_skew_score": rsrs_skew_score,
        },
        index=df.index,
    )

    return result_df


def calc_rsrs(
    df: pd.DataFrame,
    n_window: int = 18,
    m_window: int = 250,
    buy_threshold: float = 0.7,
    sell_threshold: float = -0.7,
    high_col: str = "HighValue",
    low_col: str = "LowValue",
) -> Dict[str, Any]:
    """
    计算最新一期 RSRS 因子指标与交易倾向.
    """
    rsrs_df = calc_rsrs_series(
        df,
        n_window=n_window,
        m_window=m_window,
        high_col=high_col,
        low_col=low_col
    )

    if rsrs_df.empty:
        return {
            "score": 0.0,
            "zscore": 0.0,
            "slope": 1.0,
            "r2": 0.0,
            "signal": "HOLD",
            "strength": "neutral"
        }

    latest = rsrs_df.iloc[-1]
    score = float(latest["rsrs_score"]) if not pd.isna(latest["rsrs_score"]) else 0.0
    zscore = float(latest["rsrs_zscore"]) if not pd.isna(latest["rsrs_zscore"]) else 0.0
    slope = float(latest["rsrs_slope"]) if not pd.isna(latest["rsrs_slope"]) else 1.0
    r2 = float(latest["rsrs_r2"]) if not pd.isna(latest["rsrs_r2"]) else 0.0

    if score > buy_threshold:
        signal = "BUY"
        strength = "strong_bullish" if score > 1.2 else "bullish"
    elif score < sell_threshold:
        signal = "SELL"
        strength = "strong_bearish" if score < -1.2 else "bearish"
    else:
        signal = "HOLD"
        strength = "neutral"

    return {
        "score": round(score, 4),
        "zscore": round(zscore, 4),
        "slope": round(slope, 4),
        "r2": round(r2, 4),
        "signal": signal,
        "strength": strength,
    }
