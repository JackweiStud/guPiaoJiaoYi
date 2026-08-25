"""多资产 ETF 截面动量与因子复合评分器 (Cross-Section Scorer)

复合评分公式:
    Score_i = w_mom * RiskAdjMom_i + w_rsrs * RSRS_Score_i + w_vol * VolumeRatio_i
    结合 MA60 趋势保护，动态筛选全市场动量最强、阻力支撑最优、放量突破的领头板块。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple

from quant.factors.rsrs import calc_rsrs_series
from quant.factors.volatility import calc_atr, calc_risk_adjusted_momentum


def compute_etf_single_date_factors(
    df: pd.DataFrame,
    date_idx: Optional[int] = None,
    mom_window: int = 20,
    rsrs_n: int = 18,
    rsrs_m: int = 250
) -> Dict[str, float]:
    """
    计算单只 ETF 在指定日期的截面因子明细.
    """
    if df.empty or len(df) < mom_window:
        return {
            "ret_20d": 0.0,
            "atr_pct": 0.02,
            "risk_adj_mom": 0.0,
            "rsrs_score": 0.0,
            "vol_ratio": 1.0,
            "ma60_bias": 0.0,
            "close": 1.0
        }

    sub_df = df if date_idx is None else df.iloc[: date_idx + 1]
    if len(sub_df) < mom_window:
        return {
            "ret_20d": 0.0,
            "atr_pct": 0.02,
            "risk_adj_mom": 0.0,
            "rsrs_score": 0.0,
            "vol_ratio": 1.0,
            "ma60_bias": 0.0,
            "close": float(sub_df["CloseValue"].iloc[-1])
        }

    close = sub_df["CloseValue"].astype(float)
    vol = sub_df["Volume"].astype(float)
    cur_p = close.iloc[-1]

    # 1. 20日收益率与 ATR 波动率
    ret_20d = float((cur_p - close.iloc[-mom_window]) / close.iloc[-mom_window])
    atr_series = calc_atr(sub_df, period=mom_window)
    cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else cur_p * 0.02
    atr_pct = cur_atr / cur_p if cur_p > 0 else 0.02

    # 风险调整动量
    risk_adj_mom = ret_20d / atr_pct if atr_pct > 1e-4 else ret_20d

    # 2. RSRS 评分
    try:
        rsrs_df = calc_rsrs_series(sub_df, n_window=rsrs_n, m_window=rsrs_m)
        cur_rsrs = float(rsrs_df["rsrs_score"].iloc[-1]) if not pd.isna(rsrs_df["rsrs_score"].iloc[-1]) else 0.0
    except Exception:
        cur_rsrs = 0.0

    # 3. 5日 / 20日量比
    vol_5 = vol.iloc[-5:].mean() if len(vol) >= 5 else vol.iloc[-1]
    vol_20 = vol.iloc[-20:].mean() if len(vol) >= 20 else vol_5
    vol_ratio = float(vol_5 / vol_20) if vol_20 > 0 else 1.0

    # 4. MA60 均线偏离度 (中长期趋势保护)
    ma60_window = min(60, len(close))
    ma60 = float(close.iloc[-ma60_window:].mean())
    ma60_bias = float((cur_p - ma60) / ma60) if ma60 > 0 else 0.0

    return {
        "ret_20d": round(ret_20d, 4),
        "atr_pct": round(atr_pct, 4),
        "risk_adj_mom": round(risk_adj_mom, 4),
        "rsrs_score": round(cur_rsrs, 4),
        "vol_ratio": round(vol_ratio, 4),
        "ma60_bias": round(ma60_bias, 4),
        "close": round(cur_p, 4)
    }


def score_universe_cross_section(
    universe_dfs: Dict[str, pd.DataFrame],
    universe_info: Optional[Dict[str, Dict[str, Any]]] = None,
    date_idx: Optional[int] = None,
    w_mom: float = 0.50,
    w_rsrs: float = 0.30,
    w_vol: float = 0.20
) -> pd.DataFrame:
    """
    对标的池所有 ETF 在某一日进行截面打分并排名.

    :return: 包含代码、名称、各因子值、复合得分与排名的 DataFrame
    """
    from quant.rotation.universe import DEFAULT_ETF_UNIVERSE
    info_map = universe_info or DEFAULT_ETF_UNIVERSE

    records = []
    for symbol, df in universe_dfs.items():
        meta = info_map.get(symbol, {"name": symbol, "category": "ETF", "is_defensive": False})
        factors = compute_etf_single_date_factors(df, date_idx=date_idx)
        
        records.append({
            "symbol": symbol,
            "name": meta.get("name", symbol),
            "category": meta.get("category", "ETF"),
            "is_defensive": meta.get("is_defensive", False),
            **factors
        })

    if not records:
        return pd.DataFrame()

    res_df = pd.DataFrame(records)

    # 截面标准化 (Z-score 处理非防御类资产)
    non_def = res_df[~res_df["is_defensive"]].copy()
    if len(non_def) >= 2:
        def z_score(series):
            std = series.std()
            return (series - series.mean()) / std if std > 1e-6 else pd.Series(0.0, index=series.index)

        mom_z = z_score(non_def["risk_adj_mom"])
        rsrs_z = z_score(non_def["rsrs_score"])
        vol_z = z_score(non_def["vol_ratio"])

        # 趋势惩罚: 若价格处于 MA60 之下且处于严重下行通道，打折扣分
        trend_penalty = non_def["ma60_bias"].apply(lambda b: 0.0 if b >= 0 else b * 2.0)

        composite_score = (w_mom * mom_z + w_rsrs * rsrs_z + w_vol * vol_z) + trend_penalty
        non_def["score"] = composite_score
    else:
        non_def["score"] = non_def["risk_adj_mom"]

    # 将防御类资产分数设为基准 0 分
    def_df = res_df[res_df["is_defensive"]].copy()
    def_df["score"] = 0.0

    scored_df = pd.concat([non_def, def_df]).sort_values(by="score", ascending=False).reset_index(drop=True)
    scored_df["rank"] = scored_df.index + 1
    return scored_df
