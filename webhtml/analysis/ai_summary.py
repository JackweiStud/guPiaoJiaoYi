"""AI 摘要模块

根据《需求说明书.md》的模板组装 Prompt，并在 USE_DEEPSEEK 为真时
调用 DeepSeek Chat Completions 接口生成当日AI结论（控制在约200字）。
"""

from __future__ import annotations

from typing import Dict
import requests

from webhtml.config import settings


def build_prompt_from_view(view: Dict) -> str:
    indexes = view.get("indexes", [])
    up_down = view.get("up_down", {})
    sectors = view.get("sectors", [])
    globals_groups = view.get("globals_groups", [])

    # 选取Top 3、Bottom 2行业名
    top_names = [s.get("etf_name", "") for s in sectors[:3]]
    bottom_names = [s.get("etf_name", "") for s in sectors[-2:]] if len(sectors) >= 2 else [s.get("etf_name", "") for s in sectors[-len(sectors):]]

    def fmt_idx(i: int) -> str:
        if i < len(indexes):
            return f"{indexes[i]['name']}:{indexes[i]['change_pct_str']}"
        return ""

    # 全球与风险信号中，取若干代表项
    globals_flat = []
    for g in globals_groups:
        for item in g.get("items", []):
            globals_flat.append(f"{item['indicator']}:{item['value_or_change_str']}")
    globals_str = ", ".join(globals_flat[:4])

    prompt = (
        "你是一位专业的、风格中立客观的中国A股市场金融分析师。请根据以下今日收盘后的结构化数据，"
        "生成一份不超过200字的、高度概括的当日市场核心结论。\n"
        "必须覆盖：市场整体评价、核心领涨主线(1-3个)、领跌板块(1-2个)、市场风格倾向、关键全球/风险信号。\n\n"
        f"A股市场温度：{fmt_idx(0)}, {fmt_idx(1)}, {fmt_idx(2)}; 涨跌比 {up_down.get('up',0)}:{up_down.get('down',0)}（{up_down.get('label','')}）。\n"
        f"行业Top: {', '.join(top_names)}; 行业Bottom: {', '.join(bottom_names)}。\n"
        f"全球与风险信号: {globals_str}。\n"
        "请直接给出中文结论，不要客套话。"
    )
    return prompt


def _deepseek_chat(prompt: str) -> str:
    url = f"{settings.DEEPSEEK_API_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"}
    system_prompt = (
        "你是一位客观、克制、结构化表达的中国A股市场分析师。"
        "输出严格控制在200字左右，避免夸张措辞。"
    )
    payload = {
        "model": "deepseek-ai/DeepSeek-V3.1",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 512,
        "temperature": 0,
        "top_p": 0,
        "stream": False,
        "response_format": {"type": "text"},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip() or "(AI返回空)"
    except Exception:
        return "(AI调用失败)"


def generate_ai_summary(view: Dict) -> str:
    if not settings.USE_DEEPSEEK:
        return "(未启用AI) 今日市场温度与风格已汇总，详见各表格。"
    prompt = build_prompt_from_view(view)
    return _deepseek_chat(prompt)


