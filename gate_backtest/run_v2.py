"""v2 复现入口：python -m gate_backtest.run_v2

不破坏 v1：`python -m gate_backtest.run` 仍跑 v1。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from gate_backtest import constants as C
from gate_backtest.backtest import (
    build_at_least_n_position,
    build_scaled_position,
    daily_cash_return_from_dgs3mo,
    run_buy_and_hold,
    run_fund_backtest,
    run_listed_backtest,
    run_monthly_dca,
)
from gate_backtest.bootstrap import mdd_diff_block_bootstrap
from gate_backtest.data import align_asof, copy_raw_to_artifacts, load_all
from gate_backtest.gates import credit_gate, oil_gate, rate_absolute_gate, rate_gate
from gate_backtest.metrics import (
    avg_holding_length,
    missed_opportunity_cost,
    summarize_equity,
)
from gate_backtest.null_random import random_timing_mdds
from gate_backtest.plotting import plot_drawdowns, plot_equity_curves, plot_random_mdd_hist

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_v2")
ARTIFACTS = "/opt/cursor/artifacts"

# v1 全样本组合（对照写死，不改）
V1_COMBO_MDD = -0.2572
V1_COMBO_ANN = 0.0378
V1_COMBO_HOLD = 0.0789


def _require_frozen_v2() -> Tuple[float, float, float]:
    q = C.CREDIT_Q_V2
    tau = C.CREDIT_BAA_THRESHOLD_V2
    tau_rate = C.RATE_ABS_THRESHOLD_V2
    if q is None or tau is None or tau_rate is None:
        raise SystemExit("v2 阈值尚未写死：CREDIT_Q_V2 / CREDIT_BAA_THRESHOLD_V2 / RATE_ABS_THRESHOLD_V2")
    return float(q), float(tau), float(tau_rate)


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


def _eval_scaled(
    name: str,
    ohlcv: pd.DataFrame,
    gates: Sequence[pd.Series],
    cash_daily: pd.Series,
    asset_rets: pd.Series,
) -> Dict[str, Any]:
    pos, cdays, mstreak = build_scaled_position(gates, ohlcv.index)
    return _eval_from_position(name, ohlcv, pos, cash_daily, asset_rets, cdays, mstreak)


def _eval_at_least(
    name: str,
    ohlcv: pd.DataFrame,
    gates: Sequence[pd.Series],
    cash_daily: pd.Series,
    asset_rets: pd.Series,
    n_min: int = C.AT_LEAST_GATES_SWITCH,
) -> Dict[str, Any]:
    pos, cdays, mstreak = build_at_least_n_position(gates, ohlcv.index, n_min=n_min)
    return _eval_from_position(name, ohlcv, pos, cash_daily, asset_rets, cdays, mstreak)


def _segment_stats(equity: pd.Series, position: pd.Series, returns: pd.Series) -> Dict[str, float]:
    if equity is None or equity.empty or len(equity) < 5:
        return {
            "max_drawdown": float("nan"),
            "ann_return": float("nan"),
            "hold_day_share": float("nan"),
            "exposure_share": float("nan"),
        }
    eq = equity / equity.iloc[0]
    base = summarize_equity(eq, position.reindex(eq.index), returns.reindex(eq.index))
    return {
        "max_drawdown": base["max_drawdown"],
        "ann_return": base["ann_return"],
        "hold_day_share": base["hold_day_share"],
        "exposure_share": base["exposure_share"],
    }


def _robust_stable(base_mdd: float, variants: List[float], tol_ratio: float = 0.25) -> bool:
    if not np.isfinite(base_mdd) or abs(base_mdd) < 1e-12:
        return False
    for v in variants:
        if not np.isfinite(v):
            return False
        if abs(v - base_mdd) / abs(base_mdd) > tol_ratio:
            return False
    return True


def _pct(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "NA"
    return f"{x * 100:.2f}%"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS, exist_ok=True)

    refresh = "--refresh" in argv
    print("== v2：加载真实数据（默认复用 data_raw；--refresh 强制重下）==")
    bundle = load_all(prefer_raw=not refresh)
    copied = copy_raw_to_artifacts(os.path.join(ARTIFACTS, "data_raw"))
    print(f"data_raw -> artifacts: {len(copied)} files")

    q, tau, tau_rate = _require_frozen_v2()
    tau_v1 = float(C.CREDIT_BAA_THRESHOLD)
    print(f"写死映射: q={q}, tau_v2={tau}, tau_v1={tau_v1}, tau_rate={tau_rate}")

    soxx = bundle.prices["SOXX"].copy()
    soxx = soxx.loc[soxx.index >= pd.Timestamp(C.SAMPLE_START)]
    smh = bundle.prices["SMH"].copy()
    smh = smh.loc[smh.index >= pd.Timestamp(C.SAMPLE_START)]

    cash_daily = daily_cash_return_from_dgs3mo(bundle.fred["DGS3MO"])
    asset_rets = _asset_returns(soxx)

    g_oil = oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD, C.OIL_STREAK_DAYS)
    g_rate_ma = rate_gate(bundle.fred["DGS30"], C.RATE_MA_WINDOW, band=0.0)
    g_rate_abs = rate_absolute_gate(bundle.fred["DGS30"], tau_rate)
    g_credit_new = credit_gate(bundle.fred["BAA10Y"], tau)
    g_credit_v1 = credit_gate(bundle.fred["BAA10Y"], tau_v1)

    results: Dict[str, Dict[str, Any]] = {}

    # ---- 固定矩阵 ----
    results["主"] = _eval_scaled(
        "主", soxx, [g_oil, g_rate_abs, g_credit_new], cash_daily, asset_rets
    )
    results["对照A"] = _eval_scaled(
        "对照A", soxx, [g_oil, g_rate_ma, g_credit_new], cash_daily, asset_rets
    )
    results["对照B"] = _eval_scaled(
        "对照B", soxx, [g_oil, g_rate_abs, g_credit_v1], cash_daily, asset_rets
    )
    results["对照C"] = _eval_at_least(
        "对照C", soxx, [g_oil, g_rate_abs, g_credit_new], cash_daily, asset_rets
    )
    results["对照D"] = _eval_at_least(
        "对照D", soxx, [g_oil, g_rate_ma, g_credit_new], cash_daily, asset_rets
    )

    # 额外：仓位缩放 + v1 τ + MA20（便于四条对照；不计入通过标准）
    results["缩放+v1τ+MA20"] = _eval_scaled(
        "缩放+v1τ+MA20", soxx, [g_oil, g_rate_ma, g_credit_v1], cash_daily, asset_rets
    )

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

    # 稳健性 ±10%（主策略路径）
    robust_specs = [
        (
            "油价-10%",
            [
                oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD * 0.9, C.OIL_STREAK_DAYS),
                g_rate_abs,
                g_credit_new,
            ],
        ),
        (
            "油价+10%",
            [
                oil_gate(bundle.fred["DCOILBRENTEU"], C.OIL_THRESHOLD * 1.1, C.OIL_STREAK_DAYS),
                g_rate_abs,
                g_credit_new,
            ],
        ),
        (
            "利率绝对-10%",
            [g_oil, rate_absolute_gate(bundle.fred["DGS30"], tau_rate * 0.9), g_credit_new],
        ),
        (
            "利率绝对+10%",
            [g_oil, rate_absolute_gate(bundle.fred["DGS30"], tau_rate * 1.1), g_credit_new],
        ),
        (
            "信用-10%",
            [g_oil, g_rate_abs, credit_gate(bundle.fred["BAA10Y"], tau * 0.9)],
        ),
        (
            "信用+10%",
            [g_oil, g_rate_abs, credit_gate(bundle.fred["BAA10Y"], tau * 1.1)],
        ),
    ]
    robust_mdds: List[float] = []
    for rname, gates in robust_specs:
        st = _eval_scaled(f"稳健-{rname}", soxx, gates, cash_daily, asset_rets)
        results[f"稳健-{rname}"] = st
        robust_mdds.append(st["max_drawdown"])

    results["SMH-主"] = _eval_scaled(
        "SMH-主", smh, [g_oil, g_rate_abs, g_credit_new], cash_daily, _asset_returns(smh)
    )

    fund_note = ""
    if bundle.fund_nav is not None:
        nav = bundle.fund_nav.loc[bundle.fund_nav.index >= pd.Timestamp("2024-01-01")]
        if len(nav) > 5:
            pos, cdays, mstreak = build_scaled_position(
                [g_oil, g_rate_abs, g_credit_new], nav.index
            )
            fund_pf = run_fund_backtest(nav, (pos > 0).astype(float), cash_daily, daily_subscribe_limit=10_000.0)
            # 场外参考：分数仓位按「是否>0」触发申购额度逻辑会失真；改为按目标暴露近似：
            # 仍用 at-least 风格不合适。这里用缩放仓位直接作为目标权重不可行（日限额）。
            # 按 PREREG：539002 只作参考；用「仓位>0 即尝试申购」并注明局限。
            results["539002-主参考"] = {
                "name": "539002-主参考",
                **summarize_equity(fund_pf["total"], pos, fund_pf["returns"]),
                "missed_opportunity_cost": float("nan"),
                "equity": fund_pf["total"],
                "returns": fund_pf["returns"],
                "position": pos,
                "carry_forward_days": cdays,
                "max_carry_streak": mstreak,
            }
            fund_note = (
                "539002 参考：日申购额度 1 万元下，缩放目标仓位无法精确跟踪；"
                "实现上在目标仓位>0 的交易日按额度申购（近似暴露），不可与 SOXX 直接对比。"
            )
        else:
            fund_note = "539002 在 2024+ 有效净值过少"
    else:
        fund_note = "539002 净值未能加载：" + str(bundle.gaps.get("539002"))

    # 随机择时（对主策略：匹配平均暴露与平均持仓长度）
    main = results["主"]
    print("== 随机择时零假设（1000 条，匹配平均暴露与持仓长度）==")
    mdds, p5 = random_timing_mdds(
        soxx,
        cash_daily,
        hold_share=main["hold_day_share"],
        avg_len=main["avg_hold_len"],
        n_paths=C.N_RANDOM_PATHS,
        seed=C.RANDOM_SEED,
        mean_exposure=main["exposure_share"],
    )
    np.save(os.path.join(OUT_DIR, "random_mdds_v2.npy"), mdds)

    print("== 分块 bootstrap（主策略 vs 一直持有）==")
    point, lo, hi, _ = mdd_diff_block_bootstrap(
        main["returns"],
        results["一直持有"]["returns"],
        block=C.BOOTSTRAP_BLOCK,
        n_boot=C.BOOTSTRAP_N,
        seed=C.BOOTSTRAP_SEED,
    )

    # 分段表（矩阵核心 + 基准）
    segment_rows = []
    strategy_names_main = ["主", "对照A", "对照B", "对照C", "对照D", "一直持有", "每月定投"]
    for seg_name, (seg_start, seg_end) in C.SEGMENTS.items():
        for sname in strategy_names_main:
            st = results[sname]
            eq = st["equity"].loc[seg_start:seg_end]
            pos = st["position"].reindex(eq.index)
            rets = st["returns"].reindex(eq.index)
            base = _segment_stats(eq, pos, rets)
            if sname not in ("一直持有", "每月定投"):
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
                    "exposure_share": base["exposure_share"],
                    "missed_opportunity_cost": miss,
                }
            )
    seg_df = pd.DataFrame(segment_rows)

    # 通过标准（仅主策略）
    mdd_c = main["max_drawdown"]
    mdd_bh = results["一直持有"]["max_drawdown"]
    crit1 = abs(mdd_c) <= 0.70 * abs(mdd_bh) if abs(mdd_bh) > 0 else False
    crit2 = mdd_c > p5
    ann_c = main["ann_return"]
    ann_bh = results["一直持有"]["ann_return"]
    crit3 = (ann_bh - ann_c) <= 0.03 + 1e-12
    passed = bool(crit1 and crit2 and crit3)

    variant_names = [n for n in results if n not in ("一直持有", "每月定投")]
    n_variants = len(variant_names)
    robust_ok = _robust_stable(main["max_drawdown"], robust_mdds)

    ffill_rows = []
    for sid, series in bundle.fred.items():
        _, cdays, mstreak = align_asof(series, soxx.index)
        ffill_rows.append(
            {"series_id": sid, "carry_forward_days": cdays, "max_carry_streak": mstreak, "calendar": "SOXX 交易日"}
        )
    for ticker in bundle.prices:
        ffill_rows.append(
            {
                "series_id": ticker,
                "carry_forward_days": 0,
                "max_carry_streak": 0,
                "calendar": "自身交易日（无需沿用）",
            }
        )
    ffill_df = pd.DataFrame(ffill_rows)

    curves = {
        "主": main["equity"],
        "对照A": results["对照A"]["equity"],
        "对照B": results["对照B"]["equity"],
        "对照C": results["对照C"]["equity"],
        "对照D": results["对照D"]["equity"],
        "一直持有": results["一直持有"]["equity"],
        "每月定投": results["每月定投"]["equity"],
    }
    p1 = plot_equity_curves(curves, os.path.join(OUT_DIR, "equity_curves_v2.png"), title="v2 净值曲线（初始=1）")
    p2 = plot_drawdowns(curves, os.path.join(OUT_DIR, "drawdowns_v2.png"), title="v2 回撤")
    p3 = plot_random_mdd_hist(
        mdds,
        main["max_drawdown"],
        p5,
        os.path.join(OUT_DIR, "random_mdd_hist_v2.png"),
        title="v2 随机择时组最大回撤分布（主策略）",
    )
    for p in (p1, p2, p3):
        shutil.copy2(p, os.path.join(ARTIFACTS, os.path.basename(p)))

    results_path = os.path.join(ROOT, "RESULTS_v2.md")
    _write_results_v2(
        results_path,
        bundle=bundle,
        seg_df=seg_df,
        results=results,
        ffill_df=ffill_df,
        q=q,
        tau=tau,
        tau_v1=tau_v1,
        tau_rate=tau_rate,
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
    shutil.copy2(results_path, os.path.join(ARTIFACTS, "RESULTS_v2.md"))

    summary = {
        "credit_q_v2": q,
        "credit_tau_v2": tau,
        "credit_tau_v1": tau_v1,
        "tau_rate": tau_rate,
        "main_mdd": mdd_c,
        "bh_mdd": mdd_bh,
        "main_ann": ann_c,
        "bh_ann": ann_bh,
        "main_hold": main["hold_day_share"],
        "main_exposure": main["exposure_share"],
        "random_p5": p5,
        "bootstrap_point": point,
        "bootstrap_90ci": [lo, hi],
        "criteria": {"c1": crit1, "c2": crit2, "c3": crit3, "pass": passed},
        "n_variants": n_variants,
        "robust_stable": robust_ok,
        "matrix": {
            k: {
                "mdd": results[k]["max_drawdown"],
                "ann": results[k]["ann_return"],
                "hold": results[k]["hold_day_share"],
                "exposure": results[k]["exposure_share"],
                "miss": results[k]["missed_opportunity_cost"],
            }
            for k in ("主", "对照A", "对照B", "对照C", "对照D", "一直持有", "每月定投")
        },
    }
    with open(os.path.join(OUT_DIR, "summary_v2.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"RESULTS_v2.md -> {results_path}")
    return 0


def _write_results_v2(
    path: str,
    *,
    bundle,
    seg_df: pd.DataFrame,
    results: Dict[str, Any],
    ffill_df: pd.DataFrame,
    q: float,
    tau: float,
    tau_v1: float,
    tau_rate: float,
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
    main = results["主"]
    bh = results["一直持有"]

    lines: List[str] = []
    lines.append("# 固定门槛回测结果 v2（规则验证）")
    lines.append("")
    lines.append(f"生成时间（UTC）：{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("")
    lines.append("复现命令：")
    lines.append("")
    lines.append("```bash")
    lines.append("python -m gate_backtest.run_v2")
    lines.append("# v1 入口仍为：python -m gate_backtest.run")
    lines.append("```")
    lines.append("")
    lines.append("## 方法说明")
    lines.append("")
    lines.append(
        "- **主策略**：按开了几道门定仓位（3/2/1/0 → 100%/66%/33%/0%），"
        "信用门用新 τ，利率门用 DGS30 绝对水平（中位数 τ_rate）。"
    )
    lines.append(
        "- **仓位缩放计费**：按目标仓位与当前仓位的差额名义调仓，每次对 |Δ| 计 0.1% 单边费；未持仓现金按 DGS3MO 计息。"
    )
    lines.append(
        "- **随机择时零假设**：随机的是信号路径；匹配主策略的**平均暴露**与**平均持仓长度**；价格与现金收益真实。"
    )
    lines.append(
        "- **分块 bootstrap**：对主策略与一直持有的真实日收益同步分块重采样（块长约 20 日），"
        "估计最大回撤差异的 90% CI。"
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
    lines.append(
        "- BAMLH0A0HYM2：本环境 FRED 公开 CSV 再拉仍仅自 2023-11-06 起有观测；以此为 OAS「可得期」算 q。"
    )
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
    lines.append("## 一次性写死阈值（预登记）")
    lines.append("")
    lines.append(f"- OAS 可得期：{C.CREDIT_OAS_AVAIL_START_V2} ~ {C.CREDIT_OAS_AVAIL_END_V2}（n={C.CREDIT_OAS_N_V2}）")
    lines.append(f"- OAS=3.6% 的分位数 **q** = **{q:.12f}**")
    lines.append(
        f"- 2007+ BAA10Y 第 q 分位 **τ** = **{tau:.12f}**"
        f"（样本 {C.CREDIT_BAA_SAMPLE_START_V2} ~ {C.CREDIT_BAA_SAMPLE_END_V2}，n={C.CREDIT_BAA_N_V2}）"
    )
    lines.append(f"- v1 对照 τ = **{tau_v1}**（差异：新 τ − v1 τ = {tau - tau_v1:.6f}）")
    lines.append(
        f"- 利率绝对水平 **τ_rate** = **{tau_rate}**"
        f"（2007+ DGS30 中位数；样本 {C.RATE_ABS_SAMPLE_START_V2} ~ {C.RATE_ABS_SAMPLE_END_V2}，n={C.RATE_ABS_N_V2}）"
    )
    lines.append(f"- 映射数据截止：{C.CREDIT_MAPPING_ASOF_V2}")
    lines.append("")
    lines.append("## 核心对照表（全样本）")
    lines.append("")
    lines.append(
        "| 策略 | 规则摘要 | 最大回撤 | 年化 | 踏空成本 | 持仓占比 | 暴露占比 | vs v1组合 MDD | vs v1组合 年化 | vs 一直持有 MDD降幅 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    matrix_desc = {
        "主": "缩放 + 新τ + 利率绝对",
        "对照A": "缩放 + 新τ + 利率MA20",
        "对照B": "缩放 + v1τ=1.8 + 利率绝对",
        "对照C": "至少2门 + 新τ + 利率绝对",
        "对照D": "至少2门 + 新τ + 利率MA20",
        "一直持有": "基准",
        "每月定投": "基准",
        "缩放+v1τ+MA20": "缩放 + v1τ + MA20（附加）",
    }
    for sname in ("主", "对照A", "对照B", "对照C", "对照D", "缩放+v1τ+MA20", "一直持有", "每月定投"):
        st = results[sname]
        mdd = st["max_drawdown"]
        ann = st["ann_return"]
        vs_v1_mdd = mdd - V1_COMBO_MDD
        vs_v1_ann = ann - V1_COMBO_ANN
        if abs(bh["max_drawdown"]) > 0 and sname not in ("一直持有", "每月定投"):
            mdd_reduce = 1.0 - abs(mdd) / abs(bh["max_drawdown"])
        else:
            mdd_reduce = float("nan")
        lines.append(
            f"| {sname} | {matrix_desc[sname]} | {_pct(mdd)} | {_pct(ann)} | "
            f"{_pct(st['missed_opportunity_cost']) if np.isfinite(st['missed_opportunity_cost']) else 'NA'} | "
            f"{_pct(st['hold_day_share'])} | {_pct(st['exposure_share'])} | "
            f"{_pct(vs_v1_mdd)} | {_pct(vs_v1_ann)} | "
            f"{_pct(mdd_reduce) if np.isfinite(mdd_reduce) else 'NA'} |"
        )
    lines.append("")
    lines.append(
        f"v1 组合写死对照：MDD={_pct(V1_COMBO_MDD)}，年化={_pct(V1_COMBO_ANN)}，持仓={_pct(V1_COMBO_HOLD)}。"
    )
    lines.append("")
    lines.append("## 分段结果（矩阵 × 分段）")
    lines.append("")
    lines.append("| 分段 | 策略 | 最大回撤 | 年化收益 | 踏空成本 | 持仓占比 | 暴露占比 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for _, r in seg_df.iterrows():
        lines.append(
            f"| {r['segment']} | {r['strategy']} | {_pct(r['max_drawdown'])} | {_pct(r['ann_return'])} | "
            f"{_pct(r['missed_opportunity_cost']) if np.isfinite(r['missed_opportunity_cost']) else 'NA'} | "
            f"{_pct(r['hold_day_share'])} | {_pct(r['exposure_share'])} |"
        )
    lines.append("")
    lines.append("## 随机组与 bootstrap（主策略）")
    lines.append("")
    lines.append(f"- 主策略全样本 MDD = {_pct(main['max_drawdown'])}")
    lines.append(
        f"- 主策略平均暴露 = {_pct(main['exposure_share'])}，持仓占比 = {_pct(main['hold_day_share'])}，"
        f"平均持仓长度 = {main['avg_hold_len']:.2f} 日"
    )
    lines.append(f"- 随机组 MDD 第 5 百分位 = {_pct(p5)}（n={len(mdds)}，seed={C.RANDOM_SEED}）")
    lines.append(
        f"- 分块 bootstrap：MDD_主 − MDD_一直持有 = {_pct(point)}，"
        f"90% CI = [{_pct(lo)}, {_pct(hi)}]（block={C.BOOTSTRAP_BLOCK}, n={C.BOOTSTRAP_N}, seed={C.BOOTSTRAP_SEED}）"
    )
    lines.append("")
    lines.append("## 通过标准判定（仅主策略；标准与 v1 相同）")
    lines.append("")
    lines.append(
        f"1. 主策略 MDD 幅度相对一直持有降低 ≥30%："
        f" |MDD_c|={_pct(abs(main['max_drawdown']))}，|MDD_bh|={_pct(abs(bh['max_drawdown']))} → "
        f"**{'通过' if c1 else '未通过'}**"
    )
    lines.append(
        f"2. 主策略 MDD 浅于随机组 P5（mdd_c > p5）：{_pct(main['max_drawdown'])} vs {_pct(p5)} → "
        f"**{'通过' if c2 else '未通过'}**"
    )
    lines.append(
        f"3. 年化落后一直持有 ≤3pct：主 {_pct(main['ann_return'])}，持有 {_pct(bh['ann_return'])}，"
        f"差 {_pct(bh['ann_return'] - main['ann_return'])} → **{'通过' if c3 else '未通过'}**"
    )
    lines.append("")
    lines.append(f"**总结论：{'通过' if passed else '未通过'}**（须三条同时满足）")
    lines.append("")
    lines.append("## 多重比较与稳健性")
    lines.append("")
    lines.append(f"- 共测试门控相关变体 **{n_variants}** 个（含矩阵、稳健性、SMH、基金参考等）。")
    lines.append(f"- 变体列表：{', '.join(variant_names)}")
    lines.append("（报告不单独突出表现最好的变体。）")
    lines.append(
        f"- 阈值 ±10% 稳健性（主策略）：变体 MDD={[ _pct(x) for x in robust_mdds]}；"
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
    lines.append("- 仓库：`gate_backtest/output_v2/equity_curves_v2.png`")
    lines.append("- 仓库：`gate_backtest/output_v2/drawdowns_v2.png`")
    lines.append("- 仓库：`gate_backtest/output_v2/random_mdd_hist_v2.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/equity_curves_v2.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/drawdowns_v2.png`")
    lines.append("- artifacts：`/opt/cursor/artifacts/random_mdd_hist_v2.png`")
    lines.append("")
    lines.append("## 原始数据路径（可核对）")
    lines.append("")
    lines.append("- 仓库：`gate_backtest/data_raw/`（复用 v1 归档）")
    lines.append("- artifacts：`/opt/cursor/artifacts/data_raw/`")
    for m in bundle.meta:
        lines.append(f"  - `{m.raw_path}`")
    lines.append("")
    lines.append("## 已知局限")
    lines.append("")
    lines.append("- FRED/Yahoo 节假日未从 bday 缺失统计中剔除，缺失天数为上界。")
    lines.append("- DGS30 预登记剔除 2002–2006；主样本自 2007。")
    lines.append("- BAMLH0A0HYM2 在本环境仅自 2023-11 起有观测；q 基于该可得期，再映射到 2007+ BAA10Y。")
    lines.append("- 分数仓位按开盘差额调仓；手续费从现金扣除，实际权重可能略偏离目标。")
    lines.append("- 539002 仅为 2024+ 参考，且受每日 1 万元申购额度约束，不可与 SOXX 全样本直接对比。")
    lines.append("- 通过标准仅对「主」策略判定；对照 A/B/C/D 只做对照，不另改标准。")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
