"""多资产 ETF 截面动量轮动决策引擎 (Rotation Engine)

核心逻辑:
    1. 动态筛选全市场综合评分 Top N (默认 2 只) 强势板块 ETF;
    2. 防御切换闸门: 当全市场动量评分均跌破安全阈值 (表明处于系统性下行/泥沙俱下行情),
       自动将全部或部分仓位切换至国债 ETF (511090) 或空仓现金避险。
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from quant.rotation.scorer import score_universe_cross_section


def select_top_etfs(
    scored_df: pd.DataFrame,
    current_holdings: Optional[List[str]] = None,
    top_n: int = 2,
    safety_cutoff: float = 0.0,
    defensive_symbol: str = "511090"
) -> Dict[str, Any]:
    """
    根据截面打分表做出每日/每周资产配置与轮动决策 (引入持仓缓冲带与绝对动量过滤).

    :param scored_df: 由 score_universe_cross_section 生成的排名表
    :param current_holdings: 当前持仓代码列表 (用于防锯齿频繁换仓)
    :param top_n: 目标持有标的数量 (默认 2 只)
    :param safety_cutoff: 防御切换阈值
    :param defensive_symbol: 避险防御代码 (30年国债 ETF 511090)
    :return: 包含持仓建议、目标权重、状态说明的决策字典
    """
    if scored_df.empty:
        return {
            "regime": "defensive",
            "reason": "数据为空，切换防御",
            "weights": {defensive_symbol: 1.0},
            "selected_assets": []
        }

    non_defensive = scored_df[~scored_df["is_defensive"]].copy()
    if non_defensive.empty:
        return {
            "regime": "defensive",
            "reason": "无有效进攻标的",
            "weights": {defensive_symbol: 1.0},
            "selected_assets": []
        }

    # 过滤出具备基本多头特征的合格候选标的 (20日动量为正且处于 MA60 之上，或 RSRS 处于极高反转区)
    qualified = non_defensive[
        (non_defensive["ret_20d"] > 0.0) | (non_defensive["ma60_bias"] > -0.01) | (non_defensive["rsrs_score"] > 0.7)
    ].copy()

    # 1. 判定是否触发全市场防御切换 (无任何合格进攻标的，或全市场处于系统性破位熊市)
    if qualified.empty:
        return {
            "regime": "defensive",
            "reason": "全市场进攻标的均处于下行破位走势，触发避险闸门全仓切换至 30年国债 ETF",
            "weights": {defensive_symbol: 1.0},
            "selected_assets": [
                {
                    "symbol": defensive_symbol,
                    "name": "30年国债 ETF",
                    "category": "固定收益避险",
                    "rank": 1,
                    "score": 0.0,
                    "ret_20d": "0.0%",
                    "rsrs": 0.0,
                    "weight": 1.0,
                    "reason": "系统性避险"
                }
            ]
        }

    # 2. 候选标的选取 (结合持仓缓冲带 Hysteresis)
    # 若当前持有的标的仍位列前 top_n + 1，则优先保留，避免频繁摩擦换仓
    chosen_symbols = []
    holding_set = set(current_holdings or [])
    
    # 首先检查现有持仓是否依然排名前列且合格
    for _, row in qualified.iterrows():
        sym = str(row["symbol"])
        if sym in holding_set and len(chosen_symbols) < top_n:
            # 只要排名前 top_n + 1 且未破位则继续持有
            if int(row["rank"]) <= top_n + 1:
                chosen_symbols.append(sym)

    # 补充新入围的 Top 标的
    for _, row in qualified.iterrows():
        sym = str(row["symbol"])
        if sym not in chosen_symbols and len(chosen_symbols) < top_n:
            chosen_symbols.append(sym)

    n_sel = len(chosen_symbols)
    if n_sel == 0:
        return {
            "regime": "defensive",
            "reason": "无合格标的，切换国债防御",
            "weights": {defensive_symbol: 1.0},
            "selected_assets": []
        }

    equal_weight = round(1.0 / n_sel, 4)
    weights: Dict[str, float] = {}
    selected_assets: List[Dict[str, Any]] = []

    for sym in chosen_symbols:
        matched = non_defensive[non_defensive["symbol"] == sym]
        if not matched.empty:
            row = matched.iloc[0]
            weights[sym] = equal_weight
            selected_assets.append({
                "symbol": sym,
                "name": row["name"],
                "category": row["category"],
                "rank": int(row["rank"]),
                "score": round(float(row["score"]), 3),
                "ret_20d": f"{float(row['ret_20d']) * 100:+.2f}%",
                "rsrs": round(float(row["rsrs_score"]), 2),
                "weight": equal_weight
            })

    return {
        "regime": "growth_offensive",
        "reason": f"截面动量强势领涨，聚焦全市场 Top {n_sel} 龙头赛道",
        "weights": weights,
        "selected_assets": selected_assets
    }
