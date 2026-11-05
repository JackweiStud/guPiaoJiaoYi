"""分块 bootstrap：重采样的是真实日收益，不是合成价格。"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from gate_backtest.metrics import max_drawdown


def _block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """圆形分块 bootstrap 下标。"""
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=n_blocks)
    idx = np.concatenate([np.arange(s, s + block) % n for s in starts])[:n]
    return idx


def equity_from_returns(returns: np.ndarray, initial: float = 1.0) -> np.ndarray:
    return initial * np.cumprod(1.0 + returns)


def mdd_diff_block_bootstrap(
    strategy_returns: pd.Series,
    buyhold_returns: pd.Series,
    block: int = 20,
    n_boot: int = 1000,
    seed: int = 20251105,
    ci: float = 0.90,
) -> Tuple[float, float, float, np.ndarray]:
    """
    对 (策略收益, 一直持有收益) 同步分块重采样，
    估计 MDD_strategy - MDD_buyhold 的置信区间。
    注意：MDD 为负或接近负值；差异 = mdd_s - mdd_bh（若策略回撤更浅，差异为正）。

    CI 构造：对 bootstrap 复制做 **均值重定心（recentered percentile）** 后再取分位。
    原因：对收益分块重采样再 cumprod 得到的路径 MDD 差，相对全样本点估计常有
    一阶偏置；若直接对原始 bootstrap 分布取百分位，点估计可能落在名义 CI 之外
    （度量本身一致，并非符号搞反）。重定心后区间宽度不变，但以全样本点估计为中心。
    返回的第四项仍为**未重定心**的原始 bootstrap 差，便于诊断偏置。
    """
    idx = strategy_returns.index.intersection(buyhold_returns.index)
    rs = strategy_returns.reindex(idx).fillna(0.0).values.astype(float)
    rb = buyhold_returns.reindex(idx).fillna(0.0).values.astype(float)
    n = len(rs)
    rng = np.random.default_rng(seed)

    point_s = max_drawdown(pd.Series(equity_from_returns(rs)))
    point_b = max_drawdown(pd.Series(equity_from_returns(rb)))
    point = point_s - point_b

    diffs = np.empty(n_boot)
    for i in range(n_boot):
        take = _block_indices(n, block, rng)
        es = equity_from_returns(rs[take])
        eb = equity_from_returns(rb[take])
        diffs[i] = max_drawdown(pd.Series(es)) - max_drawdown(pd.Series(eb))

    # 重定心：diffs_centered = diffs - mean(diffs) + point
    centered = diffs - float(np.mean(diffs)) + point
    alpha = (1.0 - ci) / 2.0
    lo = float(np.quantile(centered, alpha))
    hi = float(np.quantile(centered, 1.0 - alpha))
    return point, lo, hi, diffs
