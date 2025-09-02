from typing import Any, Dict
import json
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

from webhtml.config import settings


def _create_jinja_env():
    env = Environment(
        loader=FileSystemLoader(settings.TEMPLATES_DIR, followlinks=True),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def render_report(data: Dict[str, Any]) -> str:
    """将结构化数据渲染成 HTML 字符串。"""
    env = _create_jinja_env()
    template = env.get_template(settings.REPORT_TEMPLATE_NAME)

    html = template.render(
        report_date=data.get("report_date"),
        ai_summary=data.get("ai_summary", "(AI未启用)"),
        indexes=data.get("indexes", []),
        up_down=data.get("up_down", {}),
        styles_groups=data.get("styles_groups", []),
        sectors=data.get("sectors", []),
        risks=data.get("risks", []),
        globals_groups=data.get("globals_groups", []),
        current_year=data.get("current_year"),
    )
    return html


def save_report(html: str) -> str:
    """保存 HTML 到输出目录，返回文件路径。"""
    settings.ensure_directories()
    output_path = settings.report_output_path()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


def backup_raw_data(raw_data: Dict[str, Any]) -> str:
    """备份原始数据到 output/data 目录。"""
    settings.ensure_directories()
    path = settings.raw_data_output_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    return path


