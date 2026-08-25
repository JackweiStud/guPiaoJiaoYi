"""多资产 ETF 截面动量轮动组合回测引擎 (Portfolio Backtester)

模拟全生命周期截面动量轮动投资组合表现:
    - 每日/定期截面打分与 Top 2 轮动
    - 市场系统性走弱时自动切换国债 ETF 避险
    - 计算换手率、手续费扣除、组合净值曲线与多维度绩效
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from quant.rotation.universe import load_universe_data, DEFAULT_ETF_UNIVERSE
from quant.rotation.scorer import score_universe_cross_section
from quant.rotation.engine import select_top_etfs
from quant.backtest.single_asset import calculate_metrics


def align_universe_price_data(
    universe_dfs: Dict[str, pd.DataFrame],
    price_col: str = "CloseValue"
) -> Tuple[pd.DataFrame, List[pd.Timestamp]]:
    """
    对齐标的池所有 ETF 的收盘价时间序列.
    """
    price_dict = {}
    for sym, df in universe_dfs.items():
        if price_col in df.columns:
            price_dict[sym] = df[price_col].astype(float)

    price_matrix = pd.DataFrame(price_dict).dropna(how="all").ffill()
    common_dates = list(price_matrix.index)
    return price_matrix, common_dates


def run_portfolio_rotation_backtest(
    universe_dfs: Optional[Dict[str, pd.DataFrame]] = None,
    initial_capital: float = 100000.0,
    rebalance_interval: int = 3,  # 每 3 个交易日检查调仓
    top_n: int = 2,
    safety_cutoff: float = -0.3,
    commission_rate: float = 0.0003,
    defensive_symbol: str = "511090"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    执行多资产截面动量轮动回测.

    :return: (portfolio_df, metrics_dict)
    """
    if universe_dfs is None:
        universe_dfs = load_universe_data()

    if not universe_dfs:
        raise ValueError("标的池数据为空，无法执行回测")

    price_matrix, common_dates = align_universe_price_data(universe_dfs)
    n_days = len(common_dates)
    if n_days < 30:
        raise ValueError("可用历史数据过短 (少于 30 个交易日)")

    # 状态变量
    cash = initial_capital
    holdings: Dict[str, float] = {sym: 0.0 for sym in universe_dfs.keys()}
    
    total_history = np.zeros(n_days, dtype=np.float64)
    cash_history = np.zeros(n_days, dtype=np.float64)
    turnover_history = np.zeros(n_days, dtype=np.float64)
    regime_history: List[str] = []

    # 逐日模拟
    warmup_period = 30  # 预热因子计算所需历史数据

    for i in range(n_days):
        current_date = common_dates[i]
        
        # 1. 计算当日资产组合市值
        current_asset_value = 0.0
        for sym, shares in holdings.items():
            if shares > 0 and sym in price_matrix.columns:
                p = price_matrix.loc[current_date, sym]
                if not pd.isna(p):
                    current_asset_value += shares * p
        current_total = cash + current_asset_value

        # 2. 调仓周期判断 (预热期后每隔 rebalance_interval 天调仓)
        is_rebalance_day = (i >= warmup_period) and ((i - warmup_period) % rebalance_interval == 0)

        daily_turnover = 0.0
        cur_regime = "holding"

        if is_rebalance_day:
            # 截取截至当天的各标的子数据集
            sub_dfs = {}
            for sym, df in universe_dfs.items():
                date_mask = df.index <= current_date
                if date_mask.sum() >= 20:
                    sub_dfs[sym] = df.loc[date_mask]

            if len(sub_dfs) >= 2:
                # 截面打分
                scored_df = score_universe_cross_section(sub_dfs)
                current_active_syms = [s for s, sh in holdings.items() if sh > 0]
                decision = select_top_etfs(
                    scored_df,
                    current_holdings=current_active_syms,
                    top_n=top_n,
                    safety_cutoff=safety_cutoff,
                    defensive_symbol=defensive_symbol
                )
                cur_regime = decision.get("regime", "offensive")
                target_weights = decision.get("weights", {})

                # 计算目标持仓金额与股数
                target_positions: Dict[str, float] = {}
                for sym, w in target_weights.items():
                    if sym in price_matrix.columns:
                        p = price_matrix.loc[current_date, sym]
                        if not pd.isna(p) and p > 0:
                            target_val = current_total * w * (1.0 - commission_rate)
                            target_shares = int(target_val / p // 100) * 100
                            target_positions[sym] = target_shares

                # 先卖出不在目标池或需要减仓的标的
                for sym, current_shares in list(holdings.items()):
                    p = price_matrix.loc[current_date, sym] if sym in price_matrix.columns else 1.0
                    target_s = target_positions.get(sym, 0.0)
                    if current_shares > target_s and not pd.isna(p):
                        sell_shares = current_shares - target_s
                        revenue = sell_shares * p * (1.0 - commission_rate)
                        cash += revenue
                        holdings[sym] = target_s
                        daily_turnover += revenue

                # 再买入目标池中需要增仓的标的
                for sym, target_s in target_positions.items():
                    p = price_matrix.loc[current_date, sym] if sym in price_matrix.columns else 1.0
                    cur_s = holdings.get(sym, 0.0)
                    if target_s > cur_s and not pd.isna(p):
                        buy_shares = target_s - cur_s
                        cost = buy_shares * p * (1.0 + commission_rate)
                        if cash >= cost:
                            cash -= cost
                            holdings[sym] = target_s
                            daily_turnover += cost
                        else:
                            # 资金不足时按剩余现金尽量买入
                            possible_shares = int((cash * (1.0 - commission_rate)) / p // 100) * 100
                            if possible_shares > 0:
                                cost = possible_shares * p * (1.0 + commission_rate)
                                cash -= cost
                                holdings[sym] = cur_s + possible_shares
                                daily_turnover += cost

        # 3. 记录每日结算数据
        day_end_val = 0.0
        for sym, shares in holdings.items():
            if shares > 0 and sym in price_matrix.columns:
                p = price_matrix.loc[current_date, sym]
                if not pd.isna(p):
                    day_end_val += shares * p

        total_history[i] = cash + day_end_val
        cash_history[i] = cash
        turnover_history[i] = daily_turnover
        regime_history.append(cur_regime)

    # 4. 构建基准表现 (等权持有标的池中所有进攻型 ETF)
    non_def_syms = [s for s, m in DEFAULT_ETF_UNIVERSE.items() if not m.get("is_defensive", False) and s in price_matrix.columns]
    if non_def_syms:
        eq_bench = price_matrix[non_def_syms].pct_change().fillna(0.0).mean(axis=1)
        bench_cum = (1.0 + eq_bench).cumprod() * initial_capital
    else:
        bench_cum = pd.Series(initial_capital, index=common_dates)

    portfolio_df = pd.DataFrame({
        "total": total_history,
        "cash": cash_history,
        "turnover": turnover_history,
        "regime": regime_history,
        "benchmark": bench_cum.values
    }, index=common_dates)

    # 截取预热期之后的数据评估绩效
    eval_df = portfolio_df.iloc[warmup_period:].copy()
    eval_df["CloseValue"] = eval_df["benchmark"]
    metrics = calculate_metrics(eval_df, initial_capital=initial_capital)
    
    # 补充组合专用指标
    total_turnover = float(turnover_history.sum())
    metrics["total_turnover"] = round(total_turnover, 2)
    metrics["annual_turnover_rate"] = round(total_turnover / initial_capital / max((n_days - warmup_period) / 242.0, 0.1), 2)
    metrics["start_date"] = str(common_dates[warmup_period].strftime("%Y-%m-%d"))
    metrics["end_date"] = str(common_dates[-1].strftime("%Y-%m-%d"))

    return portfolio_df, metrics
