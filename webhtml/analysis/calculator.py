"""数据计算模块(calculator)

将 fetcher 的原始数据转换为模板渲染所需结构：
- 格式化涨跌幅显示(+/-X.XX%)与颜色类
- 行业/主题排序与Top/Bottom高亮
"""

from __future__ import annotations

from typing import Dict, Any, List


def _pct_to_str(p: float) -> str:
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.2f}%"


def _class_by_value(v: float) -> str:
    return "positive" if v >= 0 else "negative"


def build_report_view(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    将原始市场数据转换为HTML模板渲染所需的结构化数据
    输入：raw - 包含市场指数、涨跌统计、风格、行业、风险指标、全球市场等原始数据
    输出：格式化后的数据字典，包含涨跌幅显示格式、颜色类、排序高亮等模板渲染所需字段
    """
    result: Dict[str, Any] = {
        "report_date": raw.get("date"),
        "current_year": raw.get("date", "0000")[:4],
        "ai_summary": "(AI未开启)",
    }

    # A股市场温度
    # 构建A股市场温度（指数）部分
    # 遍历原始数据中的indexes列表，将每个指数的名称、收盘价、涨跌幅格式化字符串、颜色类、成交额等字段提取并格式化，供模板渲染使用
    indexes = []
    for item in raw.get("indexes", []):
        indexes.append({
            "name": item["name"],  # 指数名称
            "close": f"{item['close']:.2f}",  # 收盘价，保留两位小数
            "change_class": _class_by_value(item["change_pct"]),  # 涨跌幅对应的颜色类
            "change_pct_str": _pct_to_str(item["change_pct"]),    # 涨跌幅格式化字符串（带正负号和百分号）
            "turnover_billion": f"{item['turnover_billion']}",    # 成交额（亿元）
        })
    result["indexes"] = indexes
    
    # 构建A股市场温度（涨跌家数）部分
    # 遍历原始数据中的up_down列表，将每个涨跌家数、活跃度、标签等字段提取并格式化，供模板渲染使用
    up_down = raw.get("up_down", {"up": 0, "down": 0})
    up_count = up_down.get("up", 0)
    down_count = up_down.get("down", 0)
    total_count = up_count + down_count
    
    # 判断逻辑：当up占比超过(up+down)的80%为普涨；当down占比超过(up+down)的80%为普跌；其他为分化
    if total_count > 0:
        up_ratio = up_count / total_count
        down_ratio = down_count / total_count
        if up_ratio > 0.8:
            label = "普涨"
        elif down_ratio > 0.8:
            label = "普跌"
        else:
            label = "分化"
    else:
        label = "分化"

    result["up_down"] = {
        "up": up_down.get("up", 0), 
        "down": up_down.get("down", 0), 
        "activityPct": up_down.get("activityPct", "0.0%"),
        "label": label, 
        "class": _class_by_value(up_down.get("up", 0) - up_down.get("down", 0))
    }

    # 市场风格与规模（分组）
    groups: Dict[str, List[dict]] = {}
    for it in raw.get("styles", []):
        groups.setdefault(it["category"], []).append(it)
    styles_groups = []
    for cat, items in groups.items():
        view_items = []
        for it in items:
            view_items.append({
                "name": it["name"],
                "code": it["code"],
                "change_class": _class_by_value(it["change_pct"]),
                "change_pct_str": _pct_to_str(it["change_pct"]),
                "row_class": "bg-slate-50" if "价值" in cat else "",
            })
        styles_groups.append({"category": cat, "items": view_items})
    result["styles_groups"] = styles_groups

    # 行业与主题 - 排序并标 Top/Bottom 5
    sectors = sorted(raw.get("sectors", []), key=lambda x: x.get("change_pct", 0), reverse=True)
    n = len(sectors)
    top_k = min(3, n)
    bottom_k = min(3, n)
    view_sectors = []
    for idx, s in enumerate(sectors):
        if idx < top_k:
            row_class = "bg-red-50"
            name_text_class = "text-red-800"
        elif idx >= n - bottom_k:
            row_class = "bg-green-50"
            name_text_class = "text-green-800"
        else:
            row_class = ""
            name_text_class = ""
        leaders = []
        for l in s.get("leaders", []):
            leaders.append({
                "name": l["name"],
                "change_class": _class_by_value(l.get("change_pct", 0.0)),
                "change_pct_str": _pct_to_str(l.get("change_pct", 0.0)),
                "bold": "font-bold" if idx < top_k else "",
            })
        view_sectors.append({
            "etf_name": s["etf_name"],
            "change_class": _class_by_value(s.get("change_pct", 0)),
            "change_pct_str": _pct_to_str(s.get("change_pct", 0)),
            "name_text_class": name_text_class,
            "row_class": row_class,
            "leaders": leaders,
        })
    result["sectors"] = view_sectors

    # 风险偏好
    risks_view = []
    for i, r in enumerate(raw.get("risks", [])):
        risks_view.append({
            "category": r["category"],
            "name": r["name"],
            "change_class": _class_by_value(r.get("value_or_change", 0.0)),
            # 如果名称以“收益率”结尾，则格式化为“↑ xx.xx%”，否则用通用百分比格式化函数
            "value_or_change_str": (
                f"↑ {r['value_or_change']:.2f}%" if r["name"].endswith("收益率")
                else _pct_to_str(r.get("value_or_change", 0.0))
            ),
            "interpretation": r.get("interpretation", ""),
            "row_class": "bg-slate-50" if i % 2 == 0 else "",
        })
    result["risks"] = risks_view

    # 全球环境与关联市场
    groups2: Dict[str, List[dict]] = {}
    for g in raw.get("globals", []):
        groups2.setdefault(g["category"], []).append(g)
    globals_groups = []
    for cat, items in groups2.items():
        vitems = []
        for i, it in enumerate(items):
            vitems.append({
                "indicator": it["indicator"],
                "change_class": _class_by_value(it.get("value_or_change", 0.0)),
                "value_or_change_str": _pct_to_str(it.get("value_or_change", 0.0)),
                "interpretation": it.get("interpretation", ""),
                "row_class": "bg-slate-50" if i % 2 == 0 else "",
            })
        globals_groups.append({"category": cat, "items": vitems})
    result["globals_groups"] = globals_groups

    result["_raw"] = raw
    return result


