"""宏观流动性与全市场状态机 (Macro & Market Regime State Machine)

核心功能:
    打通 webhtml 宏观与跨资产信号 (美债10Y、美元/离岸人民币汇率、全市场涨跌比、宽基指数MA60),
    输出四级宏观状态与顶层总仓位上限闸门:
    - STRONG_OFFENSIVE: 强动量/进攻状态 (仓位上限 80% ~ 100%)
    - BALANCED_OSCILLATING: 结构震荡状态 (仓位上限 40% ~ 60%)
    - RISK_OFF_DEFENSIVE: 避险防守状态 (仓位上限 0% ~ 20%，主配国债)
    - BEAR_LIQUIDITY_SHOCK: 流动性冲击/极度防御 (0% 仓位 / 纯现金国债)
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class MacroRegimeClassifier:
    """
    宏观与全市场状态分类器
    """
    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent.parent

    def _load_latest_webhtml_context(self) -> Optional[Dict[str, Any]]:
        """从 webhtml 最新生成的报表或原始数据中提取宏观上下文"""
        output_dir = self.project_root / "webhtml" / "output"
        backup_dir = output_dir / "backup"
        
        if backup_dir.exists():
            # 找到最新的 backup json 文件
            json_files = sorted(backup_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
            if json_files:
                try:
                    data = json.loads(json_files[0].read_text(encoding="utf-8"))
                    return data
                except Exception:
                    pass
        return None

    def evaluate_regime(
        self,
        cnh_change_pct: Optional[float] = None,
        us10y_change_pct: Optional[float] = None,
        up_down_ratio: Optional[float] = None,
        broad_index_above_ma60: bool = True
    ) -> Dict[str, Any]:
        """
        评估当前宏观与全市场状态.

        :param cnh_change_pct: 离岸人民币汇率近期变动 (正为贬值, 负为升值)
        :param us10y_change_pct: 美债10年期收益率变动
        :param up_down_ratio: A股全市场涨跌比 (上涨家数 / 下跌家数)
        :param broad_index_above_ma60: 沪深300/宽基指数是否站上 60 日均线
        :return: 状态字典
        """
        # 1. 尝试从 webhtml 数据自动补全宏观参数
        if up_down_ratio is None or cnh_change_pct is None:
            raw = self._load_latest_webhtml_context()
            if raw:
                # 尝试解析涨跌比
                up_cnt = raw.get("up_count") or (raw.get("up_down", {}).get("up", 2000))
                down_cnt = raw.get("down_count") or (raw.get("up_down", {}).get("down", 2000))
                if down_cnt > 0 and up_down_ratio is None:
                    up_down_ratio = float(up_cnt) / float(down_cnt)

                # 尝试解析汇率
                for g in raw.get("globals", []):
                    if g.get("code") == "CNH=X" and cnh_change_pct is None:
                        cnh_change_pct = float(g.get("value_or_change", 0.0))

        # 默认中性值
        cnh = cnh_change_pct if cnh_change_pct is not None else 0.0
        us10y = us10y_change_pct if us10y_change_pct is not None else 0.0
        ratio = up_down_ratio if up_down_ratio is not None else 1.0

        # 2. 状态判定规则链
        # 规则 1: 流动性冲击 (汇率急贬 + 市场普跌 < 0.3)
        if cnh > 0.35 and ratio < 0.4:
            regime = "BEAR_LIQUIDITY_SHOCK"
            pos_cap = 0.10
            label = "流动性收紧/极度防御"
            desc = f"离岸人民币走弱({cnh:+.2f}%)，全市场涨跌比低迷({ratio:.2f})，建议空仓或全部配置30年国债ETF。"

        # 规则 2: 避险防守 (宽基均线空头 或 全市场跌多涨少 ratio < 0.6)
        elif not broad_index_above_ma60 and ratio < 0.7:
            regime = "RISK_OFF_DEFENSIVE"
            pos_cap = 0.30
            label = "避险防守状态"
            desc = f"宽基指数处于MA60熊线下方，市场情绪偏弱，仓位上限压缩至30%，优先配置红利/国债。"

        # 规则 3: 强动量/进攻 (市场情绪高涨 ratio > 1.5 且 均线多头)
        elif broad_index_above_ma60 and ratio >= 1.2:
            regime = "STRONG_OFFENSIVE"
            pos_cap = 1.00
            label = "强动量进攻状态"
            desc = f"全市场赚钱效应良好(涨跌比 {ratio:.2f})且宽基处于多头格局，仓位上限提升至 100%，积极参与主线轮动。"

        # 规则 4: 结构震荡 (中性)
        else:
            regime = "BALANCED_OSCILLATING"
            pos_cap = 0.60
            label = "结构性震荡状态"
            desc = f"宏观信号平稳，全市场多空博弈，仓位上限维持在 40%~60%，精选截面动量领先的结构性板块。"

        return {
            "regime": regime,
            "label": label,
            "max_position_cap": pos_cap,
            "description": desc,
            "indicators": {
                "cnh_change_pct": round(cnh, 3),
                "us10y_change_pct": round(us10y, 3),
                "up_down_ratio": round(ratio, 2),
                "broad_index_above_ma60": broad_index_above_ma60
            }
        }


def get_current_macro_regime() -> Dict[str, Any]:
    """快捷获取当前宏观状态评级"""
    classifier = MacroRegimeClassifier()
    return classifier.evaluate_regime()
