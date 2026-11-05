"""回测引擎：次日开盘成交、现金按 DGS3MO、信号至少滞后 1 日。"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from gate_backtest.constants import (
    AT_LEAST_GATES_SWITCH,
    FUND_REDEEM_TIERS,
    FUND_SUBSCRIBE_FEE,
    LISTED_COMMISSION,
    POSITION_SCALE_BY_GATES,
    SIGNAL_LAG_DAYS,
)
from gate_backtest.data import align_asof


def daily_cash_return_from_dgs3mo(dgs3mo_pct: pd.Series) -> pd.Series:
    """DGS3MO 为年化百分数；日收益 ≈ r/100/252。只用真实发布值。"""
    s = dgs3mo_pct.dropna().astype(float) / 100.0 / 252.0
    return s


def apply_signal_lag(gate_open: pd.Series, lag: int = SIGNAL_LAG_DAYS) -> pd.Series:
    """信号至少滞后 lag 个交易日（在目标交易日历上 shift）。"""
    return gate_open.astype(bool).shift(lag).fillna(False).astype(bool)


def apply_signal_lag_float(series: pd.Series, lag: int = SIGNAL_LAG_DAYS) -> pd.Series:
    """浮点仓位序列滞后 lag 个交易日；前段填 0。"""
    return series.astype(float).shift(lag).fillna(0.0)


def build_target_position(
    gate_native: pd.Series,
    trading_index: pd.DatetimeIndex,
    lag: int = SIGNAL_LAG_DAYS,
) -> Tuple[pd.Series, int, int]:
    """
    原生门信号 → 对齐到交易日历（沿用上一个已发布值）→ 滞后 lag 日 → 目标仓位 0/1。
    返回 (position, carry_days, max_carry_streak)。
    """
    aligned, carry_days, max_streak = align_asof(gate_native.astype(float), trading_index)
    # aligned 为 0/1/NaN；无历史时不持仓
    open_aligned = aligned.fillna(0.0) > 0.5
    pos = apply_signal_lag(open_aligned, lag=lag)
    return pos.astype(float), carry_days, max_streak


def _align_gates_to_calendar(
    gates_native: Sequence[pd.Series],
    trading_index: pd.DatetimeIndex,
) -> Tuple[list, int, int]:
    """各自 asof 对齐到交易日历；返回 bool 列表与沿用统计。"""
    aligned_bools = []
    total_carry = 0
    max_streak = 0
    for g in gates_native:
        aligned, cdays, mstreak = align_asof(g.astype(float), trading_index)
        aligned_bools.append(aligned.fillna(0.0) > 0.5)
        total_carry += cdays
        max_streak = max(max_streak, mstreak)
    return aligned_bools, total_carry, max_streak


def build_combo_position(
    gates_native: list,
    trading_index: pd.DatetimeIndex,
    lag: int = SIGNAL_LAG_DAYS,
) -> Tuple[pd.Series, int, int]:
    """
    多个原生日历门：各自 asof 对齐到交易日历后再 AND，然后滞后。
    禁止在原生日历上 inner-join（会丢掉非共同发布日的真实信息状态）。
    返回的 carry 统计取各门沿用天数之和与最长 streak 的最大者（报告用）。
    """
    aligned_bools, total_carry, max_streak = _align_gates_to_calendar(gates_native, trading_index)
    combo = aligned_bools[0]
    for b in aligned_bools[1:]:
        combo = combo & b
    pos = apply_signal_lag(combo, lag=lag)
    return pos.astype(float), total_carry, max_streak


def build_gate_count_series(
    gates_native: Sequence[pd.Series],
    trading_index: pd.DatetimeIndex,
) -> Tuple[pd.Series, int, int]:
    """对齐后逐日统计开了几道门（未滞后）。"""
    aligned_bools, total_carry, max_streak = _align_gates_to_calendar(gates_native, trading_index)
    count = sum(b.astype(int) for b in aligned_bools)
    return count.astype(int), total_carry, max_streak


def build_scaled_position(
    gates_native: Sequence[pd.Series],
    trading_index: pd.DatetimeIndex,
    scale_map: Optional[Mapping[int, float]] = None,
    lag: int = SIGNAL_LAG_DAYS,
) -> Tuple[pd.Series, int, int]:
    """
    按开了几道门定仓位：默认 3→100%、2→66%、1→33%、0→0%，再滞后 lag 日。
    """
    scale_map = dict(POSITION_SCALE_BY_GATES if scale_map is None else scale_map)
    count, total_carry, max_streak = build_gate_count_series(gates_native, trading_index)
    weights = count.map(lambda n: float(scale_map.get(int(n), 0.0))).astype(float)
    pos = apply_signal_lag_float(weights, lag=lag)
    return pos, total_carry, max_streak


def build_at_least_n_position(
    gates_native: Sequence[pd.Series],
    trading_index: pd.DatetimeIndex,
    n_min: int = AT_LEAST_GATES_SWITCH,
    lag: int = SIGNAL_LAG_DAYS,
) -> Tuple[pd.Series, int, int]:
    """至少 n_min 门放行 → 满仓，否则空仓；再滞后。"""
    count, total_carry, max_streak = build_gate_count_series(gates_native, trading_index)
    open_gate = count >= int(n_min)
    pos = apply_signal_lag(open_gate, lag=lag)
    return pos.astype(float), total_carry, max_streak


def run_listed_backtest(
    ohlcv: pd.DataFrame,
    target_pos: pd.Series,
    cash_daily: pd.Series,
    initial_capital: float = 100_000.0,
    commission: float = LISTED_COMMISSION,
) -> pd.DataFrame:
    """
    场内：目标仓位在决策日确定后，于**当日开盘**调仓（信号已含 ≥1 日滞后，
    等价于「t-1 收盘可知信号 → t 开盘成交」）。
    空仓现金按对齐后的 DGS3MO 日收益计息。

    若目标仓位含非 {0,1} 的分数仓位，自动走差额调仓路径
   （按 |Δ名义| 计单边手续费；未持仓现金每日计息）。
    """
    pos = target_pos.reindex(ohlcv.index).fillna(0.0).astype(float)
    uniq = set(np.round(pos.unique(), 6).tolist())
    if uniq.issubset({0.0, 1.0}):
        return _run_listed_binary(ohlcv, pos, cash_daily, initial_capital, commission)
    return run_listed_backtest_fractional(ohlcv, pos, cash_daily, initial_capital, commission)


def _run_listed_binary(
    ohlcv: pd.DataFrame,
    pos: pd.Series,
    cash_daily: pd.Series,
    initial_capital: float,
    commission: float,
) -> pd.DataFrame:
    """v1 兼容：0/1 全仓切换。"""
    idx = ohlcv.index
    open_px = ohlcv["Open"].astype(float)
    close_px = ohlcv["Close"].astype(float)
    cash_r, _, _ = align_asof(cash_daily, idx)
    cash_r = cash_r.fillna(0.0)

    equity = np.zeros(len(idx))
    holdings = np.zeros(len(idx))
    cash_arr = np.zeros(len(idx))
    shares = 0.0
    cash = initial_capital
    prev_pos = 0.0

    for i, dt in enumerate(idx):
        desired = float(pos.iloc[i])
        # 开盘调仓
        if desired != prev_pos:
            px = float(open_px.iloc[i])
            if not np.isfinite(px) or px <= 0:
                # 当日无真实开盘价：不交易（不编造价格）
                pass
            elif desired > prev_pos and shares == 0.0:
                # 全仓买入
                budget = cash
                cost_px = px * (1.0 + commission)
                sh = budget / cost_px
                shares = sh
                cash = 0.0
            elif desired < prev_pos and shares > 0.0:
                proceeds = shares * px * (1.0 - commission)
                cash = proceeds
                shares = 0.0
            prev_pos = desired if (
                (desired > 0 and shares > 0) or (desired == 0 and shares == 0)
            ) else prev_pos

        # 空仓计息（用上一日现金在当日计息；开盘卖出后的现金当日起息）
        if shares == 0.0 and cash > 0:
            cash *= 1.0 + float(cash_r.iloc[i])

        mark = float(close_px.iloc[i]) if np.isfinite(close_px.iloc[i]) else np.nan
        hold_val = shares * mark if shares > 0 and np.isfinite(mark) else 0.0
        cash_arr[i] = cash
        holdings[i] = hold_val
        equity[i] = cash + hold_val

    out = pd.DataFrame(
        {
            "cash": cash_arr,
            "holdings": holdings,
            "total": equity,
            "position": pos.values,
            "shares": [np.nan] * len(idx),  # 简化：不逐日存份额序列以外的细节
        },
        index=idx,
    )
    # 重算真实份额轨迹过长；用 position 与 total 足够算指标
    out["returns"] = out["total"].pct_change().fillna(0.0)
    return out


def run_listed_backtest_fractional(
    ohlcv: pd.DataFrame,
    target_pos: pd.Series,
    cash_daily: pd.Series,
    initial_capital: float = 100_000.0,
    commission: float = LISTED_COMMISSION,
    tol: float = 1e-9,
) -> pd.DataFrame:
    """
    分数仓位回测：按目标权重与当前权重差额调仓。

    实现细节（开测前写死）：
    1. 开盘以 open 价标记总权益 total = cash + shares * open；
    2. 目标股票名义 = desired_weight * total；
    3. 差额 Δ = 目标名义 − 当前名义；对 |Δ| 收取单边 commission 费用（从现金扣除）；
    4. 买入：cash 减少 |Δ|+fee，shares 增加 |Δ|/px；卖出对称；
    5. 未持仓现金每日按 DGS3MO 计息（调仓后的现金余额计息）。
    """
    idx = ohlcv.index
    open_px = ohlcv["Open"].astype(float)
    close_px = ohlcv["Close"].astype(float)
    pos = target_pos.reindex(idx).fillna(0.0).astype(float)
    cash_r, _, _ = align_asof(cash_daily, idx)
    cash_r = cash_r.fillna(0.0)

    equity = np.zeros(len(idx))
    holdings = np.zeros(len(idx))
    cash_arr = np.zeros(len(idx))
    shares = 0.0
    cash = float(initial_capital)

    for i, _dt in enumerate(idx):
        desired = float(np.clip(pos.iloc[i], 0.0, 1.0))
        px = float(open_px.iloc[i])
        if np.isfinite(px) and px > 0:
            total_open = cash + shares * px
            if total_open > 0:
                cur_val = shares * px
                target_val = desired * total_open
                delta = target_val - cur_val
                if abs(delta) > tol:
                    fee = abs(delta) * commission
                    if delta > 0:
                        # 买入：需支付 delta + fee；现金不足则按可得资金缩放
                        afford = max(cash - fee, 0.0)
                        buy_notional = min(delta, afford)
                        if buy_notional > tol and cash >= buy_notional + fee:
                            shares += buy_notional / px
                            cash -= buy_notional + fee
                        elif cash > fee + tol:
                            buy_notional = max(cash - fee, 0.0)
                            shares += buy_notional / px
                            cash -= buy_notional + fee
                    else:
                        sell_notional = min(-delta, shares * px)
                        if sell_notional > tol:
                            shares -= sell_notional / px
                            cash += sell_notional - fee
                            if shares < 0 and abs(shares) < 1e-12:
                                shares = 0.0

        if cash > 0:
            cash *= 1.0 + float(cash_r.iloc[i])

        mark = float(close_px.iloc[i]) if np.isfinite(close_px.iloc[i]) else np.nan
        hold_val = shares * mark if shares > 0 and np.isfinite(mark) else 0.0
        cash_arr[i] = cash
        holdings[i] = hold_val
        equity[i] = cash + hold_val

    out = pd.DataFrame(
        {
            "cash": cash_arr,
            "holdings": holdings,
            "total": equity,
            "position": pos.values,
            "shares": [np.nan] * len(idx),
        },
        index=idx,
    )
    out["returns"] = out["total"].pct_change().fillna(0.0)
    return out


def run_buy_and_hold(
    ohlcv: pd.DataFrame,
    cash_daily: pd.Series,
    initial_capital: float = 100_000.0,
    commission: float = LISTED_COMMISSION,
) -> pd.DataFrame:
    pos = pd.Series(1.0, index=ohlcv.index)
    # 首日开盘买入后一直持有
    return run_listed_backtest(ohlcv, pos, cash_daily, initial_capital, commission)


def run_monthly_dca(
    ohlcv: pd.DataFrame,
    cash_daily: pd.Series,
    initial_capital: float = 100_000.0,
    commission: float = LISTED_COMMISSION,
    monthly_cash: Optional[float] = None,
) -> pd.DataFrame:
    """
    每月定投：将初始资金按回测月份数均分，每月第一个交易日开盘买入；
    未投入现金按 DGS3MO 计息。已买入份额一直持有。
    """
    idx = ohlcv.index
    open_px = ohlcv["Open"].astype(float)
    close_px = ohlcv["Close"].astype(float)
    cash_r, _, _ = align_asof(cash_daily, idx)
    cash_r = cash_r.fillna(0.0)

    months = idx.to_period("M").unique()
    n_months = max(len(months), 1)
    contrib = monthly_cash if monthly_cash is not None else initial_capital / n_months

    # 每月首个交易日
    first_days = set(idx.to_series().groupby(idx.to_period("M")).first().tolist())

    cash = float(initial_capital)
    shares = 0.0
    rows = []
    contributed = 0.0

    for dt in idx:
        # 先计息（未投入部分）
        if cash > 0:
            cash *= 1.0 + float(cash_r.loc[dt])
        if dt in first_days and contributed < initial_capital - 1e-8:
            px = float(open_px.loc[dt])
            invest = min(contrib, cash)
            if np.isfinite(px) and px > 0 and invest > 0:
                cost_px = px * (1.0 + commission)
                sh = invest / cost_px
                shares += sh
                cash -= invest
                contributed += invest
        mark = float(close_px.loc[dt])
        hold = shares * mark if np.isfinite(mark) else 0.0
        rows.append({"cash": cash, "holdings": hold, "total": cash + hold, "position": 1.0 if shares > 0 else 0.0})

    out = pd.DataFrame(rows, index=idx)
    out["returns"] = out["total"].pct_change().fillna(0.0)
    return out


def fund_redeem_fee(holding_days: int) -> float:
    for lim, fee in FUND_REDEEM_TIERS:
        if holding_days < lim:
            return fee
    return 0.0


def run_fund_backtest(
    nav: pd.Series,
    target_pos: pd.Series,
    cash_daily: pd.Series,
    initial_capital: float = 100_000.0,
    daily_subscribe_limit: float = 10_000.0,
    subscribe_fee: float = FUND_SUBSCRIBE_FEE,
) -> pd.DataFrame:
    """
    场外参考：T+1 净值成交；每日申购额度 1 万元；
    申购费 0.16%；赎回按持有期分档。
    """
    idx = nav.dropna().index
    nav = nav.reindex(idx).astype(float)
    pos = target_pos.reindex(idx).fillna(0.0)
    cash_r, _, _ = align_asof(cash_daily, idx)
    cash_r = cash_r.fillna(0.0)

    cash = float(initial_capital)
    shares = 0.0
    lots = []  # (shares, buy_date_ordinal)
    rows = []
    date_list = list(idx)

    for i, dt in enumerate(date_list):
        desired = float(pos.iloc[i])
        # T+1：用当日净值作为成交价（信号已滞后；决策在前一日）
        px = float(nav.iloc[i])
        if shares == 0 and cash > 0:
            cash *= 1.0 + float(cash_r.iloc[i])

        if desired > 0.5 and cash > 0 and np.isfinite(px) and px > 0:
            invest = min(daily_subscribe_limit, cash)
            if invest > 0:
                fee = invest * subscribe_fee
                net = invest - fee
                sh = net / px
                shares += sh
                cash -= invest
                lots.append([sh, i])
        elif desired < 0.5 and shares > 0 and np.isfinite(px) and px > 0:
            # 按 FIFO 赎回全部分额
            proceeds = 0.0
            for sh, buy_i in lots:
                hold_days = i - buy_i
                fee_rate = fund_redeem_fee(hold_days)
                proceeds += sh * px * (1.0 - fee_rate)
            cash += proceeds
            shares = 0.0
            lots = []

        hold_val = shares * px if shares > 0 else 0.0
        rows.append(
            {
                "cash": cash,
                "holdings": hold_val,
                "total": cash + hold_val,
                "position": 1.0 if shares > 0 else 0.0,
            }
        )

    out = pd.DataFrame(rows, index=idx)
    out["returns"] = out["total"].pct_change().fillna(0.0)
    return out


def slice_portfolio(pf: pd.DataFrame, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    s = pf.loc[start:end].copy()
    if s.empty:
        return s
    # 分段净值归一，便于分段年化；指标用分段内相对变化
    return s
