import os
from datetime import datetime


# 项目根目录(以本文件为基准)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")
DATA_DIR = os.path.join(OUTPUT_DIR, "data")

# 模板目录
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
REPORT_TEMPLATE_NAME = "report_template.html"

# 功能开关
SEND_MAIL = 1  # 可选邮件发送，默认关闭，由 main 控制
USE_DEEPSEEK = 1  # 可选AI总结，默认关闭；可复用 deepSeekAi.py

# DeepSeek / 邮件配置占位（请在需要时填充或读取外部配置）
DEEPSEEK_API_BASE = "https://api.siliconflow.cn/v1"
DEEPSEEK_API_KEY = "sk-rmfaxultndibttfndnfxmwryoatbjwtbzyvumrbiamjhhbns"


def ensure_directories() -> None:
    """确保输出目录存在。"""
    for path in (OUTPUT_DIR, REPORT_DIR, LOG_DIR, DATA_DIR):
        os.makedirs(path, exist_ok=True)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def report_filename_for_today() -> str:
    return f"report_{today_str()}.html"


def report_output_path() -> str:
    return os.path.join(REPORT_DIR, report_filename_for_today())


def raw_data_output_path() -> str:
    return os.path.join(DATA_DIR, f"raw_data_{today_str()}.json")


