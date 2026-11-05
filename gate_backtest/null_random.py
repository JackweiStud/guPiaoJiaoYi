"""随机择时零假设：随机的是信号路径，不是价格。"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from gate_backtest.backtest import run_listed_backtest
from gate_backtest.metrics import max_drawdown


def _generate_one_path(
    n: int,
    hold_share: float,
    avg_len: float,
    rng: np.random.Generator,
    on_level: float = 1.0,
) -> np.ndarray:
    """
    生成持仓路径，使「仓位>0 的天数占比」与平均持仓长度接近目标。
    on 段仓位为 on_level（默认 1.0；分数仓位时取平均暴露/持仓占比以匹配平均暴露）。
    用几何分布长度的 on/off 交替块。
    """
    avg_len = max(avg_len, 1.0)
    # off 段期望长度由 hold_share 反推：hold = on/(on+off) => off = on*(1-h)/h
    if hold_share <= 0:
        return np.zeros(n)
    if hold_share >= 1 and abs(on_level - 1.0) < 1e-12:
        return np.ones(n)
    mean_on = avg_len
    mean_off = mean_on * (1.0 - min(hold_share, 0.999999)) / max(hold_share, 1e-12)
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
        path[i:j] = on_level if state == 1 else 0.0
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
    mean_exposure: Optional[float] = None,
) -> Tuple[np.ndarray, float]:
    """
    返回每条随机信号路径的最大回撤数组，以及第 5 百分位。
    价格与现金收益均为真实序列；仅信号随机。

    若提供 mean_exposure（平均暴露 = mean(position)），则 on 段仓位 =
    mean_exposure / hold_share，以同时匹配平均暴露与平均持仓长度。
    """
    rng = np.random.default_rng(seed)
    n = len(ohlcv)
    if mean_exposure is None or hold_share <= 0:
        on_level = 1.0
    else:
        on_level = float(np.clip(mean_exposure / max(hold_share, 1e-12), 0.0, 1.0))
    mdds = np.empty(n_paths)
    for k in range(n_paths):
        path = _generate_one_path(n, hold_share, avg_len, rng, on_level=on_level)
        pos = pd.Series(path, index=ohlcv.index)
        pf = run_listed_backtest(ohlcv, pos, cash_daily, initial_capital=initial_capital)
        mdds[k] = max_drawdown(pf["total"])
    p5 = float(np.quantile(mdds, 0.05))
    return mdds, p5
