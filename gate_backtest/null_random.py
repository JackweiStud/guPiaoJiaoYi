"""随机择时零假设：随机的是信号路径，不是价格。"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from gate_backtest.backtest import run_listed_backtest
from gate_backtest.metrics import avg_holding_length, max_drawdown


def _generate_one_path(
    n: int,
    hold_share: float,
    avg_len: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    生成 0/1 持仓路径，使持仓天数占比与平均持仓长度接近目标。
    用几何分布长度的 on/off 交替块。
    """
    avg_len = max(avg_len, 1.0)
    # off 段期望长度由 hold_share 反推：hold = on/(on+off) => off = on*(1-h)/h
    if hold_share <= 0:
        return np.zeros(n)
    if hold_share >= 1:
        return np.ones(n)
    mean_on = avg_len
    mean_off = mean_on * (1.0 - hold_share) / hold_share
    mean_off = max(mean_off, 1.0)

    path = np.zeros(n, dtype=float)
    i = 0
    state = 1 if rng.random() < hold_share else 0
    while i < n:
        if state == 1:
            length = max(1, int(rng.geometric(1.0 / mean_on)))
        else:
            length = max(1, int(rng.geometric(1.0 / mean_off)))
        j = min(n, i + length)
        path[i:j] = state
        i = j
        state = 1 - state
    return path


def random_timing_mdds(
    ohlcv: pd.DataFrame,
    cash_daily: pd.Series,
    hold_share: float,
    avg_len: float,
    n_paths: int = 1000,
    seed: int = 20251105,
    initial_capital: float = 100_000.0,
) -> Tuple[np.ndarray, float]:
    """
    返回每条随机信号路径的最大回撤数组，以及第 5 百分位。
    价格与现金收益均为真实序列；仅信号随机。
    """
    rng = np.random.default_rng(seed)
    n = len(ohlcv)
    mdds = np.empty(n_paths)
    for k in range(n_paths):
        path = _generate_one_path(n, hold_share, avg_len, rng)
        pos = pd.Series(path, index=ohlcv.index)
        pf = run_listed_backtest(ohlcv, pos, cash_daily, initial_capital=initial_capital)
        mdds[k] = max_drawdown(pf["total"])
    p5 = float(np.quantile(mdds, 0.05))
    return mdds, p5
