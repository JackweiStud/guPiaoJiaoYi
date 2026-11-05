"""绩效指标与踏空成本。"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min()) if len(dd) else 0.0


def drawdown_duration_days(equity: pd.Series) -> int:
    """最长回撤持续交易日数（从创新高后跌破到再创新高）。"""
    if equity.empty:
        return 0
    peak = equity.cummax()
    in_dd = equity < peak
    max_dur = 0
    cur = 0
    for flag in in_dd.tolist():
        if flag:
            cur += 1
            max_dur = max(max_dur, cur)
        else:
            cur = 0
    return int(max_dur)


def annualized_return(equity: pd.Series, periods_per_year: float = 252.0) -> float:
    if len(equity) < 2:
        return 0.0
    total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    n = len(equity)
    return float((1.0 + total) ** (periods_per_year / n) - 1.0)


def annualized_vol(returns: pd.Series, periods_per_year: float = 252.0) -> float:
    r = returns.dropna()
    if r.std(ddof=0) == 0 or len(r) < 2:
        return 0.0
    return float(r.std(ddof=0) * np.sqrt(periods_per_year))


def calmar(ann_ret: float, mdd: float) -> float:
    if mdd == 0:
        return float("nan")
    return float(ann_ret / abs(mdd))


def summarize_equity(
    equity: pd.Series,
    position: pd.Series,
    returns: Optional[pd.Series] = None,
) -> Dict[str, float]:
    if returns is None:
        returns = equity.pct_change().fillna(0.0)
    mdd = max_drawdown(equity)
    ann = annualized_return(equity)
    vol = annualized_vol(returns)
    pos = position.reindex(equity.index).fillna(0.0)
    hold_share = float((pos > 0).mean()) if len(pos) else 0.0
    exposure_share = float(pos.mean()) if len(pos) else 0.0
    # 换手：持仓状态变化次数
    turns = int((pos.fillna(0).diff().abs() > 0).sum())
    return {
        "max_drawdown": mdd,
        "drawdown_duration_days": float(drawdown_duration_days(equity)),
        "ann_return": ann,
        "ann_vol": vol,
        "calmar": calmar(ann, mdd),
        "n_turnovers": float(turns),
        "hold_day_share": hold_share,
        "exposure_share": exposure_share,
    }


def missed_opportunity_cost(
    asset_returns: pd.Series,
    cash_returns: pd.Series,
    gate_open: pd.Series,
) -> float:
    """
    踏空成本 = 门关闭期间一直持有的收益 − 现金收益。
    用累乘：prod(1+r_asset|closed) - prod(1+r_cash|closed)，再减 1 对齐到收益口径差。
    返回绝对收益差（小数）。
    """
    idx = asset_returns.index.intersection(cash_returns.index).intersection(gate_open.index)
    closed = ~gate_open.reindex(idx).fillna(False).astype(bool)
    if closed.sum() == 0:
        return 0.0
    a = asset_returns.reindex(idx).fillna(0.0)[closed]
    c = cash_returns.reindex(idx).fillna(0.0)[closed]
    asset_cum = float((1.0 + a).prod() - 1.0)
    cash_cum = float((1.0 + c).prod() - 1.0)
    return asset_cum - cash_cum


def avg_holding_length(position: pd.Series) -> float:
    """平均连续持仓长度（交易日）。"""
    pos = (position.fillna(0) > 0).astype(int)
    if pos.sum() == 0:
        return 0.0
    changes = pos.diff().fillna(pos.iloc[0]).ne(0)
    group_id = changes.cumsum()
    lengths = pos.groupby(group_id).sum()
    hold_lengths = lengths[lengths > 0]
    return float(hold_lengths.mean()) if len(hold_lengths) else 0.0
