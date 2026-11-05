"""图表：净值、回撤、随机组 MDD 分布。"""

from __future__ import annotations

import os
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

# 优先使用系统 CJK 字体，避免图中中文缺字
for _font in (
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
):
    try:
        font_manager.fontManager.addfont(_font)
        plt.rcParams["font.sans-serif"] = [
            font_manager.FontProperties(fname=_font).get_name(),
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue


def _ensure(dirpath: str) -> None:
    os.makedirs(dirpath, exist_ok=True)


def plot_equity_curves(
    curves: Dict[str, pd.Series],
    out_path: str,
    title: str = "净值曲线（初始=1）",
) -> str:
    _ensure(os.path.dirname(out_path))
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, s in curves.items():
        if s is None or s.empty:
            continue
        norm = s / s.iloc[0]
        ax.plot(norm.index, norm.values, label=name, linewidth=1.2)
    ax.set_title(title)
    ax.set_ylabel("净值")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_drawdowns(
    curves: Dict[str, pd.Series],
    out_path: str,
    title: str = "回撤",
) -> str:
    _ensure(os.path.dirname(out_path))
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, s in curves.items():
        if s is None or s.empty:
            continue
        peak = s.cummax()
        dd = s / peak - 1.0
        ax.plot(dd.index, dd.values, label=name, linewidth=1.0)
    ax.set_title(title)
    ax.set_ylabel("回撤")
    ax.legend(loc="best", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_random_mdd_hist(
    mdds: np.ndarray,
    strategy_mdd: float,
    p5: float,
    out_path: str,
    title: str = "随机择时组最大回撤分布",
) -> str:
    _ensure(os.path.dirname(out_path))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(mdds, bins=40, color="#4C78A8", alpha=0.85, edgecolor="white")
    ax.axvline(strategy_mdd, color="#E45756", linewidth=2, label=f"策略 MDD={strategy_mdd:.2%}")
    ax.axvline(p5, color="#F58518", linewidth=2, linestyle="--", label=f"随机组 P5={p5:.2%}")
    ax.set_title(title)
    ax.set_xlabel("最大回撤")
    ax.set_ylabel("频数")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
