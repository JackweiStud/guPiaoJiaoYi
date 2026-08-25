"""ETF 标的池与资产大类定义模块 (Universe Definition)

覆盖 A 股全市场核心风格与 Beta 资产大类:
    1. 高弹性科技/成长: 588180 (科创50), 159915 (创业板)
    2. 核心消费/医药: 159843 (食品饮料)
    3. 红利/大金融: 512820 (证券/银行), 512810 (军工)
    4. 海外/全球科技: 513160 (恒生科技)
    5. 防御避风港: 511090 (30年国债 ETF)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
from sdd import load_etf_data

# 核心资产池元数据
DEFAULT_ETF_UNIVERSE = {
    "588180": {
        "name": "科创50 ETF",
        "category": "科技成长",
        "beta_type": "high_growth",
        "is_defensive": False,
    },
    "159915": {
        "name": "创业板 ETF",
        "category": "成长创新",
        "beta_type": "high_growth",
        "is_defensive": False,
    },
    "159843": {
        "name": "食品饮料 ETF",
        "category": "核心消费",
        "beta_type": "consumer",
        "is_defensive": False,
    },
    "512820": {
        "name": "证券/金融 ETF",
        "category": "大金融",
        "beta_type": "financial",
        "is_defensive": False,
    },
    "512810": {
        "name": "军工 ETF",
        "category": "高端制造/周期",
        "beta_type": "cyclical",
        "is_defensive": False,
    },
    "513160": {
        "name": "恒生科技 ETF",
        "category": "海外互联网",
        "beta_type": "global_tech",
        "is_defensive": False,
    },
    "511090": {
        "name": "30年国债 ETF",
        "category": "固定收益避险",
        "beta_type": "defensive_bond",
        "is_defensive": True,
    },
}


def get_universe_info() -> Dict[str, Dict[str, Any]]:
    """获取标的池配置信息"""
    return DEFAULT_ETF_UNIVERSE.copy()


def load_universe_data(
    stock_data_dir: Optional[str] = None,
    codes: Optional[List[str]] = None
) -> Dict[str, pd.DataFrame]:
    """
    加载标的池所有 ETF 的历史日线数据.

    :param stock_data_dir: 数据根目录 (默认当前项目的 stock_data/)
    :param codes: 指定加载的代码列表 (默认为 DEFAULT_ETF_UNIVERSE 全部代码)
    :return: {symbol: df} 字典
    """
    if stock_data_dir is None:
        project_root = Path(__file__).resolve().parent.parent.parent
        stock_data_dir = str(project_root / "stock_data")

    target_codes = codes or list(DEFAULT_ETF_UNIVERSE.keys())
    universe_dfs: Dict[str, pd.DataFrame] = {}

    for code in target_codes:
        clean_code = code.split(".")[0]
        csv_path = os.path.join(stock_data_dir, clean_code, f"{clean_code}_Day.csv")
        if os.path.exists(csv_path):
            try:
                df = load_etf_data(csv_path)
                if not df.empty and len(df) >= 30:
                    universe_dfs[clean_code] = df
            except Exception as e:
                print(f"[Universe] 加载 {clean_code} 失败: {e}")
        else:
            # 兼容直接存放在 stock_data 下的情况
            alt_path = os.path.join(stock_data_dir, f"{clean_code}_Day.csv")
            if os.path.exists(alt_path):
                try:
                    df = load_etf_data(alt_path)
                    if not df.empty and len(df) >= 30:
                        universe_dfs[clean_code] = df
                except Exception:
                    pass

    return universe_dfs
