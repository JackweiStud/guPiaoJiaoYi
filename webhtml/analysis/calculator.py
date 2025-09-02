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
    result: Dict[str, Any] = {
        "report_date": raw.get("date"),
        "current_year": raw.get("date", "0000")[:4],
        "ai_summary": "(AI未开启)",
    }

    # A股市场温度
    indexes = []
    for item in raw.get("indexes", []):
        indexes.append({
            "name": item["name"],
            "close": f"{item['close']:.2f}",
            "change_class": _class_by_value(item["change_pct"]),
            "change_pct_str": _pct_to_str(item["change_pct"]),
            "turnover_billion": f"{item['turnover_billion']}",
        })
    result["indexes"] = indexes
    up_down = raw.get("up_down", {"up": 0, "down": 0})
    label = "普涨" if up_down.get("up", 0) > up_down.get("down", 0) else ("普跌" if up_down.get("up", 0) < up_down.get("down", 0) else "分化")
    result["up_down"] = {"up": up_down.get("up", 0), "down": up_down.get("down", 0), "label": label, "class": _class_by_value(up_down.get("up", 0) - up_down.get("down", 0))}

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

    # 行业与主题 - 排序并标 Top/Bottom
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
            "value_or_change_str": (f"↑ {r['value_or_change']:.2f}%" if r["name"].endswith("收益率") else _pct_to_str(r.get("value_or_change", 0.0))),
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


