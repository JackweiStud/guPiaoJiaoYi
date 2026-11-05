"""BAA10Y ← OAS 一次性映射（预登记规定，只算一次后写死）。"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from gate_backtest.constants import CREDIT_OAS_TARGET, CREDIT_OVERLAP_START, SAMPLE_START


def _rank_quantile_of_target(vals: np.ndarray, target: float) -> float:
    """rank 法：q = (#{x<target} + 0.5#{x=target}) / n。"""
    n = len(vals)
    if n == 0:
        raise RuntimeError("空样本无法计算分位")
    less = float(np.sum(vals < target))
    eq = float(np.sum(vals == target))
    return (less + 0.5 * eq) / n


def compute_baa_threshold_from_oas(
    oas: pd.Series,
    baa: pd.Series,
    overlap_start: str = CREDIT_OVERLAP_START,
    oas_target: float = CREDIT_OAS_TARGET,
) -> Dict[str, float]:
    """
    v1：在重叠期内：
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
    q = _rank_quantile_of_target(vals, oas_target)
    tau = float(np.quantile(b.values.astype(float), q, method="linear"))
    return {
        "q": float(q),
        "tau": tau,
        "n_overlap": float(len(vals)),
        "overlap_start": str(idx.min().date()),
        "overlap_end": str(idx.max().date()),
        "oas_target": float(oas_target),
    }


def compute_baa_threshold_v2(
    oas: pd.Series,
    baa: pd.Series,
    baa_sample_start: str = SAMPLE_START,
    oas_target: float = CREDIT_OAS_TARGET,
) -> Dict[str, float]:
    """
    v2：在 HY OAS **可得期**算 q，再取 2007+（默认 SAMPLE_START）至今 BAA10Y 同 q 分位为 τ。
    不做插值；两侧各自用真实发布值。
    """
    o = oas.dropna().astype(float).sort_index()
    if len(o) < 10:
        raise RuntimeError(f"OAS 可得期有效样本过少: {len(o)}")
    q = _rank_quantile_of_target(o.values.astype(float), oas_target)
    start = pd.Timestamp(baa_sample_start)
    b = baa.dropna().astype(float).sort_index()
    b = b.loc[b.index >= start]
    if len(b) < 10:
        raise RuntimeError(f"BAA 样本有效过少: {len(b)}")
    tau = float(np.quantile(b.values.astype(float), q, method="linear"))
    return {
        "q": float(q),
        "tau": tau,
        "n_oas": float(len(o)),
        "oas_start": str(o.index.min().date()),
        "oas_end": str(o.index.max().date()),
        "n_baa": float(len(b)),
        "baa_start": str(b.index.min().date()),
        "baa_end": str(b.index.max().date()),
        "oas_target": float(oas_target),
    }


def compute_rate_absolute_threshold(
    dgs30: pd.Series,
    sample_start: str = SAMPLE_START,
    percentile: float = 0.50,
) -> Dict[str, float]:
    """v2：2007+ DGS30 指定分位（默认中位数）作为 τ_rate。"""
    start = pd.Timestamp(sample_start)
    s = dgs30.dropna().astype(float).sort_index()
    s = s.loc[s.index >= start]
    if len(s) < 10:
        raise RuntimeError(f"DGS30 样本有效过少: {len(s)}")
    tau = float(np.quantile(s.values.astype(float), percentile, method="linear"))
    return {
        "tau_rate": tau,
        "percentile": float(percentile),
        "n": float(len(s)),
        "start": str(s.index.min().date()),
        "end": str(s.index.max().date()),
    }
