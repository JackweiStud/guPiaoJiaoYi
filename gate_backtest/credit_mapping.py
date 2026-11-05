"""BAA10Y ← OAS 一次性映射（预登记规定，只算一次后写死）。"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from gate_backtest.constants import CREDIT_OAS_TARGET, CREDIT_OVERLAP_START


def compute_baa_threshold_from_oas(
    oas: pd.Series,
    baa: pd.Series,
    overlap_start: str = CREDIT_OVERLAP_START,
    oas_target: float = CREDIT_OAS_TARGET,
) -> Dict[str, float]:
    """
    在重叠期内：
    1) 计算 oas_target 在 OAS 经验分布中的分位数 q（rank 法：严格小于 + 0.5*相等）/n
    2) 取 BAA10Y 同重叠期第 q 分位数为 τ
    只使用真实重叠日（两侧均有发布的日期），不做插值。
    """
    start = pd.Timestamp(overlap_start)
    o = oas.dropna().astype(float)
    b = baa.dropna().astype(float)
    o = o.loc[o.index >= start]
    b = b.loc[b.index >= start]
    idx = o.index.intersection(b.index)
    if len(idx) < 10:
        raise RuntimeError(f"重叠期有效样本过少: {len(idx)}")
    o = o.loc[idx]
    b = b.loc[idx]
    vals = o.values.astype(float)
    n = len(vals)
    less = float(np.sum(vals < oas_target))
    eq = float(np.sum(vals == oas_target))
    q = (less + 0.5 * eq) / n
    tau = float(np.quantile(b.values.astype(float), q, method="linear"))
    return {
        "q": float(q),
        "tau": tau,
        "n_overlap": float(n),
        "overlap_start": str(idx.min().date()),
        "overlap_end": str(idx.max().date()),
        "oas_target": float(oas_target),
    }
