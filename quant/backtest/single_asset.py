"""单标的量化回测与新旧策略对比引擎

对比评估:
    1. 传统 SMA 均线交叉 + 静态 RSI 策略
    2. 下一代 RSRS + KAMA + ATR 动态移动止损自适应策略
"""

from __future__ import annotations

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List

from quant.factors.rsrs import calc_rsrs_series
from quant.factors.kama import calc_kama, calc_efficiency_ratio
from quant.factors.volatility import calc_atr
from quant.risk.trailing_stop import ATRTrailingStop


def calculate_metrics(
    portfolio_df: pd.DataFrame,
    initial_capital: float = 100000.0,
    annual_trading_days: int = 242
) -> Dict[str, Any]:
    """
    计算详尽的量化绩效指标 (收益率、夏普、最大回撤、卡玛、胜率等).
    """
    if portfolio_df.empty or "total" not in portfolio_df.columns:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "benchmark_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "total_trades": 0,
            "avg_holding_days": 0.0
        }

    total_series = portfolio_df["total"]
    daily_returns = total_series.pct_change().fillna(0.0)

    n_days = len(portfolio_df)
    years = max(n_days / annual_trading_days, 0.05)

    # 1. 累计收益率与年化收益率
    total_return = (total_series.iloc[-1] - initial_capital) / initial_capital
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1.0 else -1.0

    # 2. 基准收益 (Buy & Hold)
    if "CloseValue" in portfolio_df.columns and len(portfolio_df) > 1:
        first_p = portfolio_df["CloseValue"].iloc[0]
        last_p = portfolio_df["CloseValue"].iloc[-1]
        benchmark_ret = (last_p - first_p) / first_p if first_p > 0 else 0.0
    else:
        benchmark_ret = 0.0

    # 3. 最大回撤
    cummax = total_series.cummax()
    drawdown = (total_series - cummax) / cummax
    max_drawdown = float(drawdown.min())

    # 4. 夏普比率 (无风险利率设为 2.0%)
    rf_daily = 0.02 / annual_trading_days
    excess_ret = daily_returns - rf_daily
    std_ret = daily_returns.std()
    sharpe = float((excess_ret.mean() / std_ret) * np.sqrt(annual_trading_days)) if std_ret > 1e-6 else 0.0

    # 5. 卡玛比率
    calmar = float(cagr / abs(max_drawdown)) if abs(max_drawdown) > 1e-4 else 0.0

    # 6. 交易统计 (胜率、盈亏比)
    trades = []
    holding_days_list = []
    
    if "holdings" in portfolio_df.columns and "cash" in portfolio_df.columns:
        in_trade = False
        buy_price = 0.0
        buy_day_idx = 0
        
        for i in range(len(portfolio_df)):
            hold = portfolio_df["holdings"].iloc[i]
            cur_price = portfolio_df["CloseValue"].iloc[i] if "CloseValue" in portfolio_df.columns else 1.0
            
            if not in_trade and hold > 0:
                in_trade = True
                buy_price = cur_price
                buy_day_idx = i
            elif in_trade and hold == 0:
                in_trade = False
                pnl = (cur_price - buy_price) / buy_price
                trades.append(pnl)
                holding_days_list.append(i - buy_day_idx)

    total_trades = len(trades)
    if total_trades > 0:
        winning_trades = [t for t in trades if t > 0]
        losing_trades = [t for t in trades if t < 0]
        win_rate = len(winning_trades) / total_trades
        
        avg_win = np.mean(winning_trades) if winning_trades else 0.0
        avg_loss = abs(np.mean(losing_trades)) if losing_trades else 1e-6
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
        avg_holding_days = float(np.mean(holding_days_list)) if holding_days_list else 0.0
    else:
        win_rate = 0.0
        profit_loss_ratio = 0.0
        avg_holding_days = 0.0

    return {
        "total_return": round(total_return, 4),
        "annualized_return": round(cagr, 4),
        "benchmark_return": round(benchmark_ret, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sharpe_ratio": round(sharpe, 4),
        "calmar_ratio": round(calmar, 4),
        "win_rate": round(win_rate, 4),
        "profit_loss_ratio": round(profit_loss_ratio, 2) if profit_loss_ratio != float("inf") else 999.0,
        "total_trades": total_trades,
        "avg_holding_days": round(avg_holding_days, 1)
    }


def run_nextgen_single_backtest(
    df: pd.DataFrame,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    rsrs_n: int = 18,
    rsrs_m: int = 250,
    rsrs_buy_thd: float = 0.7,
    rsrs_sell_thd: float = -0.7,
    kama_er_period: int = 10,
    kama_fast: int = 2,
    kama_slow: int = 30,
    atr_period: int = 14,
    atr_stop_multiplier: float = 2.5,
    volume_filter_window: int = 20,
    min_volume_ratio: float = 0.8
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    运行下一代自适应策略回测 (RSRS + KAMA + ATR Trailing Stop).
    """
    data = df.copy()
    close = data["CloseValue"].astype(float)
    high = data["HighValue"].astype(float)
    low = data["LowValue"].astype(float)
    vol = data["Volume"].astype(float)

    # 1. 计算核心因子
    rsrs_df = calc_rsrs_series(data, n_window=rsrs_n, m_window=rsrs_m)
    rsrs_score = rsrs_df["rsrs_score"]

    kama = calc_kama(close, er_period=kama_er_period, fast_period=kama_fast, slow_period=kama_slow)
    atr = calc_atr(data, period=atr_period)
    vol_ma = vol.rolling(window=volume_filter_window, min_periods=5).mean()

    n = len(data)
    cash = initial_capital
    holdings = 0.0  # 股数
    
    cash_history = np.zeros(n, dtype=np.float64)
    holdings_history = np.zeros(n, dtype=np.float64)
    total_history = np.zeros(n, dtype=np.float64)
    signals_history = np.zeros(n, dtype=int)
    stop_line_history = np.full(n, np.nan, dtype=np.float64)

    trailing_stop = ATRTrailingStop(atr_multiplier=atr_stop_multiplier)
    in_pos = False

    for i in range(n):
        cur_p = close.iloc[i]
        cur_h = high.iloc[i]
        cur_l = low.iloc[i]
        cur_vol = vol.iloc[i]
        cur_vol_ma = vol_ma.iloc[i] if not pd.isna(vol_ma.iloc[i]) else cur_vol
        cur_rsrs = rsrs_score.iloc[i] if not pd.isna(rsrs_score.iloc[i]) else 0.0
        cur_kama = kama.iloc[i] if not pd.isna(kama.iloc[i]) else cur_p
        cur_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else cur_p * 0.02

        sig = 0
        if not in_pos:
            # 综合入场条件 (RSRS 领先信号 + KAMA 顺势确认 + 量能不萎缩)
            # 当 RSRS 强力反转 (>0.7) 且价格处于 KAMA 之上或紧贴上拐
            is_rsrs_bull = cur_rsrs > rsrs_buy_thd
            is_kama_bull = cur_p >= cur_kama * 0.995
            is_volume_ok = cur_vol >= cur_vol_ma * min_volume_ratio

            if is_rsrs_bull and is_kama_bull and is_volume_ok and (i >= rsrs_n + 10):
                sig = 1
                # 全仓买入 (按 100 股整手)
                trade_cash = cash * (1.0 - commission_rate)
                shares_to_buy = int(trade_cash / cur_p // 100) * 100
                if shares_to_buy > 0:
                    cost = shares_to_buy * cur_p * (1.0 + commission_rate)
                    if cash >= cost:
                        cash -= cost
                        holdings = shares_to_buy
                        in_pos = True
                        init_stop = trailing_stop.enter_position(cur_p, cur_atr)
                        stop_line_history[i] = init_stop
        else:
            # 持仓状态: 更新 ATR 移动止损
            is_stopped, stop_p, _ = trailing_stop.update(cur_h, cur_p, cur_atr)
            stop_line_history[i] = stop_p

            # 出场条件: 1. 触发 ATR 动态止损; 2. RSRS 出现严重顶背离 (< sell_threshold) 且跌破 KAMA
            is_rsrs_bear = (cur_rsrs < rsrs_sell_thd) and (cur_p < cur_kama)

            if is_stopped or is_rsrs_bear:
                sig = -1
                # 全部平仓
                revenue = holdings * cur_p * (1.0 - commission_rate)
                cash += revenue
                holdings = 0.0
                in_pos = False
                trailing_stop.reset()

        signals_history[i] = sig
        cash_history[i] = cash
        holdings_history[i] = holdings
        total_history[i] = cash + holdings * cur_p

    portfolio_df = pd.DataFrame({
        "CloseValue": close,
        "HighValue": high,
        "LowValue": low,
        "Volume": vol,
        "cash": cash_history,
        "holdings": holdings_history,
        "total": total_history,
        "signal": signals_history,
        "trailing_stop": stop_line_history,
        "rsrs_score": rsrs_score,
        "kama": kama
    }, index=data.index)

    metrics = calculate_metrics(portfolio_df, initial_capital=initial_capital)
    return portfolio_df, metrics


def run_legacy_single_backtest(
    df: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    运行传统 SMA 均线 + RSI 策略回测 (基于现有 strategy_params.json 配置).
    """
    from sdd import simple_ma_strategy, run_backtest

    # 尝试加载固化参数
    params_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "strategy_params.json")
    clean_sym = symbol.split(".")[0]
    
    short_window, long_window = 3, 12
    rsi_period, rsiValueThd, rsiRateUp = 13, 30, 1.5
    MaRateUp, divergence_threshold, VolumeSellRate = 1.1, 0.06, 4.5
    volume_mavg_Value = 10

    if os.path.exists(params_file):
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                content = "\n".join(l for l in f if not l.strip().startswith("//"))
                all_params = json.loads(content)
                p = all_params.get(clean_sym, all_params.get("default", {}))
                short_window = p.get("short_window", short_window)
                long_window = p.get("long_window", long_window)
                rsi_period = p.get("rsi_period", rsi_period)
                rsiValueThd = p.get("rsiValueThd", rsiValueThd)
                rsiRateUp = p.get("rsiRateUp", rsiRateUp)
                MaRateUp = p.get("MaRateUp", MaRateUp)
                divergence_threshold = p.get("divergence_threshold", divergence_threshold)
                VolumeSellRate = p.get("VolumeSellRate", VolumeSellRate)
                volume_mavg_Value = p.get("volume_mavg_Value", volume_mavg_Value)
        except Exception:
            pass

    signals = simple_ma_strategy(
        df,
        clean_sym,
        short_window=short_window,
        long_window=long_window,
        volume_mavg_Value=volume_mavg_Value,
        rsi_period=rsi_period,
        MaRateUp=MaRateUp,
        rsiValueThd=rsiValueThd,
        rsiRateUp=rsiRateUp,
        divergence_threshold=divergence_threshold,
        VolumeSellRate=VolumeSellRate,
        plot_chart=0,
        enable_file_io=False
    )

    port = run_backtest(df, clean_sym, signals, initial_capital=initial_capital, commission_rate=commission_rate)
    metrics = calculate_metrics(port, initial_capital=initial_capital)
    return port, metrics


def compare_strategies_single_asset(
    df: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """
    单标的新旧策略对比运行，输出综合对比指标字典.
    """
    _, legacy_m = run_legacy_single_backtest(df, symbol, initial_capital=initial_capital)
    _, nextgen_m = run_nextgen_single_backtest(df, initial_capital=initial_capital)

    return {
        "symbol": symbol,
        "legacy": legacy_m,
        "nextgen": nextgen_m,
        "delta": {
            "total_return": round(nextgen_m["total_return"] - legacy_m["total_return"], 4),
            "max_drawdown_reduction": round(abs(legacy_m["max_drawdown"]) - abs(nextgen_m["max_drawdown"]), 4),
            "sharpe_improvement": round(nextgen_m["sharpe_ratio"] - legacy_m["sharpe_ratio"], 4),
            "win_rate_delta": round(nextgen_m["win_rate"] - legacy_m["win_rate"], 4)
        }
    }
