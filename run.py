#!/usr/bin/env python3
"""
统一任务运行入口 (报告生成/信号计算/自动任务).

模式 (mode):
  all       运行所有任务 (获取数据 -> 信号计算 -> 生成报告)
  report    仅生成 HTML 报告并发送邮件
  signal    仅计算交易信号
  fetch     仅获取最新行情数据
  auto      运行自动化交易处理流程 (包含 AI 深度分析)

常用示例:
  ./venv/bin/python run.py report                     # 生成 HTML 报表并发送邮件
  ./venv/bin/python run.py signal --codes 159843      # 计算指定代码的交易信号
  ./venv/bin/python run.py auto --codes 512820.SH     # 运行 AI 深度分析及自动化流程
  ./venv/bin/python run.py all --no-ai --no-mail      # 运行全部任务，但禁用 AI 和邮件
  ./venv/bin/python run.py --list-codes               # 查看 strategy_params.json 中的代码列表
  
  ./venv/bin/python run.py auto --codes 512820.SH --no-mail-auto --format json



参数说明:
  --codes           指定代码，多个用逗号分隔 (如 159843,512820.SH)
  --no-fetch        跳过数据抓取，直接使用本地缓存数据
  --no-ai           禁用 HTML 报告中的 AI 市场总结
  --no-mail         禁用 HTML 报告的邮件发送
  --no-mail-auto    禁用自动化流程 (auto 模式) 的邮件发送
  --format          输出格式: text (默认) 或 json (适合机器人集成)
  --summary-file    将运行结果摘要保存到指定文件
  --list-codes      列出当前配置的所有监控代码并退出
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent


def _strip_json_comments(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))


def _load_strategy_codes() -> List[str]:
    params_path = PROJECT_ROOT / "strategy_params.json"
    if not params_path.exists():
        return []
    try:
        raw = _strip_json_comments(params_path.read_text(encoding="utf-8"))
        data = json.loads(raw)
        codes = []
        for key in data.keys():
            if key == "default":
                continue
            if not key.isdigit():
                continue
            if len(key) != 6:
                continue
            codes.append(key)
        return sorted(set(codes))
    except Exception:
        return []


def _normalize_code(code: str) -> str:
    code = code.strip().upper()
    if not code:
        return code
    if "." in code:
        return code
    if code.isdigit() and len(code) == 6:
        # ETF heuristic: 5/6 -> SH, else SZ
        if code.startswith(("5", "6", "9")):
            return f"{code}.SH"
        return f"{code}.SZ"
    return code


def _parse_codes(codes_arg: Optional[str]) -> List[str]:
    if not codes_arg:
        return []
    parts = []
    for item in codes_arg.split(","):
        item = item.strip()
        if not item:
            continue
        parts.append(_normalize_code(item))
    return parts


def _default_codes_for_mode(mode: str) -> List[str]:
    env_key = "AUTO_CODES" if mode == "auto" else "SIGNAL_CODES"
    env_val = os.getenv(env_key, "").strip()
    if env_val:
        return _parse_codes(env_val)

    if mode == "auto":
        # Keep current autoProcess defaults
        return [_normalize_code("159843"), _normalize_code("512820")]

    return [_normalize_code(c) for c in _load_strategy_codes()]


def run_fetch(codes: List[str]) -> Dict[str, bool]:
    if not codes:
        return {}
    from main import ETFTest

    results: Dict[str, bool] = {}
    for code in codes:
        try:
            results[code] = bool(ETFTest(code))
        except Exception:
            results[code] = False
    return results


def run_signal(codes: List[str], fetch_first: bool) -> List[Dict[str, str]]:
    from autoProcess import get_trading_signal

    fetch_results: Dict[str, bool] = {}
    if fetch_first:
        fetch_results = run_fetch(codes)

    signals: List[Dict[str, str]] = []
    for code in codes:
        try:
            _type, text, reason = get_trading_signal(code)
            signals.append({
                "code": code,
                "signal": text,
                "reason": reason,
                "fetch_ok": fetch_results.get(code) if fetch_first else None,
            })
        except Exception as exc:
            signals.append({
                "code": code,
                "signal": "error",
                "reason": f"signal failed: {exc}",
                "fetch_ok": fetch_results.get(code) if fetch_first else None,
            })
    return signals


def run_auto(codes: List[str], send_email: bool) -> List[Dict[str, str]]:
    from autoProcess import run_trading_strategy

    results: List[Dict[str, str]] = []
    for code in codes:
        try:
            result = run_trading_strategy(code, send_email=send_email)
            if isinstance(result, dict):
                results.append(result)
            else:
                results.append({"code": code, "status": "ok"})
        except Exception as exc:
            results.append({"code": code, "status": f"error: {exc}"})
    return results


def run_report(no_ai: bool, no_mail: bool) -> Dict[str, str]:
    from webhtml.config import settings
    from webhtml.reporter.generator import render_report, save_report, backup_raw_data
    from webhtml.data_handler.fetcher import fetch_all_data
    from webhtml.analysis.calculator import build_report_view
    from webhtml.analysis.ai_summary import generate_ai_summary

    if no_ai:
        settings.USE_DEEPSEEK = 0
    if no_mail:
        settings.SEND_MAIL = 0

    raw = fetch_all_data()
    view = build_report_view(raw)
    view["ai_summary"] = generate_ai_summary(view)

    backup_raw_data(view.get("_raw", {}))
    html = render_report(view)
    output_path = save_report(html)

    return {
        "report_date": str(view.get("report_date") or ""),
        "report_path": str(output_path),
        "ai_summary": str(view.get("ai_summary") or ""),
    }


def _emit_summary(payload: Dict, fmt: str, summary_file: Optional[str]) -> None:
    if fmt == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        lines = []
        lines.append("===SUMMARY===")
        lines.append(f"time: {payload.get('generated_at','')}")
        lines.append(f"mode: {payload.get('mode','')}")
        if payload.get("report"):
            report = payload["report"]
            lines.append(f"report_date: {report.get('report_date','')}")
            lines.append(f"report_path: {report.get('report_path','')}")
            lines.append(f"ai_summary: {report.get('ai_summary','')}")
        if payload.get("signals"):
            lines.append("signals:")
            for item in payload["signals"]:
                lines.append(f"{item.get('code','')}: {item.get('signal','')} | {item.get('reason','')}")
        if payload.get("auto"):
            lines.append("auto:")
            for item in payload["auto"]:
                lines.append(f"{item.get('code','')}: {item.get('status','')}")
        lines.append("===END SUMMARY===")
        text = "\n".join(lines)

    print(text)

    if summary_file:
        Path(summary_file).write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified entrypoint for guPiaoJiaoYi.")
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["all", "report", "signal", "fetch", "auto"],
        help="Task mode to run",
    )
    parser.add_argument("--codes", help="Comma-separated codes, e.g. 159843,512820.SH")
    parser.add_argument("--no-fetch", action="store_true", help="Skip data fetch before signal")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI summary in report")
    parser.add_argument("--no-mail", action="store_true", help="Disable report email sending")
    parser.add_argument("--no-mail-auto", action="store_true", help="Disable autoProcess email sending")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Summary output format")
    parser.add_argument("--summary-file", help="Write summary to a file")
    parser.add_argument("--list-codes", action="store_true", help="List default signal codes and exit")

    args = parser.parse_args()

    payload: Dict = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        # Always echo the exact invocation for automation/audit (OpenClaw/TG).
        "invocation": {
            "python": sys.executable,
            "cwd": os.getcwd(),
            "argv": sys.argv,
        },
    }

    if args.list_codes:
        defaults = _default_codes_for_mode("signal")
        print("\n".join(defaults))
        return 0

    codes = _parse_codes(args.codes)
    if not codes and args.mode in ("signal", "fetch", "auto", "all"):
        codes = _default_codes_for_mode("auto" if args.mode == "auto" else "signal")

    if args.mode in ("report", "all"):
        payload["report"] = run_report(no_ai=args.no_ai, no_mail=args.no_mail)

    if args.mode in ("signal", "all"):
        payload["signals"] = run_signal(codes, fetch_first=not args.no_fetch)

    if args.mode == "fetch":
        payload["fetch"] = run_fetch(codes)

    if args.mode == "auto":
        payload["auto"] = run_auto(codes, send_email=not args.no_mail_auto)

    _emit_summary(payload, fmt=args.format, summary_file=args.summary_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
