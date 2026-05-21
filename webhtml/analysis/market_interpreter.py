"""机构级跨资产信号解读规则。

目标不是预测市场，而是把方向、传导和冲突关系讲清楚，避免静态模板误导。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _change(item: Optional[Dict[str, Any]]) -> Optional[float]:
    if not item:
        return None
    value = item.get("value_or_change")
    return float(value) if value is not None else None


def _fmt(label: str, value: Optional[float]) -> str:
    if value is None:
        return f"{label} -"
    sign = "+" if value >= 0 else ""
    return f"{label} {sign}{value:.2f}%"


def _by_code(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("code", "")): item for item in items}


def _make_signal(
    signal: str,
    impact: str,
    strength: str,
    confidence: str,
    summary: str,
    evidence: List[str],
) -> Dict[str, Any]:
    return {
        "signal": signal,
        "impact": impact,
        "strength": strength,
        "confidence": confidence,
        "summary": summary,
        "evidence": evidence,
    }


def build_market_context(raw: Dict[str, Any]) -> Dict[str, Any]:
    globals_by_code = _by_code(raw.get("globals", []))
    risks_by_code = _by_code(raw.get("risks", []))
    ndx = _change(globals_by_code.get("^NDX"))
    hstech = _change(globals_by_code.get("HSTECH.HK"))
    cnh = _change(globals_by_code.get("CNH=X"))
    btc = _change(globals_by_code.get("BTC-USD"))
    eth = _change(globals_by_code.get("ETH-USD"))
    us10y = _change(risks_by_code.get("US10Y"))

    signals: List[Dict[str, Any]] = []
    if ndx is not None and hstech is not None and ndx > 0.8 and hstech < -0.5:
        evidence = [_fmt("纳斯达克100", ndx), _fmt("恒生科技", hstech)]
        if cnh is not None:
            evidence.append(_fmt("USD/CNH", cnh))
        signals.append(
            _make_signal(
                "china_tech_transmission_blocked",
                "negative",
                "medium",
                "high",
                "美股科技强势，但港股科技下跌，外部科技行情对中国资产传导受阻",
                evidence,
            )
        )
    elif ndx is not None and hstech is not None and ndx > 0.8 and hstech > 0.5:
        signals.append(
            _make_signal(
                "global_china_tech_resonance",
                "positive",
                "medium",
                "high",
                "美股科技与港股科技同步走强，科技风险偏好形成共振",
                [_fmt("纳斯达克100", ndx), _fmt("恒生科技", hstech)],
            )
        )

    if cnh is not None and cnh > 0.05:
        signals.append(
            _make_signal(
                "renminbi_weaker",
                "negative",
                "medium",
                "high",
                "美元兑离岸人民币上行，人民币走弱，对外资流入和A股估值偏负面",
                [_fmt("USD/CNH", cnh)],
            )
        )
    elif cnh is not None and cnh < -0.05:
        signals.append(
            _make_signal(
                "renminbi_stronger",
                "positive",
                "medium",
                "high",
                "美元兑离岸人民币下行，人民币走强，对外资流入环境偏正面",
                [_fmt("USD/CNH", cnh)],
            )
        )

    if us10y is not None and us10y > 0:
        signals.append(
            _make_signal(
                "us_yield_valuation_pressure",
                "negative",
                "medium",
                "high",
                "10年期美债收益率上行，全球估值锚抬升，成长股估值承压",
                [_fmt("10年期美债收益率", us10y)],
            )
        )

    if btc is not None and eth is not None and btc > 0 and eth > 0:
        signals.append(
            _make_signal(
                "crypto_risk_appetite",
                "positive",
                "weak",
                "medium",
                "BTC与ETH同步上涨，高波动风险资产回暖，全球风险偏好边际改善",
                [_fmt("BTC", btc), _fmt("ETH", eth)],
            )
        )

    return {
        "globals_by_code": globals_by_code,
        "risks_by_code": risks_by_code,
        "market_signals": signals,
    }


def interpret_global_item(item: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    code = item.get("code")
    value = _change(item)
    globals_by_code = context.get("globals_by_code", {})
    ndx = _change(globals_by_code.get("^NDX"))
    hstech = _change(globals_by_code.get("HSTECH.HK"))
    btc = _change(globals_by_code.get("BTC-USD"))
    eth = _change(globals_by_code.get("ETH-USD"))

    if value is None:
        text = "数据不足，暂不判断方向"
    elif code == "CNH=X":
        if value > 0:
            text = "美元兑离岸人民币上行，人民币走弱，对外资流入和A股估值偏负面"
        elif value < 0:
            text = "美元兑离岸人民币下行，人民币走强，对外资流入环境偏正面"
        else:
            text = "美元兑离岸人民币基本持平，汇率对A股边际影响有限"
    elif code == "HSTECH.HK":
        if value < 0 and ndx is not None and ndx > 0:
            text = "港股科技走弱而美股科技走强，中资科技资产传导受阻，对A股科技情绪偏谨慎"
        elif value > 0 and ndx is not None and ndx > 0:
            text = "港股科技与美股科技同步走强，对A股AI、半导体等成长方向偏正面"
        elif value < 0:
            text = "港股科技走弱，中资成长资产风险偏好承压"
        else:
            text = "港股科技回暖，对A股科技板块情绪有边际支撑"
    elif code == "^NDX":
        if value > 0 and hstech is not None and hstech < 0:
            text = "美股科技反弹，但港股科技未跟随，不能简单外推为A股科技共振"
        elif value > 0:
            text = "美股科技风险偏好改善，对A股AI、半导体等成长方向偏正面"
        else:
            text = "美股科技走弱，对A股成长风格风险偏好偏负面"
    elif code == "^GSPC":
        text = "美股宽基上涨，全球权益风险偏好改善" if value > 0 else "美股宽基走弱，全球权益风险偏好降温"
    elif code == "NVDA":
        text = "英伟达上涨，AI算力链情绪改善" if value > 0 else "英伟达走弱，AI算力链情绪承压"
    elif code == "PGJ":
        text = "中概资产上涨，外资对中国资产风险偏好改善" if value > 0 else "中概资产走弱，外资对中国资产偏谨慎"
    elif code in {"BTC-USD", "ETH-USD"}:
        if btc is not None and eth is not None and btc > 0 and eth > 0:
            text = "高波动风险资产同步回暖，说明全球风险偏好边际改善，但对A股传导较弱"
        else:
            text = "加密资产波动反映高风险偏好变化，对A股只作辅助观察"
    elif code == "^HSI":
        text = "港股大盘上涨，中国资产风险偏好改善" if value > 0 else "港股大盘走弱，中国资产风险偏好承压"
    else:
        text = item.get("interpretation", "")

    return {"interpretation": text}


def interpret_risk_item(item: Dict[str, Any], _context: Dict[str, Any]) -> Dict[str, Any]:
    code = item.get("code")
    value = _change(item)
    name = item.get("name", "")

    if value is None:
        text = "数据不足，暂不判断方向"
    elif code == "US10Y":
        if value > 0:
            text = "10年期美债收益率上行，全球估值锚抬升，对高估值成长股和A股科技偏压制"
        elif value < 0:
            text = "10年期美债收益率下行，成长股估值压力缓解，对A股科技偏正面"
        else:
            text = "10年期美债收益率基本持平，估值锚边际影响有限"
    elif code == "US30Y":
        if value > 0:
            text = "30年期美债收益率上行，长端期限溢价抬升，对全球久期资产和成长股估值偏压制"
        elif value < 0:
            text = "30年期美债收益率下行，长端期限溢价回落，对全球久期资产和成长股估值偏正面"
        else:
            text = "30年期美债收益率基本持平，长端期限溢价边际影响有限"
    elif code == "UK10Y":
        if value > 0:
            text = "英国10年期国债收益率上行，英镑资产长端利率压力升温，对欧洲风险资产偏负面"
        elif value < 0:
            text = "英国10年期国债收益率下行，英镑资产长端利率压力缓解，对欧洲风险资产边际正面"
        else:
            text = "英国10年期国债收益率基本持平，对全球风险偏好边际影响有限"
    elif code == "JP10Y":
        if value > 0:
            text = "日本10年期国债收益率上行，日债利率正常化压力升温，全球套息交易和高估值资产承压"
        elif value < 0:
            text = "日本10年期国债收益率下行，日债利率压力缓解，对全球套息交易冲击边际下降"
        else:
            text = "日本10年期国债收益率基本持平，日债风险锚边际影响有限"
    elif code == "GLOBAL_COMEX_GOLD":
        text = "COMEX黄金上涨，避险或通胀交易升温，需结合美股和利率判断风险属性" if value > 0 else "COMEX黄金走弱，避险需求边际降温"
    elif code == "YINN":
        text = "海外杠杆做多中国资产走强，外资风险偏好改善" if value > 0 else "海外杠杆做多中国资产走弱，外资对中国资产偏谨慎"
    elif code == "518880":
        text = "国内黄金ETF上涨，内资避险需求升温" if value > 0 else "国内黄金ETF走弱，避险需求边际下降"
    elif code == "511090":
        text = "长期国债ETF上涨，久期资产走强，权益风险偏好偏谨慎" if value > 0 else "长期国债ETF走弱，避险资金边际回撤"
    else:
        text = item.get("interpretation", "") or f"{name}方向待观察"

    return {"interpretation": text}
