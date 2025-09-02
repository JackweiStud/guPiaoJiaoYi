"""数据获取模块(fetcher)

首期实现策略：
- 优先尝试通过 akshare 获取核心快照；
- 若获取失败或依赖缺失，返回本地 mock 数据（保证页面可生成）。

返回数据为"原始数据字典"，供 analysis.calculator 处理为模板字段。
"""

from __future__ import annotations

from typing import Dict, Any, List
from datetime import datetime

try:
    import akshare as ak  # type: ignore
except Exception:  # noqa: BLE001
    ak = None  # 允许在无 akshare 环境下运行（mock）


def _mock_raw_data() -> Dict[str, Any]:
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "indexes": [
            {"name": "上证指数", "code": "sh000001", "close": 3100.50, "change_pct": 1.20, "turnover_billion": 4500},
            {"name": "创业板指", "code": "sz399006", "close": 2250.10, "change_pct": -0.50, "turnover_billion": 2300},
            {"name": "科创50指", "code": "sh000688", "close": 1050.80, "change_pct": 2.80, "turnover_billion": 1200},
        ],
        "up_down": {"up": 3500, "down": 1500},
        "styles": [
            {"category": "大规模/价值", "name": "上证50ETF", "code": "510050", "change_pct": 1.5},
            {"category": "大规模/价值", "name": "沪深300ETF", "code": "510300", "change_pct": 1.2},
            {"category": "大规模/价值", "name": "红利ETF", "code": "510880", "change_pct": 0.8},
            {"category": "大规模/价值", "name": "科创50ETF", "code": "588000", "change_pct": 2.8},
            {"category": "中小规模/成长", "name": "中证500ETF", "code": "510500", "change_pct": 0.5},
            {"category": "中小规模/成长", "name": "中证1000ETF", "code": "159845", "change_pct": -0.2},
            {"category": "中小规模/成长", "name": "科创100ETF", "code": "588190", "change_pct": 1.9},
        ],
        "sectors": [
            {"etf_name": "券商ETF", "code": "512000", "change_pct": 5.2, "leaders": [
                {"name": "中信证券", "change_pct": 7.12},
                {"name": "东方财富", "change_pct": 6.53},
            ]},
            {"etf_name": "芯片ETF", "code": "512760", "change_pct": 4.1, "leaders": [
                {"name": "中芯国际", "change_pct": 4.51},
                {"name": "北方华创", "change_pct": 5.23},
            ]},
            {"etf_name": "人工智能AI ETF", "code": "560800", "change_pct": 3.5, "leaders": [
                {"name": "科大讯飞", "change_pct": 5.89},
                {"name": "浪潮信息", "change_pct": 6.14},
            ]},
            {"etf_name": "软件ETF", "code": "159852", "change_pct": 2.8, "leaders": [
                {"name": "金山办公", "change_pct": 4.05},
            ]},
            {"etf_name": "新能源车ETF", "code": "159806", "change_pct": 1.2, "leaders": [
                {"name": "宁德时代", "change_pct": 1.88},
                {"name": "比亚迪", "change_pct": 2.15},
            ]},
            {"etf_name": "保险主题ETF", "code": "512000", "change_pct": 1.1, "leaders": [
                {"name": "中国平安", "change_pct": 1.5},
            ]},
            {"etf_name": "银行ETF", "code": "512800", "change_pct": 0.9, "leaders": [
                {"name": "招商银行", "change_pct": 1.2},
            ]},
            {"etf_name": "有色金属ETF", "code": "512400", "change_pct": 0.7, "leaders": [
                {"name": "紫金矿业", "change_pct": 1.3},
            ]},
            {"etf_name": "煤炭ETF", "code": "515220", "change_pct": -0.3, "leaders": [
                {"name": "中国神华", "change_pct": 1.01},
            ]},
            {"etf_name": "消费ETF", "code": "159928", "change_pct": -0.8, "leaders": [
                {"name": "贵州茅台", "change_pct": 2.03},
            ]},
            {"etf_name": "食品饮料ETF", "code": "159843", "change_pct": -1.5, "leaders": [
                {"name": "五粮液", "change_pct": -1.2},
                {"name": "泸州老窖", "change_pct": -1.8},
            ]},
            {"etf_name": "医药ETF", "code": "512010", "change_pct": -1.9, "leaders": [
                {"name": "恒瑞医药", "change_pct": -3.05},
                {"name": "药明康德", "change_pct": -2.81},
            ]},
            {"etf_name": "医疗ETF", "code": "159828", "change_pct": -2.1, "leaders": [
                {"name": "迈瑞医疗", "change_pct": -2.5},
                {"name": "爱尔眼科", "change_pct": -3.1},
            ]},
        ],
        "risks": [
            {"category": "国内避险", "name": "黄金ETF", "code": "518880", "value_or_change": -0.5, "interpretation": "市场风险偏好提升"},
            {"category": "国内安全", "name": "30年国债ETF", "code": "511260", "value_or_change": -0.1, "interpretation": "资金流向风险资产"},
            {"category": "全球避险", "name": "COMEX黄金", "code": "GLOBAL_COMEX_GOLD", "value_or_change": -0.8, "interpretation": "避险情绪降温"},
            {"category": "全球风险锚", "name": "10年期美债收益率", "code": "US10Y", "value_or_change": 4.25, "interpretation": "对高估值成长股构成潜在压力"},
            {"category": "做多A股", "name": "YINN富时3倍做多中国", "code": "YINN", "value_or_change": 41.25, "interpretation": "外资看多看空"},
        ],
        "globals": [
            {"category": "关联圈 (香港)", "indicator": "恒生指数", "code": "HSI", "value_or_change": 1.5, "interpretation": "市场情绪联动"},
            {"category": "关联圈 (香港)", "indicator": "恒生科技指数", "code": "HSTECH", "value_or_change": 2.5, "interpretation": "与A股科技板块形成共振"},
            {"category": "环境圈 (美股)", "indicator": "标普500", "code": "^GSPC", "value_or_change": 1.1, "interpretation": "全球风险偏好向好"},
            {"category": "环境圈 (美股)", "indicator": "纳斯达克100", "code": "^NDX", "value_or_change": 1.8, "interpretation": "利好A股科技股开盘"},
            {"category": "环境圈 (美股)", "indicator": "英伟达(NVDA)", "code": "NVDA", "value_or_change": 4.5, "interpretation": "AI与半导体情绪高涨"},
            {"category": "环境圈 (美股)", "indicator": "金龙中国指数", "code": "PGJ", "value_or_change": 3.0, "interpretation": "提振中概股相关板块情绪"},
            {"category": "环境圈 (其他)", "indicator": "美元/离岸CNH", "code": "USDCNH", "value_or_change": -0.3, "interpretation": "人民币升值，利好外资流入"},
            {"category": "环境圈 (加密货币)", "indicator": "比特币 (BTC)", "code": "BTCUSDT", "value_or_change": 3.5, "interpretation": "全球投机情绪回暖"},
            {"category": "环境圈 (加密货币)", "indicator": "以太坊 (ETH)", "code": "ETHUSDT", "value_or_change": 4.2, "interpretation": "高风险偏好资产表现强势"},
        ],
        "_source": "mock",
    }


def fetch_all_data() -> Dict[str, Any]:
    """获取全部原始数据。若失败返回 mock。"""
    # 现阶段直接返回 mock，后续可逐步替换为 akshare 实时数据
    return _mock_raw_data()


