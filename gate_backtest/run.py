"""一条命令复现：python -m gate_backtest.run"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from gate_backtest import constants as C
from gate_backtest.backtest import (
    build_combo_position,
    build_target_position,
    daily_cash_return_from_dgs3mo,
    run_buy_and_hold,
    run_fund_backtest,
    run_listed_backtest,
    run_monthly_dca,
)
from gate_backtest.data import align_asof
from gate_backtest.bootstrap import mdd_diff_block_bootstrap
from gate_backtest.credit_mapping import compute_baa_threshold_from_oas
from gate_backtest.data import DataBundle, copy_raw_to_artifacts, load_all
from gate_backtest.gates import credit_gate, oil_gate, oas_gate, rate_gate
from gate_backtest.metrics import (
    avg_holding_length,
    missed_opportunity_cost,
    summarize_equity,
)
from gate_backtest.null_random import random_timing_mdds
from gate_backtest.plotting import plot_drawdowns, plot_equity_curves, plot_random_mdd_hist

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
ARTIFACTS = "/opt/cursor/artifacts"


def _require_frozen_credit() -> Tuple[float, float]:
    if C.CREDIT_Q is None or C.CREDIT_BAA_THRESHOLD is None:
        raise SystemExit(
            "CREDIT_Q / CREDIT_BAA_THRESHOLD 尚未写死。请先运行映射并单独 commit。"
        )
    return float(C.CREDIT_Q), float(C.CREDIT_BAA_THRESHOLD)


def _asset_returns(ohlcv: pd.DataFrame) -> pd.Series:
    return ohlcv["Close"].astype(float).pct_change().fillna(0.0)


def _eval_from_position(
    name: str,
    ohlcv: pd.DataFrame,
    pos: pd.Series,
    cash_daily: pd.Series,
    asset_rets: pd.Series,
    carry_days: int = 0,
    max_carry: int = 0,
) -> Dict[str, Any]:
    pf = run_listed_backtest(ohlcv, pos, cash_daily)
    gate_open_for_miss = pos > 0
    cash_on_cal, _, _ = align_asof(cash_daily, ohlcv.index)
    miss = missed_opportunity_cost(asset_rets, cash_on_cal.fillna(0.0), gate_open_for_miss)
    stats = summarize_equity(pf["total"], pos, pf["returns"])
    stats.update(
        {
            "name": name,
            "missed_opportunity_cost": miss,
            "avg_hold_len": avg_holding_length(pos),
            "carry_forward_days": carry_days,
            "max_carry_streak": max_carry,
            "equity": pf["total"],
            "returns": pf["returns"],
            "position": pos,
            "portfolio": pf,
        }
    )
    return stats


def _eval_strategy(
    name: str,
    ohlcv: pd.DataFrame,
    gate_native: pd.Series,
    cash_daily: pd.Series,
    asset_rets: pd.Series,
) -> Dict[str, Any]:
    pos, carry_days, max_carry = build_target_position(gate_native, ohlcv.index)
    return _eval_from_position(
        name, ohlcv, pos, cash_daily, asset_rets, carry_days, max_carry
    )


def _eval_combo(
    name: str,
    ohlcv: pd.DataFrame,
    gates_native: list,
    cash_daily: pd.Series,
    asset_rets: pd.Series,
) -> Dict[str, Any]:
    pos, carry_days, max_carry = build_combo_position(gates_native, ohlcv.index)
    return _eval_from_position(
        name, ohlcv, pos, cash_daily, asset_rets, carry_days, max_carry
    )


def _segment_stats(equity: pd.Series, position: pd.Series, returns: pd.Series) -> Dict[str, float]:
    if equity is None or equity.empty or len(equity) < 5:
        return {
            "max_drawdown": float("nan"),
            "ann_return": float("nan"),
            "hold_day_share": float("nan"),
            "missed_opportunity_cost": float("nan"),
        }
    # 分段内从该段首日净值起算
    eq = equity / equity.iloc[0]
    base = summarize_equity(eq, position.reindex(eq.index), returns.reindex(eq.index))
    return {
        "max_drawdown": base["max_drawdown"],
        "ann_return": base["ann_return"],
        "hold_day_share": base["hold_day_share"],
    }


def _robust_stable(base_mdd: float, variants: List[float], tol_ratio: float = 0.25) -> bool:
    """粗判定：各 ±10% 变体 MDD 与基准相对偏离不超过 25% 则称稳定。"""
    if not np.isfinite(base_mdd) or abs(base_mdd) < 1e-12:
        return False
    for v in variants:
        if not np.isfinite(v):
            return False
        if abs(v - base_mdd) / abs(base_mdd) > tol_ratio:
            return False
    return True


def run_mapping_only(bundle: DataBundle) -> Dict[str, float]:
    return compute_baa_threshold_from_oas(bundle.fred["BAMLH0A0HYM2"], bundle.fred["BAA10Y"])


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS, exist_ok=True)

    print("== 下载真实数据并归档原样 CSV ==")
    bundle = load_all()
    copied = copy_raw_to_artifacts(os.path.join(ARTIFACTS, "data_raw"))
    print(f"data_raw -> artifacts: {len(copied)} files")

    if "--map-credit" in argv:
        mapping = run_mapping_only(bundle)
        out = os.path.join(OUT_DIR, "credit_mapping.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(json.dumps(mapping, ensure_ascii=False, indent=2))
        print(f"wrote {out}")
        return 0

    q, tau = _require_frozen_credit()
    print(f"使用写死映射: q={q}, tau={tau}")

    # ---- 主样本日历：SOXX ----
    soxx = bundle.prices["SOXX"].copy()
    soxx = soxx.loc[soxx.index >= pd.Timestamp(C.SAMPLE_START)]
    smh = bundle.prices["SMH"].copy()
    smh = smh.loc[smh.index >= pd.Timestamp(C.SAMPLE_START)]

    cash_daily = daily_cash_return_from_dgs3mo(bundle.fred["DGS3MO"])
    asset_rets = _asset_returns(soxx)

    # 原生门（各自日历上计算；组合在交易日历对齐后 AND）
    g_oil = oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD, C.OIL_STREAK_DAYS)
    g_rate = rate_gate(bundle.fred["DGS30"], C.RATE_MA_WINDOW, band=0.0)
    g_credit = credit_gate(bundle.fred["BAA10Y"], tau)

    results: Dict[str, Dict[str, Any]] = {}
    results["组合"] = _eval_combo("组合", soxx, [g_oil, g_rate, g_credit], cash_daily, asset_rets)
    results["单门-油价"] = _eval_strategy("单门-油价", soxx, g_oil, cash_daily, asset_rets)
    results["单门-利率"] = _eval_strategy("单门-利率", soxx, g_rate, cash_daily, asset_rets)
    results["单门-信用"] = _eval_strategy("单门-信用", soxx, g_credit, cash_daily, asset_rets)
    strategies_native = {"组合": None, "单门-油价": g_oil, "单门-利率": g_rate, "单门-信用": g_credit}

    # 对照组
    bh = run_buy_and_hold(soxx, cash_daily)
    results["一直持有"] = {
        "name": "一直持有",
        **summarize_equity(bh["total"], pd.Series(1.0, index=soxx.index), bh["returns"]),
        "missed_opportunity_cost": 0.0,
        "avg_hold_len": float(len(soxx)),
        "equity": bh["total"],
        "returns": bh["returns"],
        "position": pd.Series(1.0, index=soxx.index),
        "portfolio": bh,
    }
    dca = run_monthly_dca(soxx, cash_daily)
    results["每月定投"] = {
        "name": "每月定投",
        **summarize_equity(dca["total"], dca["position"], dca["returns"]),
        "missed_opportunity_cost": 0.0,
        "avg_hold_len": float("nan"),
        "equity": dca["total"],
        "returns": dca["returns"],
        "position": dca["position"],
        "portfolio": dca,
    }

    # OAS 交叉检查（2023-11+，不参与通过标准）
    oas_g = oas_gate(bundle.fred["BAMLH0A0HYM2"], C.CREDIT_OAS_TARGET)
    soxx_oas = soxx.loc[soxx.index >= pd.Timestamp(C.CREDIT_OVERLAP_START)]
    if len(soxx_oas) > 20:
        results["OAS交叉检查-组合"] = _eval_combo(
            "OAS交叉检查-组合",
            soxx_oas,
            [g_oil, g_rate, oas_g],
            cash_daily,
            _asset_returns(soxx_oas),
        )

    # 稳健性 ±10%（组合）：每次只扰动一个门
    robust_specs = [
        ("油价-10%", [oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD * 0.9, C.OIL_STREAK_DAYS), g_rate, g_credit]),
        ("油价+10%", [oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD * 1.1, C.OIL_STREAK_DAYS), g_rate, g_credit]),
        ("利率-10%", [g_oil, rate_gate(bundle.fred["DGS30"], C.RATE_MA_WINDOW, band=-0.1), g_credit]),
        ("利率+10%", [g_oil, rate_gate(bundle.fred["DGS30"], C.RATE_MA_WINDOW, band=0.1), g_credit]),
        ("信用-10%", [g_oil, g_rate, credit_gate(bundle.fred["BAA10Y"], tau * 0.9)]),
        ("信用+10%", [g_oil, g_rate, credit_gate(bundle.fred["BAA10Y"], tau * 1.1)]),
    ]
    robust_mdds = []
    for rname, gates in robust_specs:
        st = _eval_combo(f"稳健-{rname}", soxx, gates, cash_daily, asset_rets)
        results[f"稳健-{rname}"] = st
        robust_mdds.append(st["max_drawdown"])

    # SMH 稳健性标的
    results["SMH-组合"] = _eval_combo(
        "SMH-组合", smh, [g_oil, g_rate, g_credit], cash_daily, _asset_returns(smh)
    )

    # 539002 参考
    fund_note = ""
    if bundle.fund_nav is not None:
        nav = bundle.fund_nav
        nav = nav.loc[nav.index >= pd.Timestamp("2024-01-01")]
        if len(nav) > 5:
            pos, cdays, mstreak = build_combo_position([g_oil, g_rate, g_credit], nav.index)
            fund_pf = run_fund_backtest(nav, pos, cash_daily, daily_subscribe_limit=10_000.0)
            results["539002-组合参考"] = {
                "name": "539002-组合参考",
                **summarize_equity(fund_pf["total"], pos, fund_pf["returns"]),
                "missed_opportunity_cost": float("nan"),
                "equity": fund_pf["total"],
                "returns": fund_pf["returns"],
                "position": pos,
                "carry_forward_days": cdays,
                "max_carry_streak": mstreak,
            }
        else:
            fund_note = "539002 在 2024+ 有效净值过少"
    else:
        fund_note = "539002 净值未能下载：" + str(bundle.gaps.get("539002"))

    # 随机择时（关键）
    combo = results["组合"]
    print("== 随机择时零假设（1000 条，随机的是信号）==")
    mdds, p5 = random_timing_mdds(
        soxx,
        cash_daily,
        hold_share=combo["hold_day_share"],
        avg_len=combo["avg_hold_len"],
        n_paths=C.N_RANDOM_PATHS,
        seed=C.RANDOM_SEED,
    )
    np.save(os.path.join(OUT_DIR, "random_mdds.npy"), mdds)

    # bootstrap
    print("== 分块 bootstrap（重采样真实收益）==")
    point, lo, hi, boot_diffs = mdd_diff_block_bootstrap(
        combo["returns"],
        results["一直持有"]["returns"],
        block=C.BOOTSTRAP_BLOCK,
        n_boot=C.BOOTSTRAP_N,
        seed=C.BOOTSTRAP_SEED,
    )

    # 分段表
    segment_rows = []
    strategy_names_main = ["组合", "单门-油价", "单门-利率", "单门-信用", "一直持有", "每月定投"]
    for seg_name, (seg_start, seg_end) in C.SEGMENTS.items():
        for sname in strategy_names_main:
            st = results[sname]
            eq = st["equity"].loc[seg_start:seg_end]
            pos = st["position"].reindex(eq.index)
            rets = st["returns"].reindex(eq.index)
            base = _segment_stats(eq, pos, rets)
            # 分段踏空
            if sname in ("组合", "单门-油价", "单门-利率", "单门-信用"):
                a = asset_rets.loc[eq.index]
                c, _, _ = align_asof(cash_daily, eq.index)
                miss = missed_opportunity_cost(a, c.fillna(0.0), (pos > 0))
            else:
                miss = 0.0 if sname == "一直持有" else float("nan")
            segment_rows.append(
                {
                    "segment": seg_name,
                    "strategy": sname,
                    "max_drawdown": base["max_drawdown"],
                    "ann_return": base["ann_return"],
                    "hold_day_share": base["hold_day_share"],
                    "missed_opportunity_cost": miss,
                }
            )
    seg_df = pd.DataFrame(segment_rows)

    # 通过标准
    mdd_c = combo["max_drawdown"]
    mdd_bh = results["一直持有"]["max_drawdown"]
    # 回撤幅度降低 ≥30%：|mdd_c| <= 0.7 * |mdd_bh|
    crit1 = abs(mdd_c) <= 0.70 * abs(mdd_bh) if abs(mdd_bh) > 0 else False
    # MDD 更浅（代数上更大，因为 MDD 为负）低于随机组 P5：
    # 「最大回撤低于随机组第5百分位」——回撤是负数时，更低=更负=更差。
    # 中文「低于」在回撤语境通常指回撤幅度更小。结合「区分门槛真有效」，
    # 应为：策略 MDD 幅度小于随机 P5 幅度，即 strategy_mdd > p5（两者均为负时）。
    # 预登记原文：「组合策略最大回撤低于随机组的第 5 百分位」
    # 在风险指标里「最大回撤低于」常指 |MDD| 更小。采用 |MDD_strat| < |P5| 即 mdd_c > p5。
    crit2 = mdd_c > p5  # 两者为负：策略回撤更浅
    ann_c = combo["ann_return"]
    ann_bh = results["一直持有"]["ann_return"]
    crit3 = (ann_bh - ann_c) <= 0.03 + 1e-12
    passed = bool(crit1 and crit2 and crit3)

    # 变体计数
    variant_names = [
        n
        for n in results
        if n
        not in (
            "一直持有",
            "每月定投",
        )
    ]
    n_variants = len(variant_names)

    robust_ok = _robust_stable(combo["max_drawdown"], robust_mdds)

    # 沿用统计（各 FRED 序列相对 SOXX 日历）
    ffill_rows = []
    for sid, series in bundle.fred.items():
        _, cdays, mstreak = align_asof(series, soxx.index)
        ffill_rows.append(
            {"series_id": sid, "carry_forward_days": cdays, "max_carry_streak": mstreak, "calendar": "SOXX 交易日"}
        )
    for ticker, px in bundle.prices.items():
        ffill_rows.append(
            {
                "series_id": ticker,
                "carry_forward_days": 0,
                "max_carry_streak": 0,
                "calendar": "自身交易日（无需沿用）",
            }
        )
    ffill_df = pd.DataFrame(ffill_rows)

    # 图
    curves = {
        "组合": combo["equity"],
        "一直持有": results["一直持有"]["equity"],
        "每月定投": results["每月定投"]["equity"],
        "单门-油价": results["单门-油价"]["equity"],
        "单门-利率": results["单门-利率"]["equity"],
        "单门-信用": results["单门-信用"]["equity"],
    }
    p1 = plot_equity_curves(curves, os.path.join(OUT_DIR, "equity_curves.png"))
    p2 = plot_drawdowns(curves, os.path.join(OUT_DIR, "drawdowns.png"))
    p3 = plot_random_mdd_hist(
        mdds, combo["max_drawdown"], p5, os.path.join(OUT_DIR, "random_mdd_hist.png")
    )
    for p in (p1, p2, p3):
        shutil.copy2(p, os.path.join(ARTIFACTS, os.path.basename(p)))

    # 写 RESULTS.md
    results_path = os.path.join(ROOT, "RESULTS.md")
    _write_results(
        results_path,
        bundle=bundle,
        seg_df=seg_df,
        results=results,
        ffill_df=ffill_df,
        q=q,
        tau=tau,
        p5=p5,
        boot=(point, lo, hi),
        crits=(crit1, crit2, crit3, passed),
        n_variants=n_variants,
        variant_names=variant_names,
        robust_ok=robust_ok,
        robust_mdds=robust_mdds,
        fund_note=fund_note,
        mdds=mdds,
    )
    shutil.copy2(results_path, os.path.join(ARTIFACTS, "RESULTS.md"))

    # 机器可读摘要
    summary = {
        "credit_q": q,
        "credit_tau": tau,
        "combo_mdd": mdd_c,
        "bh_mdd": mdd_bh,
        "random_p5": p5,
        "bootstrap_point": point,
        "bootstrap_90ci": [lo, hi],
        "criteria": {"c1": crit1, "c2": crit2, "c3": crit3, "pass": passed},
        "n_variants": n_variants,
        "robust_stable": robust_ok,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"RESULTS.md -> {results_path}")
    return 0


def _pct(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "NA"
    return f"{x*100:.2f}%"


def _write_results(
    path: str,
    *,
    bundle: DataBundle,
    seg_df: pd.DataFrame,
    results: Dict[str, Any],
    ffill_df: pd.DataFrame,
    q: float,
    tau: float,
    p5: float,
    boot: Tuple[float, float, float],
    crits: Tuple[bool, bool, bool, bool],
    n_variants: int,
    variant_names: List[str],
    robust_ok: bool,
    robust_mdds: List[float],
    fund_note: str,
    mdds: np.ndarray,
) -> None:
    point, lo, hi = boot
    c1, c2, c3, passed = crits
    combo = results["组合"]
    bh = results["一直持有"]

    lines: List[str] = []
    lines.append("# 固定门槛回测结果（规则验证）")
    lines.append("")
    lines.append(f"生成时间（UTC）：{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("")
    lines.append("复现命令：")
    lines.append("")
    lines.append("```bash")
    lines.append("python -m gate_backtest.run")
    lines.append("```")
    lines.append("")
    lines.append("## 方法说明（随机组与 bootstrap）")
    lines.append("")
    lines.append(
        "- **随机择时零假设组**：随机的是**持仓信号路径**（匹配组合策略的持仓天数占比与平均持仓长度）；"
        "价格与现金收益均为真实序列，不合成价格。"
    )
    lines.append(
        "- **分块 bootstrap**：对策略与一直持有的**真实日收益**做同步分块重采样（块长约 20 日），"
        "估计两者最大回撤差异的 90% 置信区间；不合成价格。"
    )
    lines.append("")
    lines.append("## 数据来源表")
    lines.append("")
    lines.append("| 序列 ID | 来源 URL | 起止日期 | 行数 | 缺失天数 | 缺失日历口径 | 下载时间 | 原样文件 |")
    lines.append("|---|---|---|---:|---:|---|---|---|")
    for m in bundle.meta:
        lines.append(
            f"| {m.series_id} | `{m.source_url}` | {m.start_date} ~ {m.end_date} | {m.n_rows} | "
            f"{m.missing_days} | {m.missing_calendar} | {m.downloaded_at} | `{m.raw_path}` |"
        )
    lines.append("")
    lines.append("缺口说明：缺失天数按上表「缺失日历口径」统计；**未做线性插值**，未生成任何填补数值。")
    if fund_note:
        lines.append(f"- 539002：{fund_note}")
    lines.append("")
    lines.append("### 日历对齐「沿用上一个发布值」统计（相对 SOXX 交易日）")
    lines.append("")
    lines.append("| 序列 | 沿用天数 | 最长连续沿用 | 日历 |")
    lines.append("|---|---:|---:|---|")
    for _, r in ffill_df.iterrows():
        lines.append(
            f"| {r['series_id']} | {r['carry_forward_days']} | {r['max_carry_streak']} | {r['calendar']} |"
        )
    lines.append("")
    lines.append("## BAA10Y 一次性映射（预登记）")
    lines.append("")
    lines.append(f"- 重叠期起点：{C.CREDIT_OVERLAP_START}")
    lines.append(f"- OAS=3.6% 的分位数 **q** = **{q:.6f}**")
    lines.append(f"- BAA10Y 映射阈值 **τ** = **{tau:.6f}**")
    lines.append(f"- 映射数据截止（写死时）：{C.CREDIT_MAPPING_ASOF}")
    if "OAS交叉检查-组合" in results:
        o = results["OAS交叉检查-组合"]
        lines.append(
            f"- OAS 交叉检查（2023-11+ 组合，信用门改用真实 OAS≤3.6%）："
            f"MDD={_pct(o['max_drawdown'])}，年化={_pct(o['ann_return'])}，持仓占比={_pct(o['hold_day_share'])}"
        )
    lines.append("")
    lines.append("## 核心结果表（分段 × 策略）")
    lines.append("")
    lines.append("| 分段 | 策略 | 最大回撤 | 年化收益 | 踏空成本 | 持仓占比 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for _, r in seg_df.iterrows():
        lines.append(
            f"| {r['segment']} | {r['strategy']} | {_pct(r['max_drawdown'])} | {_pct(r['ann_return'])} | "
            f"{_pct(r['missed_opportunity_cost']) if np.isfinite(r['missed_opportunity_cost']) else 'NA'} | "
            f"{_pct(r['hold_day_share'])} |"
        )
    lines.append("")
    lines.append("## 随机组与 bootstrap")
    lines.append("")
    lines.append(f"- 组合策略全样本 MDD = {_pct(combo['max_drawdown'])}")
    lines.append(f"- 随机组 MDD 第 5 百分位 = {_pct(p5)}（n={len(mdds)}，seed={C.RANDOM_SEED}）")
    lines.append(
        f"- 分块 bootstrap：MDD_组合 − MDD_一直持有 = {_pct(point)}，"
        f"90% CI = [{_pct(lo)}, {_pct(hi)}]（block={C.BOOTSTRAP_BLOCK}, n={C.BOOTSTRAP_N}, seed={C.BOOTSTRAP_SEED}）"
    )
    lines.append("")
    lines.append("## 通过标准判定")
    lines.append("")
    lines.append(
        f"1. 组合 MDD 幅度相对一直持有降低 ≥30%："
        f" |MDD_c|={_pct(abs(combo['max_drawdown']))}，|MDD_bh|={_pct(abs(bh['max_drawdown']))} → "
        f"**{'通过' if c1 else '未通过'}**"
    )
    lines.append(
        f"2. 组合 MDD 浅于随机组 P5（mdd_c > p5）：{_pct(combo['max_drawdown'])} vs {_pct(p5)} → "
        f"**{'通过' if c2 else '未通过'}**"
    )
    lines.append(
        f"3. 年化落后一直持有 ≤3pct：组合 {_pct(combo['ann_return'])}，持有 {_pct(bh['ann_return'])}，"
        f"差 {_pct(bh['ann_return']-combo['ann_return'])} → **{'通过' if c3 else '未通过'}**"
    )
    lines.append("")
    lines.append(f"**总结论：{'通过' if passed else '未通过'}**（须三条同时满足）")
    lines.append("")
    lines.append("## 多重比较与稳健性")
    lines.append("")
    lines.append(f"- 共测试门控相关变体 **{n_variants}** 个（含单门、稳健性扰动、SMH、OAS 交叉/基金参考等）。")
    lines.append(f"- 变体列表：{', '.join(variant_names)}")
    lines.append("（报告不单独突出表现最好的变体。）")
    lines.append(
        f"- 阈值 ±10% 稳健性（组合）：变体 MDD={[ _pct(x) for x in robust_mdds]}；"
        f"相对基准是否稳定：**{'稳定' if robust_ok else '不稳定'}**"
    )
    lines.append("")
    lines.append("## 成本假设（539002）")
    lines.append("")
    lines.append("- 申购费 0.16%；每日申购额度 **10000 元**。")
    lines.append(
        "- 赎回分档假设（本环境未核验到完整官方表，故采用常见 QDII 分档假设）："
        "<7 日 1.5%；7–29 日 0.5%；≥30 日 0%。"
    )
    lines.append("")
    lines.append("## 图表文件")
    lines.append("")
    lines.append("- 仓库：`gate_backtest/output/equity_curves.png`")
    lines.append("- 仓库：`gate_backtest/output/drawdowns.png`")
    lines.append("- 仓库：`gate_backtest/output/random_mdd_hist.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/equity_curves.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/drawdowns.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/random_mdd_hist.png`")
    lines.append("")
    lines.append("## 原始数据路径（可核对）")
    lines.append("")
    lines.append("- 仓库：`gate_backtest/data_raw/`")
    lines.append("- artifacts：`/opt/cursor/artifacts/data_raw/`")
    for m in bundle.meta:
        lines.append(f"  - `{m.raw_path}`")
    lines.append("")
    lines.append("## 已知局限")
    lines.append("")
    lines.append("- FRED/Yahoo 节假日未从 bday 缺失统计中剔除，缺失天数为上界。")
    lines.append("- DGS30 预登记剔除 2002–2006；主样本自 2007。")
    lines.append("- BAMLH0A0HYM2 在本下载中自 2023-11 起才有观测，与预登记重叠期一致。")
    lines.append("- 场内成交模型为次日（滞后后当日）开盘全仓切换；未建模滑点以外的冲击成本。")
    lines.append("- 539002 仅为 2024+ 参考，且受每日 1 万元申购额度约束，不可与 SOXX 全样本直接对比。")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
