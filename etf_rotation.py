#!/usr/bin/env python3
"""
多资产 ETF 截面动量轮动与宏观状态机执行入口 (ETF Rotation CLI).

功能:
  1. 每日截面打分与 Top 2 强势标的推荐榜单 (含国债避险切换状态)
  2. 宏观流动性闸门与总仓位上限判定
  3. 全历史多资产轮动组合回测与绩效评估
  4. 单标的新旧策略对比回测

常用示例:
  python etf_rotation.py                      # 输出今日截面打分与 Top 推荐
  python etf_rotation.py --backtest           # 运行多资产轮动历史回测并打印绩效指标
  python etf_rotation.py --compare            # 运行标的池各单资产新旧策略对比
  python etf_rotation.py --format json        # 以 JSON 格式输出 (方便与其他自动化工具集成)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from quant.rotation.universe import load_universe_data, get_universe_info, DEFAULT_ETF_UNIVERSE
from quant.rotation.scorer import score_universe_cross_section
from quant.rotation.engine import select_top_etfs
from quant.regime.macro_regime import get_current_macro_regime
from quant.backtest.portfolio import run_portfolio_rotation_backtest
from quant.backtest.single_asset import compare_strategies_single_asset


def run_daily_rotation_summary() -> Dict[str, Any]:
    """生成每日截面轮动与宏观状态摘要"""
    universe_dfs = load_universe_data()
    universe_info = get_universe_info()

    # 1. 宏观状态机
    macro_regime = get_current_macro_regime()

    # 2. 截面打分
    scored_df = score_universe_cross_section(universe_dfs, universe_info=universe_info)
    
    # 3. 轮动决策
    decision = select_top_etfs(scored_df, top_n=2, safety_cutoff=-0.3)

    ranking_list = []
    if not scored_df.empty:
        for _, r in scored_df.iterrows():
            ranking_list.append({
                "rank": int(r["rank"]),
                "symbol": str(r["symbol"]),
                "name": str(r["name"]),
                "category": str(r["category"]),
                "is_defensive": bool(r["is_defensive"]),
                "score": round(float(r["score"]), 3),
                "ret_20d": f"{float(r['ret_20d']) * 100:+.2f}%",
                "rsrs": round(float(r["rsrs_score"]), 2),
                "vol_ratio": round(float(r["vol_ratio"]), 2),
                "ma60_bias": f"{float(r['ma60_bias']) * 100:+.2f}%",
                "close": round(float(r["close"]), 3)
            })

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "macro_regime": macro_regime,
        "decision": decision,
        "rankings": ranking_list
    }


def print_text_summary(summary: Dict[str, Any]):
    print("\n" + "=" * 70)
    print(f"📊 多资产 ETF 截面动量轮动分析报告 ({summary.get('generated_at')})")
    print("=" * 70)

    regime = summary.get("macro_regime", {})
    print(f"\n【宏观流动性闸门】: {regime.get('label', '未知')} (总仓位上限: {int(regime.get('max_position_cap', 1.0) * 100)}%)")
    print(f"  说明: {regime.get('description', '')}")

    decision = summary.get("decision", {})
    print(f"\n【今日轮动配置建议】: {decision.get('reason', '')}")
    if decision.get("selected_assets"):
        for a in decision["selected_assets"]:
            print(f"  👉 标的: {a.get('name')} ({a.get('symbol')}) | 建议仓位: {int(a.get('weight', 0.5) * 100)}% | 20日动量: {a.get('ret_20d', '0.0%')}")

    print("\n【全市场监控池截面排名榜单】:")
    print(f"{'排名':<4} {'代码':<8} {'名称':<14} {'板块类别':<14} {'综合评分':<10} {'20D收益':<10} {'RSRS':<8} {'量比':<6}")
    print("-" * 76)
    for r in summary.get("rankings", []):
        def_tag = " [防守]" if r["is_defensive"] else ""
        print(f"{r['rank']:<4} {r['symbol']:<8} {r['name'] + def_tag:<14} {r['category']:<14} {r['score']:<10} {r['ret_20d']:<10} {r['rsrs']:<8} {r['vol_ratio']:<6}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="多资产 ETF 截面动量轮动与量化投研引擎")
    parser.add_argument("--backtest", action="store_true", help="运行多资产轮动全样本历史回测")
    parser.add_argument("--compare", action="store_true", help="运行单标的新旧策略回测对比")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    args = parser.parse_args()

    if args.backtest:
        print("正在运行多资产 ETF 截面动量轮动全历史回测...")
        _, metrics = run_portfolio_rotation_backtest()
        if args.format == "json":
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 60)
            print("📈 多资产 ETF 截面轮动历史回测绩效报告")
            print("=" * 60)
            print(f"回测时间区间: {metrics.get('start_date')} 至 {metrics.get('end_date')}")
            print(f"累计收益率: {metrics.get('total_return', 0.0) * 100:+.2f}% (等权基准: {metrics.get('benchmark_return', 0.0) * 100:+.2f}%)")
            print(f"年化复合收益率 (CAGR): {metrics.get('annualized_return', 0.0) * 100:+.2f}%")
            print(f"最大回撤 (Max Drawdown): {metrics.get('max_drawdown', 0.0) * 100:.2f}%")
            print(f"夏普比率 (Sharpe Ratio): {metrics.get('sharpe_ratio', 0.0):.2f}")
            print(f"卡玛比率 (Calmar Ratio): {metrics.get('calmar_ratio', 0.0):.2f}")
            print(f"总换手率: {metrics.get('total_turnover', 0.0):.2f} 元 (年化换手率: {metrics.get('annual_turnover_rate', 0.0):.1f}x)")
            print("=" * 60 + "\n")
        return

    if args.compare:
        universe_dfs = load_universe_data()
        results = []
        for sym, df in universe_dfs.items():
            if not DEFAULT_ETF_UNIVERSE.get(sym, {}).get("is_defensive", False):
                res = compare_strategies_single_asset(df, sym)
                results.append(res)

        if args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print("\n" + "=" * 80)
            print("⚖️ 单标的新旧策略对比回测报告 (传统 SMA 均线 vs 下一代 RSRS+KAMA+ATR)")
            print("=" * 80)
            for r in results:
                sym = r["symbol"]
                leg = r["legacy"]
                nxt = r["nextgen"]
                d = r["delta"]
                print(f"\n【标的: {sym}】")
                print(f"  旧策略 (SMA+RSI): 累计收益 {leg['total_return']*100:+.2f}% | 最大回撤 {leg['max_drawdown']*100:.2f}% | 夏普 {leg['sharpe_ratio']:.2f} | 胜率 {leg['win_rate']*100:.1f}%")
                print(f"  新策略 (KAMA+RSRS): 累计收益 {nxt['total_return']*100:+.2f}% | 最大回撤 {nxt['max_drawdown']*100:.2f}% | 夏普 {nxt['sharpe_ratio']:.2f} | 胜率 {nxt['win_rate']*100:.1f}%")
                print(f"  👉 收益差: {d['total_return']*100:+.2f}% | 回撤优化: {d['max_drawdown_reduction']*100:+.2f}% | 夏普提升: {d['sharpe_improvement']:+.2f}")
            print("=" * 80 + "\n")
        return

    # 默认输出每日轮动总结
    summary = run_daily_rotation_summary()
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_text_summary(summary)


if __name__ == "__main__":
    main()
